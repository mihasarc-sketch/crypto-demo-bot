
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
FEE = 0.001
STATE = Path("state.json")

def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {
        "cash": 1000.0,
        "positions": {},
        "trades": [],
        "last": {},
        "realized": 0.0
    }

def save(data):
    STATE.write_text(json.dumps(data, indent=2))

def api(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "DemoBot/3.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def notify(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": message
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data
    )
    urllib.request.urlopen(req, timeout=20).read()

def ema(values, period):
    result = values[0]
    k = 2 / (period + 1)
    for value in values[1:]:
        result = value * k + result * (1-k)
    return result

def rsi(values):
    changes = [values[i]-values[i-1]
               for i in range(len(values)-14, len(values))]
    gains = sum(max(x, 0) for x in changes)/14
    losses = sum(max(-x, 0) for x in changes)/14
    if losses == 0:
        return 100
    return 100 - 100/(1+gains/losses)

def run():
    data = load()

    for coin in COINS:
        try:
            url = (
                "https://api.binance.com/api/v3/klines?"
                + urllib.parse.urlencode({
                    "symbol": coin,
                    "interval": "1h",
                    "limit": 100
                })
            )
            rows = api(url)[:-1]
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
                    proceeds = qty * price * (1-FEE)
                    pnl = proceeds - qty*position["entry"]*(1+FEE)
                    data["cash"] += proceeds
                    data["realized"] += pnl
                    del data["positions"][coin]
                    data["trades"].append({
                        "coin": coin,
                        "side": "SELL",
                        "price": price,
                        "pnl": pnl
                    })
                    notify(
                        f"🔴 DEMO VERKAUF {coin}\n"
                        f"Kurs: {price:.4f}\n"
                        f"Ergebnis: {pnl:+.2f} USDT"
                    )

            elif fast > slow and 50 <= strength <= 70:
                budget = min(data["cash"], 100)
                if budget >= 10:
                    qty = budget*(1-FEE)/price
                    data["cash"] -= budget
                    data["positions"][coin] = {
                        "entry": price, "qty": qty
                    }
                    data["trades"].append({
                        "coin": coin,
                        "side": "BUY",
                        "price": price
                    })
                    notify(
                        f"🟢 DEMO KAUF {coin}\n"
                        f"Kurs: {price:.4f}\n"
                        f"Einsatz: {budget:.2f} USDT"
                    )

            data["last"][coin] = candle

        except Exception as error:
            print(coin, error)

    save(data)
    print("Bot-Lauf beendet:", datetime.now(timezone.utc))

if __name__ == "__main__":
    run()
