
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

COINS = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD"
}

FEE = 0.001
STATE = Path("state.json")
START_CASH = 1000.0


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())

    return {
        "cash": START_CASH,
        "positions": {},
        "trades": [],
        "last": {},
        "realized": 0.0
    }


def save(data):
    STATE.write_text(json.dumps(data, indent=2))


def api(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CryptoDemoBot/3.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def notify(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat:
        print("Telegram nicht konfiguriert")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": message
    }).encode()

    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as response:
        response.read()


def ema(values, period):
    result = values[0]
    k = 2 / (period + 1)

    for value in values[1:]:
        result = value * k + result * (1 - k)

    return result


def rsi(values):
    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    recent = changes[-14:]
    gains = sum(max(x, 0) for x in recent) / 14
    losses = sum(max(-x, 0) for x in recent) / 14

    if losses == 0:
        return 100

    return 100 - 100 / (1 + gains / losses)


def run():
    data = load()

    for coin, pair in COINS.items():
        try:
            params = urllib.parse.urlencode({
                "pair": pair,
                "interval": 60
            })

            url = (
                "https://api.kraken.com/0/public/OHLC?"
                + params
            )

            result = api(url)

            if result.get("error"):
                raise Exception(str(result["error"]))

            candles = result["result"]
            key = next(k for k in candles if k != "last")
            rows = candles[key][:-1]

            if len(rows) < 60:
                raise Exception("Zu wenig Kursdaten")

            prices = [float(x[4]) for x in rows]
            candle = str(rows[-1][0])

            if data["last"].get(coin) == candle:
                continue

            price = prices[-1]
            fast = ema(prices[-60:], 20)
            slow = ema(prices[-80:], 50)
            strength = rsi(prices)

            position = data["positions"].get(coin)

            if position:
                change = price / position["entry"] - 1
                reason = None

                if change <= -0.03:
                    reason = "Stop-Loss"
                elif change >= 0.06:
                    reason = "Take-Profit"
                elif fast < slow:
                    reason = "Trendwechsel"

                if reason:
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
                        "reason": reason
                    })

                    notify(
                        f"🔴 DEMO VERKAUF {coin}\n"
                        f"Kurs: {price:.4f}\n"
                        f"Grund: {reason}\n"
                        f"Ergebnis: {pnl:+.2f} USD"
                    )

            elif fast > slow and 50 <= strength <= 70:
                budget = min(data["cash"], 100)

                if budget >= 10:
                    qty = budget * (1 - FEE) / price
                    cost = budget

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
                        "cost": cost
                    })

                    notify(
                        f"🟢 DEMO KAUF {coin}\n"
                        f"Kurs: {price:.4f}\n"
                        f"Einsatz: {budget:.2f} USD\n"
                        f"RSI: {strength:.1f}"
                    )

            data["last"][coin] = candle
            print(
                f"{coin}: {price:.4f} | "
                f"RSI: {strength:.1f} | "
                f"Cash: {data['cash']:.2f}"
            )

        except Exception as error:
            print(f"{coin} Fehler: {error}")

        save(data)

    notify("Telegram Test erfolgreich!")

    print(
        "Bot-Lauf beendet:",
        datetime.now(timezone.utc).isoformat()
    )

if __name__ == "__