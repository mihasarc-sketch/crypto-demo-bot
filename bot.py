import json
import os
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# CRYPTO DEMO BOT 3.1
# PAPER TRADING ONLY - NO REAL MONEY

COINS = ["BTC", "ETH", "SOL", "XRP"]
START_CASH = 1000.0
FEE = 0.001
RISK = 0.10
STOP_LOSS = 0.03
TAKE_PROFIT = 0.06
STATE = Path("state.json")

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoDemoBot/3.1"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def get_market(coin):
    symbol = coin + "USDT"
    data = api("https://api.binance.com/api/v3/klines?symbol=" + symbol + "&interval=1h&limit=100")
    closes = [float(row[4]) for row in data]
    price = closes[-1]
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(x, 0) for x in changes[-14:]]
    losses = [max(-x, 0) for x in changes[-14:]]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        rsi = 100 if avg_gain > 0 else 50
    else:
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
    return price, rsi

def load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            print("State file error. Starting safely.")
    return {
        "cash": START_CASH,
        "invested": 0.0,
        "realized": 0.0,
        "positions": {},
        "trades": 0
    }

def telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured.")
        return
    try:
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20).read()
        print("Telegram message sent.")
    except Exception as e:
        print("Telegram error:", e)

def main():
    state = load()
    print("=" * 35)
    print("CRYPTO DEMO BOT 3.1")
    print("SIMULATION ONLY - NO REAL TRADES")
    print("=" * 35)

    report = ["🤖 CRYPTO DEMO BOT 3.1"]
    report.append("Paper trading only - no real money")
    errors = []

    for coin in COINS:
        try:
            price, rsi = get_market(coin)
            position = state["positions"].get(coin)
            action = "HOLD"

            if position:
                entry = position["entry"]
                change = (price - entry) / entry
                if change <= -STOP_LOSS or change >= TAKE_PROFIT or rsi >= 70:
                    quantity = position["quantity"]
                    proceeds = quantity * price * (1 - FEE)
                    cost = position["cost"]
                    profit = proceeds - cost
                    state["cash"] += proceeds
                    state["realized"] += profit
                    del state["positions"][coin]
                    state["trades"] += 1
                    action = "SELL"
                    print(coin, "SELL:", round(profit, 2), "USD")
            elif rsi <= 30 and state["cash"] >= 10:
                investment = min(state["cash"], START_CASH * RISK)
                quantity = investment / (price * (1 + FEE))
                cost = investment
                state["cash"] -= cost
                state["positions"][coin] = {
                    "entry": price,
                    "quantity": quantity,
                    "cost": cost
                }
                state["trades"] += 1
                action = "BUY"
                print(coin, "BUY:", round(investment, 2), "USD")

            print(coin, round(price, 4), "USD | RSI:", round(rsi, 1), "|", action)
            report.append(f"{coin}: {price:.4f} USD | RSI {rsi:.1f} | {action}")

        except Exception as e:
            errors.append(coin + ": " + str(e))
            print("Market error", coin, e)

    invested = sum(p["cost"] for p in state["positions"].values())
    state["invested"] = invested
    state["updated"] = datetime.now(timezone.utc).isoformat()
    STATE.write_text(json.dumps(state, indent=2))

    report.extend([
        "----------------------",
        f"Cash: {state['cash']:.2f} USD",
        f"Invested: {invested:.2f} USD",
        f"Realized profit: {state['realized']:.2f} USD",
        f"Open positions: {len(state['positions'])}",
        f"Trades: {state['trades']}"
    ])
    if errors:
        report.append("Market errors: " + ", ".join(errors))
    report.append("Simulation - no real trades.")

    message = "\n".join(report)
    print(message)
    telegram(message)

if __name__ == "__main__":
    main()