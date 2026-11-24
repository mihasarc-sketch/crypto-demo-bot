import json
import math
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# CRYPTO DEMO BOT 5.4 - PAPER TRADING ONLY - NO REAL ORDERS
# Strategy 5.3 plus a filtered momentum-breakout entry; virtual-only.
COINS = {
    "BTC": ["XBTUSD"], "ETH": ["ETHUSD"], "SOL": ["SOLUSD"], "XRP": ["XRPUSD"],
    "ADA": ["ADAUSD"], "DOGE": ["DOGEUSD", "XDGUSD"], "LINK": ["LINKUSD"],
    "AVAX": ["AVAXUSD"], "LTC": ["LTCUSD"], "DOT": ["DOTUSD"], "GOLD": [], "SILVER": []
}
METALS = {"GOLD": "PF_XAUUSD", "SILVER": "PF_XAGUSD"}
FUTURES_CHARTS = "https://futures.kraken.com/api/charts/v1"
START_CASH = 1000.0
MAX_BUY = 100.0
FEE = 0.001
SLIPPAGE = 0.0005
STOP_LOSS = 0.05  # legacy positions only
TAKE_PROFIT = 0.08  # legacy positions only
NEW_STOP_LOSS = 0.04
NEW_TAKE_PROFIT = 0.06
PROFIT_LOCK_ACTIVATION = 0.03  # activate after a completed candle closes +3% above entry
PROFIT_LOCK_FLOOR = 0.01       # protect at least +1% gross above entry
PROFIT_TRAIL_GIVEBACK = 0.025  # trail 2.5% below the best completed-candle high
MAX_OPEN_POSITIONS = 4
DAILY_MAX_LOSS = START_CASH * 0.02
MAX_CONSECUTIVE_LOSSES = 3
BREAKOUT_VOLUME_MULTIPLE = 1.20
VOLUME_LOOKBACK = 20
MOMENTUM_RSI_MIN = 48.0
MOMENTUM_RSI_MAX = 68.0
MOMENTUM_MAX_EMA_DISTANCE = 0.025
MOMENTUM_BREAKOUT_LOOKBACK = 10
BB_PERIOD = 20
BB_DEVIATIONS = 2.0
RSI_PERIOD = 14
CANDLE_INTERVAL = 240
STATE = Path("state.json")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoDemoBot/5.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode())


def telegram(message):
    """Send a notification without allowing Telegram outages to fail the paper-trading run."""
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM WARNING: nicht konfiguriert; Paper-Trading-Lauf wird fortgesetzt.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body)
        if result.get("ok"):
            print("Telegram-Benachrichtigung erfolgreich gesendet.")
            return True
        print("TELEGRAM WARNING: API meldet Fehler: " + str(result.get("description", "unbekannter Fehler")))
        return False
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(details).get("description", details)
        except (ValueError, TypeError):
            pass
        print(f"TELEGRAM WARNING: HTTP {error.code}: {details}")
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"TELEGRAM WARNING: Verbindungsfehler: {error}")
        return False
    except (ValueError, TypeError) as error:
        print(f"TELEGRAM WARNING: Antwort konnte nicht verarbeitet werden: {error}")
        return False


def load_state():
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text())
            if not isinstance(data, dict):
                raise RuntimeError("State-Datei hat ein ungültiges Format.")
            data.setdefault("cash", START_CASH)
            data.setdefault("positions", {})
            data.setdefault("trades", [])
            data.setdefault("realized", 0.0)
            return data
        except Exception as error:
            raise RuntimeError(f"State-Datei fehlerhaft; sicherer Abbruch statt Kontoreset: {error}") from error
    return {"cash": START_CASH, "positions": {}, "trades": [], "realized": 0.0}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def rsi(values, period=RSI_PERIOD):
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = changes[-period:]
    gains = sum(max(change, 0.0) for change in recent) / period
    losses = sum(max(-change, 0.0) for change in recent) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def bands(values):
    window = values[-BB_PERIOD:]
    middle = sum(window) / BB_PERIOD
    deviation = math.sqrt(sum((value - middle) ** 2 for value in window) / BB_PERIOD)
    return middle, middle - BB_DEVIATIONS * deviation


def ema(values, period=50):
    if len(values) < period:
        raise RuntimeError(f"Zu wenige Kerzen für EMA{period}")
    multiplier = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = (value - current) * multiplier + current
    return current


def market(coin):
    # Public Kraken Futures candles are used for metal price references only.
    # All positions remain virtual; this bot never sends orders.
    if coin in METALS:
        symbol = METALS[coin]
        now = int(datetime.now(timezone.utc).timestamp())
        start = now - 120 * 86400
        url = f"{FUTURES_CHARTS}/trade/{symbol}/4h?from={start}&to={now}"
        payload = api(url)
        rows = []
        for candle in payload.get("candles", []):
            candle_time = int(candle["time"]) // 1000
            if candle_time + CANDLE_INTERVAL * 60 <= now:
                rows.append({
                    "time": candle_time, "open": float(candle["open"]),
                    "high": float(candle["high"]), "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": float(candle.get("volume", 0) or 0)
                })
        rows.sort(key=lambda row: row["time"])
        closes = [row["close"] for row in rows]
        if len(closes) < BB_PERIOD + RSI_PERIOD + 2:
            raise RuntimeError(f"{symbol}: zu wenige abgeschlossene 4h-Kerzen")
        middle, lower = bands(closes)
        previous_lower = bands(closes[:-1])[1]
        ema50 = ema(closes, 50)
        ema50_previous = ema(closes[:-1], 50)
        last = rows[-1]
        return {
            "price": last["close"], "open": last["open"], "high": last["high"], "low": last["low"],
            "middle": middle, "lower": lower, "previous_close": closes[-2],
            "previous_lower": previous_lower, "rsi": rsi(closes),
            "ema50": ema50, "ema50_previous": ema50_previous,
            "prior_high": max(row["high"] for row in rows[-11:-1]),
            "volume": last.get("volume", 0.0),
            "average_volume": (sum(row.get("volume", 0.0) for row in rows[-VOLUME_LOOKBACK-1:-1]) / VOLUME_LOOKBACK
                               if len(rows) >= VOLUME_LOOKBACK + 1 else 0.0),
            "candle_time": str(last["time"])
        }

    errors = []
    for pair in COINS[coin]:
        try:
            url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={CANDLE_INTERVAL}"
            data = api(url)
            if data.get("error"):
                errors.append(f"{pair}: {data['error']}")
                continue
            result = data["result"]
            key = next(key for key in result if key != "last")
            rows = result[key][:-1]
            closes = [float(row[4]) for row in rows]
            if len(closes) < BB_PERIOD + RSI_PERIOD + 2:
                raise RuntimeError("Zu wenige abgeschlossene 4h-Kerzen")
            middle, lower = bands(closes)
            previous_lower = bands(closes[:-1])[1]
            ema50 = ema(closes, 50)
            ema50_previous = ema(closes[:-1], 50)
            last = rows[-1]
            return {
                "price": float(last[4]), "open": float(last[1]), "high": float(last[2]), "low": float(last[3]),
                "middle": middle, "lower": lower, "previous_close": closes[-2],
                "previous_lower": previous_lower, "rsi": rsi(closes),
                "ema50": ema50, "ema50_previous": ema50_previous,
                "prior_high": max(float(row[2]) for row in rows[-11:-1]),
                "volume": float(last[6]),
                "average_volume": (sum(float(row[6]) for row in rows[-VOLUME_LOOKBACK-1:-1]) / VOLUME_LOOKBACK
                                   if len(rows) >= VOLUME_LOOKBACK + 1 else 0.0),
                "candle_time": str(int(float(last[0])))
            }
        except Exception as error:
            errors.append(f"{pair}: {error}")
    raise RuntimeError("; ".join(errors))


def buy(state, coin, price, strategy="bollinger_reclaim_ema50_rsi40_4h_v3_profit_lock"): 
    budget = min(MAX_BUY, state["cash"] * 0.20)
    if budget < 10:
        return None
    execution_price = price * (1 + SLIPPAGE)
    quantity = budget * (1 - FEE) / execution_price
    state["cash"] -= budget
    state["positions"][coin] = {
        "entry": execution_price, "quantity": quantity, "cost": budget,
        "strategy": strategy,
        "stop_loss_pct": NEW_STOP_LOSS, "take_profit_pct": NEW_TAKE_PROFIT,
        "peak_price": execution_price, "profit_lock_active": False,
        "opened_at": datetime.now(timezone.utc).isoformat()
    }
    state["trades"].append({
        "coin": coin, "action": "BUY", "price": execution_price, "cost": budget,
        "strategy": strategy,
        "stop_loss_pct": NEW_STOP_LOSS, "take_profit_pct": NEW_TAKE_PROFIT,
        "time": datetime.now(timezone.utc).isoformat()
    })
    return f"🟢 DEMO-KAUF {coin}: ca. {execution_price:.6f} USD (virtuell)"


def open_positions_unrealized(state, prices):
    """Estimate open-position P&L at liquidation prices, including simulated exit costs."""
    total = 0.0
    for coin, position in state.get("positions", {}).items():
        mark = float(prices.get(coin, position.get("last_price", position["entry"])))
        exit_price = mark * (1 - SLIPPAGE)
        proceeds = float(position["quantity"]) * exit_price * (1 - FEE)
        total += proceeds - float(position["cost"])
    return total


def daily_risk_pnl(state, prices):
    return float(state.get("daily_realized", 0.0)) + open_positions_unrealized(state, prices)


def sell(state, coin, price, reason):
    position = state["positions"].pop(coin)
    execution_price = price * (1 - SLIPPAGE)
    gross = position["quantity"] * execution_price
    proceeds = gross * (1 - FEE)
    profit = proceeds - position["cost"]
    state["cash"] += proceeds
    state["realized"] += profit
    strategy = position.get("strategy", "legacy_unclassified")
    state["trades"].append({
        "coin": coin, "action": "SELL", "price": execution_price, "profit": profit,
        "reason": reason, "strategy": strategy,
        "time": datetime.now(timezone.utc).isoformat()
    })
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("risk_day") != today:
        state["risk_day"] = today
        state["daily_realized"] = 0.0
        state["consecutive_losses"] = 0
    state["daily_realized"] = float(state.get("daily_realized", 0.0)) + profit
    state["consecutive_losses"] = (int(state.get("consecutive_losses", 0)) + 1) if profit < 0 else 0
    return (f"🔴 DEMO-VERKAUF {coin}: ca. {execution_price:.6f} USD\n"
            f"Grund: {reason}\nErgebnis: {profit:+.2f} USD")


def main():
    state = load_state()
    state.setdefault("last_4h_candle", {})
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("risk_day") != today:
        state["risk_day"] = today
        state["daily_realized"] = 0.0
        state["consecutive_losses"] = 0
    state.setdefault("daily_realized", 0.0)
    state.setdefault("consecutive_losses", 0)
    messages, market_lines, decision_lines, errors = [], [], [], []
    signals, prices = {}, {}
    print("CRYPTO DEMO BOT 5.6 - BALANCED / TRAILING PRIORITY / COMBINED DAILY RISK / 4H")
    print("PAPER TRADING - KEIN ECHTHANDEL - KEINE ECHTEN ORDERS")

    for coin in COINS:
        try:
            data = market(coin)
            price = data["price"]
            prices[coin] = price
            previous_candle = state["last_4h_candle"].get(coin)
            new_candle = data["candle_time"] != previous_candle
            market_lines.append(
                f"{coin}: {price:.6f} USD | RSI: {data['rsi']:.1f} | EMA50: {data['ema50']:.6f} | "
                f"BB-Mitte: {data['middle']:.6f} | BB-Unterband: {data['lower']:.6f}"
            )
            position = state["positions"].get(coin)
            if position:
                position["last_price"] = float(price)
            signal = {
                "price": round(price, 8), "rsi": round(data["rsi"], 2),
                "bb_middle": round(data["middle"], 8), "bb_lower": round(data["lower"], 8),
                "ema50": round(data["ema50"], 8),
                "volume": round(float(data.get("volume", 0.0)), 4),
                "average_volume": round(float(data.get("average_volume", 0.0)), 4),
                "volume_ratio": (round(float(data["volume"]) / float(data["average_volume"]), 2)
                                 if float(data.get("average_volume", 0.0)) > 0 else None),
                "trend_up": bool(price > data["ema50"] and data["ema50"] > data["ema50_previous"]),
                "candle_time": data["candle_time"],
                "updated": datetime.now(timezone.utc).isoformat()
            }

            if not new_candle:
                decision_lines.append(f"{coin}: WARTEN - 4h-Kerze bereits geprüft")
                signal.update({"decision": "WAIT", "reason": "Keine neue abgeschlossene 4h-Kerze"})
            else:
                state["last_4h_candle"][coin] = data["candle_time"]
                if position:
                    stop_pct = float(position.get("stop_loss_pct", STOP_LOSS))
                    target_pct = float(position.get("take_profit_pct", TAKE_PROFIT))
                    entry_price = float(position["entry"])
                    stop_price = entry_price * (1 - stop_pct)
                    target_price = entry_price * (1 + target_pct)
                    # Use only highs/closes from completed candles. A newly activated
                    # profit lock becomes effective on the following completed candle.
                    previous_peak = float(position.get("peak_price", entry_price))
                    lock_was_active = bool(position.get("profit_lock_active", False))
                    trailing_stop = max(
                        entry_price * (1 + PROFIT_LOCK_FLOOR),
                        previous_peak * (1 - PROFIT_TRAIL_GIVEBACK)
                    )
                    if lock_was_active and data["low"] <= trailing_stop:
                        # Active profit protection is checked before the original hard stop.
                        # A gap can still produce a worse simulated fill at the candle open.
                        exit_price = data["open"] if data["open"] <= trailing_stop else trailing_stop
                        reason = f"Gewinnsicherung / Trailing-Stop (mind. +{PROFIT_LOCK_FLOOR:.0%} brutto)"
                        messages.append(sell(state, coin, exit_price, reason))
                        decision_lines.append(f"{coin}: VERKAUF - Gewinnsicherung")
                        signal.update({"decision": "SELL", "reason": reason})
                    elif data["low"] <= stop_price:
                        exit_price = data["open"] if data["open"] <= stop_price else stop_price
                        messages.append(sell(state, coin, exit_price, f"Stop-Loss {stop_pct:.0%}"))
                        decision_lines.append(f"{coin}: VERKAUF - Stop-Loss {stop_pct:.0%}")
                        signal.update({"decision": "SELL", "reason": f"Stop-Loss {stop_pct:.0%}"})
                    elif data["high"] >= target_price:
                        exit_price = data["open"] if data["open"] >= target_price else target_price
                        messages.append(sell(state, coin, exit_price, f"Take-Profit {target_pct:.0%}"))
                        decision_lines.append(f"{coin}: VERKAUF - Take-Profit {target_pct:.0%}")
                        signal.update({"decision": "SELL", "reason": f"Take-Profit {target_pct:.0%}"})
                    elif price >= data["middle"]:
                        messages.append(sell(state, coin, price, "Bollinger-Mittelband erreicht"))
                        decision_lines.append(f"{coin}: VERKAUF - Bollinger-Mittelband erreicht")
                        signal.update({"decision": "SELL", "reason": "Bollinger-Mittelband erreicht"})
                    else:
                        position["peak_price"] = max(previous_peak, float(data["high"]))
                        if lock_was_active or price >= entry_price * (1 + PROFIT_LOCK_ACTIVATION):
                            position["profit_lock_active"] = True
                        decision_lines.append(f"{coin}: HALTEN - Position offen")
                        lock_text = "Gewinnsicherung aktiv" if position.get("profit_lock_active") else f"Gewinnsicherung ab +{PROFIT_LOCK_ACTIVATION:.0%}"
                        signal.update({"decision": "HOLD", "reason": f"Kein Ausstiegssignal · {lock_text}"})
                else:
                    entry_signal = (
                        data["previous_close"] < data["previous_lower"]
                        and price > data["lower"]
                        and data["rsi"] <= 40
                        and price > data["ema50"]
                        and data["ema50"] > data["ema50_previous"]
                    )
                    volume_ok = (
                        float(data.get("average_volume", 0.0)) > 0
                        and float(data.get("volume", 0.0)) >=
                            float(data["average_volume"]) * BREAKOUT_VOLUME_MULTIPLE
                    )
                    momentum_signal = (
                        price > data["prior_high"]
                        and price > data["ema50"]
                        and data["ema50"] > data["ema50_previous"]
                        and MOMENTUM_RSI_MIN <= data["rsi"] <= MOMENTUM_RSI_MAX
                        and price <= data["ema50"] * (1 + MOMENTUM_MAX_EMA_DISTANCE)
                        and volume_ok
                    )
                    combined_daily_pnl = daily_risk_pnl(state, prices)
                    risk_pause = (
                        combined_daily_pnl <= -DAILY_MAX_LOSS
                        or int(state.get("consecutive_losses", 0)) >= MAX_CONSECUTIVE_LOSSES
                    )
                    if risk_pause:
                        pause_reason = (f"Tagesverlust-Limit erreicht (realisiert + offen: {combined_daily_pnl:+.2f} USD)"
                                        if combined_daily_pnl <= -DAILY_MAX_LOSS
                                        else f"{MAX_CONSECUTIVE_LOSSES} Verlusttrades in Folge")
                        decision_lines.append(f"{coin}: KAUFPAUSE - {pause_reason}")
                        signal.update({"decision": "WAIT", "reason": f"Kaufsperre bis UTC-Tageswechsel: {pause_reason}"})
                    elif len(state["positions"]) >= MAX_OPEN_POSITIONS:
                        decision_lines.append(f"{coin}: WARTEN - maximal {MAX_OPEN_POSITIONS} Positionen gleichzeitig")
                        signal.update({"decision": "WAIT", "reason": "Maximale Anzahl offener Positionen erreicht"})
                    elif entry_signal or momentum_signal:
                        strategy = ("bollinger_reclaim_ema50_rsi40_4h_v3_profit_lock" if entry_signal
                                    else "momentum_breakout_ema50_rsi48_68_4h_v1")
                        result = buy(state, coin, price, strategy)
                        if result:
                            messages.append(result)
                            decision_lines.append(f"{coin}: KAUFSIGNAL - DEMO-KAUF ({'Bollinger-Reclaim' if entry_signal else 'Momentum-Ausbruch'})")
                            signal.update({"decision": "BUY", "reason": ("Bollinger-Reclaim + RSI <= 40" if entry_signal else f"Momentum-Ausbruch + Volumen {float(data['volume']) / float(data['average_volume']):.2f}x Durchschnitt; EMA50 steigend; RSI 48-68")})
                        else:
                            decision_lines.append(f"{coin}: KEIN KAUF - virtuelles Budget zu klein")
                            signal.update({"decision": "WAIT", "reason": "Virtuelles Budget zu klein"})
                    else:
                        reasons = []
                        if not (data["previous_close"] < data["previous_lower"] and price > data["lower"]):
                            reasons.append("kein bestätigter Rücklauf über das untere Bollinger-Band")
                        if data["rsi"] > 40:
                            reasons.append("RSI über 40 für Bollinger-Einstieg")
                        if not volume_ok:
                            reasons.append(f"Ausbruchsvolumen unter {BREAKOUT_VOLUME_MULTIPLE:.2f}x Durchschnitt")
                        if not (price > data["ema50"] and data["ema50"] > data["ema50_previous"]):
                            reasons.append("Trendfilter EMA50 nicht aufwärts")
                        reason = "; ".join(reasons) or "Einstiegsbedingungen nicht vollständig"
                        decision_lines.append(f"{coin}: KEIN KAUF - {reason}")
                        signal.update({"decision": "WAIT", "reason": reason})
            signals[coin] = signal
        except Exception as error:
            msg = f"{coin}: {str(error)[:140]}"
            errors.append(msg)
            decision_lines.append(f"{coin}: NICHT AUSWERTBAR - {str(error)[:110]}")
            signals[coin] = {"decision": "ERROR", "reason": str(error)[:160],
                             "updated": datetime.now(timezone.utc).isoformat()}
            print(f"Fehler {coin}: {error}")

    invested = sum(position["cost"] for position in state["positions"].values())
    market_value = sum(
        position["quantity"] * prices.get(coin, position["entry"])
        for coin, position in state["positions"].items()
    )
    total = state["cash"] + market_value
    unrealized = total - START_CASH - state["realized"]
    combined_daily_pnl = daily_risk_pnl(state, prices)
    daily_loss_limit_reached = combined_daily_pnl <= -DAILY_MAX_LOSS
    closed = [trade for trade in state["trades"] if trade.get("action") == "SELL" and "profit" in trade]
    winners = [trade for trade in closed if trade["profit"] > 0]
    losers = [trade for trade in closed if trade["profit"] < 0]
    gross_profit = sum(trade["profit"] for trade in winners)
    gross_loss = abs(sum(trade["profit"] for trade in losers))
    win_rate = len(winners) / len(closed) * 100 if closed else 0
    profit_factor = gross_profit / gross_loss if gross_loss else None
    tracked_strategies = {
        "bollinger_reclaim_ema50_rsi40_4h_v3_profit_lock",
        "momentum_breakout_ema50_rsi48_68_4h_v1"
    }
    strategy_performance = {}
    for strategy in tracked_strategies:
        strategy_sells = [t for t in closed if t.get("strategy") == strategy]
        strategy_wins = sum(1 for t in strategy_sells if float(t.get("profit", 0)) > 0)
        strategy_performance[strategy] = {
            "closed": len(strategy_sells),
            "wins": strategy_wins,
            "losses": sum(1 for t in strategy_sells if float(t.get("profit", 0)) < 0),
            "win_rate": round(strategy_wins / len(strategy_sells) * 100, 1) if strategy_sells else None,
            "net_profit": round(sum(float(t.get("profit", 0)) for t in strategy_sells), 2)
        }

    report = [
        "🤖 CRYPTO DEMO BOT 5.6 - AUSGEWOGEN",
        "Strategie A: Bollinger-Reclaim + EMA50-Aufwärtstrend + RSI <= 40 | 4H",
        f"Strategie B: Momentum-Ausbruch über {MOMENTUM_BREAKOUT_LOOKBACK}-Kerzen-Hoch + EMA50 steigend + RSI {MOMENTUM_RSI_MIN:.0f}-{MOMENTUM_RSI_MAX:.0f} + max. {MOMENTUM_MAX_EMA_DISTANCE:.1%} über EMA50 + Volumen >= {BREAKOUT_VOLUME_MULTIPLE:.2f}x Durchschnitt | 4H",
        f"Risikokontrolle: Tagesverlust-Limit {DAILY_MAX_LOSS:.2f} USD (realisierte + offene Verluste) | Kaufpause nach {MAX_CONSECUTIVE_LOSSES} Verlusten in Folge | max. {MAX_OPEN_POSITIONS} Positionen",
        "Neue Trades: Stop-Loss 4 % | Take-Profit 6 % | Gewinnsicherung ab +3 %, mindestens +1 % brutto, Trailing 2,5 % | max. 4 Positionen",
        "Bestehende Positionen behalten ihre gespeicherten Stop-/Zielwerte.",
        "PAPER TRADING - KEIN ECHTHANDEL",
        "Gebühr 0,10 % + Slippage 0,05 % je Seite (simuliert)",
        "━━━━━━━━━━━━━━━━", "MARKTDATEN:", *market_lines,
        "━━━━━━━━━━━━━━━━", "KAUF-/VERKAUFS-CHECK:", *decision_lines,
        "━━━━━━━━━━━━━━━━",
        f"Virtuelles Cash: {state['cash']:.2f} USD",
        f"Investiert (Einstand): {invested:.2f} USD",
        f"Positionswert: {market_value:.2f} USD",
        f"Gesamtwert: {total:.2f} USD",
        f"Realisierter Gewinn seit Start: {state['realized']:+.2f} USD",
        f"Offener Gewinn: {unrealized:+.2f} USD",
        f"Offene Positionen: {len(state['positions'])}",
        f"Trades insgesamt: {len(state['trades'])}",
        f"Geschlossene Trades: {len(closed)}",
        f"Gewinner / Verlierer: {len(winners)} / {len(losers)}",
        f"Trefferquote: {win_rate:.1f} %",
        f"Profit-Faktor: {profit_factor:.2f}" if profit_factor is not None else "Profit-Faktor: noch nicht berechenbar",
        f"Tagesergebnis realisiert: {float(state.get('daily_realized', 0.0)):+.2f} USD | offene Positionen: {open_positions_unrealized(state, prices):+.2f} USD | zusammen: {combined_daily_pnl:+.2f} USD | Verlustserie: {int(state.get('consecutive_losses', 0))}",
        "Strategie A (nur korrekt zugeordnete Abschlüsse): " + json.dumps(strategy_performance["bollinger_reclaim_ema50_rsi40_4h_v3_profit_lock"]),
        "Strategie B (nur korrekt zugeordnete Abschlüsse): " + json.dumps(strategy_performance["momentum_breakout_ema50_rsi48_68_4h_v1"]),
        "━━━━━━━━━━━━━━━━", "PAPER TRADING - KEINE ECHTEN BÖRSENORDERS"
    ]
    if messages:
        report.extend(["", "AUSGEFÜHRTE DEMO-TRADES:", *messages])
    if errors:
        report.extend(["", "DATENFEHLER:", *errors])

    report_text = "\n".join(report)
    print(report_text)
    state["signals"] = signals
    state["strategy_performance"] = strategy_performance
    state["risk_controls"] = {
        "daily_max_loss": DAILY_MAX_LOSS,
        "daily_realized": float(state.get("daily_realized", 0.0)),
        "open_unrealized": open_positions_unrealized(state, prices),
        "daily_combined_pnl": combined_daily_pnl,
        "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,
        "buy_paused": (daily_loss_limit_reached
                       or int(state.get("consecutive_losses", 0)) >= MAX_CONSECUTIVE_LOSSES)
    }
    state["updated"] = datetime.now(timezone.utc).isoformat()
    state["strategy_version"] = "5.6_balanced_trailing_priority_combined_daily_loss_paper"
    save_state(state)
    telegram(report_text)


if __name__ == "__main__":
    main()
