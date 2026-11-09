
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

# ==================================
# CRYPTO DEMO BOT 3.0
# SIMULATION ONLY - NO REAL TRADES
# ==================================

COINS = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD"
}

START_CASH = 1000.0
FEE = 0.001
RISK = 0.10
STOP_LOSS = -0.03
TAKE_PROFIT = 0.06

STATE = Path("state.json")


def load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            print("State-Datei fehlerhaft.")

    return {
        "cash": START_CASH,
        "positions": {},
        "trades": [],
        "last": {},
        "realized": 0.0
    }


def save(data):
    temp = Path("state.tmp")
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(STATE)


def notify(message):
    import os

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram nicht konfiguriert.")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message
        }).encode()

        req = urllib.request.Request(url, data=payload)
        urllib.request.urlopen(req, timeout=15).read()

    except Exception as error:
        print("Telegram Fehler:", error)


def get_prices(pair):
    url = (
        "https://api.kraken.com/0/public/OHLC"
        f"?pair={pair}&interval=60"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CryptoDemoBot/3.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.loads(response.read())

    if result.get("error"):
        raise ValueError(str(result["error"]))

    rows = next(
        value for key, value in result["result"].items()
        if key != "last"
    )

    return rows


def ema(values, period):
    if len(values) < period:
        raise ValueError("Zu wenige Kursdaten für EMA.")

    alpha = 2 / (period + 1)
    value = sum(values[:period]) / period

    for price in values[period:]:
        value = price * alpha + value * (1 - alpha)

    return value


def rsi(values, period=14):
    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def buy(data, coin, price, strength):
    budget = data["cash"] * RISK

    if budget < 10:
        return

    cost = budget
    qty = cost / (price * (1 + FEE))

    data["cash"] -= cost

    data["positions"][coin] = {
        "entry": price,
        "qty": qty,
        "cost": cost
    }

    data["trades"].append({
        "coin": coin,
        "side": "BUY",
        "price": price,
        "cost": cost,
        "time": datetime.now(timezone.utc).isoformat()
    })

    notify(
        f"🟢 DEMO KAUF {coin}\n"
        f"Kurs: {price:.4f} USD\n"
        f"Einsatz: {cost:.2f} USD\n"
        f"RSI: {strength:.1f}"
    )


def sell(data, coin, price, reason):
    position = data["positions"][coin]

    qty = position["qty"]
    proceeds = qty * price * (1 - FEE)
    pnl = proceeds - position["cost"]

    data["cash"] += proceeds
    data["realized"] += pnl

    del data["positions"][coin]

    data["trades"].append({
        "coin": coin,
        "side": "SELL",
        "price": price,
        "pnl": pnl,
        "reason": reason,
        "time": datetime.now(timezone.utc).isoformat()
    })

    notify(
        f"🔴 DEMO VERKAUF {coin}\n"
        f"Kurs: {price:.4f} USD\n"
        f"Grund: {reason}\n"
        f"Ergebnis: {pnl:.2f} USD"
    )


def run():
    data = load()

    print("================================")
    print("CRYPTO DEMO BOT 3.0")
    print("SIMULATION - KEIN ECHTHANDEL")
    print("================================")

    for coin, pair in COINS.items():
        try:
            rows = get_prices(pair)

            prices = [float(row[4]) for row in rows]
            candle = str(rows[-1][0])

            if data["last"].get(coin) == candle:
                print(f"{coin}: Kerze bereits verarbeitet.")
                continue

            price = prices[-1]
            fast = ema(prices[-60:], 20)
            slow = ema(prices[-80:], 50)
            strength = rsi(prices)

            position = data["positions"].get(coin)

            if position:
                change = (
                    price / position["entry"]
                ) - 1

                reason = None

                if change <= STOP_LOSS:
                    reason = "Stop-Loss"

                elif change >= TAKE_PROFIT:
                    reason = "Take-Profit"

                elif fast < slow:
                    reason = "Trendwechsel"

                if reason:
                    sell(data, coin, price, reason)

            elif (
                fast > slow
                and 35 <= strength <= 65
            ):
                buy(data, coin, price, strength)

            data["last"][coin] = candle

            print(
                f"{coin}: {price:.4f} USD | "
                f"RSI: {strength:.1f} | "
                f"Cash: {data['cash']:.2f} USD"
            )

        except Exception as error:
            print(f"{coin} Fehler: {error}")

    save(data)

    invested = sum(
        p["cost"] for p in data["positions"].values()
    )

    print("--------------------------------")
    print(f"Cash: {data['cash']:.2f} USD")
    print(f"Investiert: {invested:.2f} USD")
    print(f"Realisierter Gewinn: {data['realized']:.2f} USD")
    print(f"Offene Positionen: {len(data['positions'])}")
    print(f"Trades: {len(data['trades'])}")
    print("Bot-Lauf beendet:", datetime.now(timezone.utc).isoformat())

    notify(
        f"🤖 Crypto Demo Bot 3.0\n"
        f"Cash: {data['cash']:.2f} USD\n"
        f"Investiert: {invested:.2f} USD\n"
        f"Realisierter Gewinn: {data['realized']:.2f} USD"
    )


if __name__ == "__main__":
    run()
