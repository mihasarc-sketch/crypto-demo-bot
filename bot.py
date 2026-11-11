import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

# CRYPTO DEMO BOT 4.1 - PAPER TRADING ONLY - NO REAL ORDERS
COINS = ["BTC", "ETH", "SOL", "XRP"]
START_CASH = 1000.0
MAX_BUY = 100.0
FEE = 0.001
STOP_LOSS = 0.03
TAKE_PROFIT = 0.06
STATE = Path("state.json")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoDemoBot/4.1"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram nicht konfiguriert.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.loads(response.read().decode())
        if not result.get("ok"):
            raise RuntimeError("Telegram-Nachricht fehlgeschlagen")


def load_state():
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text())
            data.setdefault("cash", START_CASH)
            data.setdefault("positions", {})
            data.setdefault("trades", [])
            data.setdefault("realized", 0.0)
            return data
        except Exception:
            print("State-Datei fehlerhaft. Neuer Start.")
    return {"cash": START_CASH, "positions": {}, "trades": [], "realized": 0.0}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def ema(values, period):
    result = values[0]
    multiplier = 2 / (period + 1)
    for value in values[1:]:
        result = value * multiplier + result * (1 - multiplier)
    return result


def rsi(values, period=14):
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = changes[-period:]
    gains = [max(x, 0) for x in recent]
    losses = [max(-x, 0) for x in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def market(coin):
    pairs = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD", "XRP": "XRPUSD"}
    url = "https://api.kraken.com/0/public/OHLC" + f"?pair={pairs[coin]}&interval=60"
    data = api(url)
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    result = data["result"]
    key = next(k for k in result if k != "last")
    candles = result[key]
    # Only completed hourly candles are used.
    closes = [float(row[4]) for row in candles[:-1]]
    if len(closes) < 50:
        raise RuntimeError("Zu wenige Marktdaten für EMA-Auswertung")
    price = closes[-1]
    fast = ema(closes[-30:], 9)
    slow = ema(closes[-50:], 21)
    strength = rsi(closes)
    return price, fast, slow, strength


def buy(state, coin, price):
    budget = min(MAX_BUY, state["cash"] * 0.20)
    if budget < 10:
        return None
    quantity = budget * (1 - FEE) / price
    state["cash"] -= budget
    state["positions"][coin] = {"entry": price, "quantity": quantity, "cost": budget}
    state["trades"].append({
        "coin": coin, "action": "BUY", "price": price, "cost": budget,
        "time": datetime.now(timezone.utc).isoformat()
    })
    return f"🟢 DEMO-KAUF {coin}: {price:.4f} USD"


def sell(state, coin, price, reason):
    position = state["positions"].pop(coin)
    gross = position["quantity"] * price
    proceeds = gross * (1 - FEE)
    profit = proceeds - position["cost"]
    state["cash"] += proceeds
    state["realized"] += profit
    state["trades"].append({
        "coin": coin, "action": "SELL", "price": price, "profit": profit,
        "reason": reason, "time": datetime.now(timezone.utc).isoformat()
    })
    return (f"🔴 DEMO-VERKAUF {coin}: {price:.4f} USD\n"
            f"Grund: {reason}\nErgebnis: {profit:+.2f} USD")


def main():
    state = load_state()
    messages, market_lines, decision_lines, errors = [], [], [], []
    print("CRYPTO DEMO BOT 4.1")
    print("PAPER TRADING - KEIN ECHTHANDEL")

    for coin in COINS:
        try:
            price, fast, slow, strength = market(coin)
            market_lines.append(
                f"{coin}: {price:.4f} USD | RSI: {strength:.1f} | "
                f"EMA9: {fast:.4f} | EMA21: {slow:.4f}"
            )
            position = state["positions"].get(coin)

            if position:
                change = price / position["entry"] - 1
                if change <= -STOP_LOSS:
                    messages.append(sell(state, coin, price, "Stop-Loss"))
                    decision_lines.append(f"{coin}: VERKAUF - Stop-Loss erreicht")
                elif change >= TAKE_PROFIT:
                    messages.append(sell(state, coin, price, "Take-Profit"))
                    decision_lines.append(f"{coin}: VERKAUF - Take-Profit erreicht")
                elif fast < slow:
                    messages.append(sell(state, coin, price, "EMA-Signal"))
                    decision_lines.append(f"{coin}: VERKAUF - EMA9 unter EMA21")
                else:
                    decision_lines.append(f"{coin}: HALTEN - Position offen, kein Verkaufssignal")
            else:
                reasons = []
                if fast <= slow:
                    reasons.append("EMA9 liegt nicht über EMA21")
                if strength < 50:
                    reasons.append("RSI unter 50")
                elif strength > 68:
                    reasons.append("RSI über 68")
                if state["cash"] < 10:
                    reasons.append("zu wenig virtuelles Guthaben")

                if reasons:
                    decision_lines.append(f"{coin}: KEIN KAUF - " + "; ".join(reasons))
                else:
                    result = buy(state, coin, price)
                    if result:
                        messages.append(result)
                        decision_lines.append(f"{coin}: KAUFSIGNAL JA - DEMO-KAUF ausgeführt")
                    else:
                        decision_lines.append(f"{coin}: KEIN KAUF - Budget zu klein")
        except Exception as error:
            msg = f"{coin}: {str(error)[:120]}"
            errors.append(msg)
            decision_lines.append(f"{coin}: NICHT AUSWERTBAR - {str(error)[:100]}")
            print(f"Fehler {coin}: {error}")

    invested = sum(p["cost"] for p in state["positions"].values())
    market_value = 0.0
    for coin, position in state["positions"].items():
        try:
            price, _, _, _ = market(coin)
            market_value += position["quantity"] * price
        except Exception:
            market_value += position["cost"]

    total = state["cash"] + market_value
    unrealized = total - START_CASH - state["realized"]
    report = [
        "🤖 CRYPTO DEMO BOT 4.1",
        "PAPER TRADING - KEIN ECHTHANDEL",
        "━━━━━━━━━━━━━━━━",
        "MARKTDATEN:",
        *market_lines,
        "━━━━━━━━━━━━━━━━",
        "KAUF-/VERKAUFS-CHECK:",
        *decision_lines,
        "━━━━━━━━━━━━━━━━",
        f"Cash: {state['cash']:.2f} USD",
        f"Investiert (Einstand): {invested:.2f} USD",
        f"Positionswert: {market_value:.2f} USD",
        f"Gesamtwert: {total:.2f} USD",
        f"Realisierter Gewinn: {state['realized']:+.2f} USD",
        f"Offener Gewinn: {unrealized:+.2f} USD",
        f"Offene Positionen: {len(state['positions'])}",
        f"Trades insgesamt: {len(state['trades'])}",
        "━━━━━━━━━━━━━━━━",
        "PAPER TRADING - KEIN ECHTHANDEL"
    ]
    if messages:
        report.extend(["", "AUSGEFÜHRTE DEMO-TRADES:", *messages])
    if errors:
        report.extend(["", "DATENFEHLER:", *errors])

    report_text = "\n".join(report)
    print(report_text)
    state["updated"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    telegram(report_text)


if __name__ == "__main__":
    main()
