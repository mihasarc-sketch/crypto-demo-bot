import json
import urllib.request
from datetime import datetime, timezone

# Historical research only. This script NEVER submits exchange orders.
BASE = "https://api.kraken.com/0/public/"
PAIRS = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD", "XRP": "XRPUSD"}
FEE = 0.001
START_CASH_PER_COIN = 250.0
MAX_BUY = 100.0
CANDLE_LIMIT = 720


def fetch_ohlc(pair):
    url = f"{BASE}OHLC?pair={pair}&interval=60"
    request = urllib.request.Request(url, headers={"User-Agent": "CryptoDemoBacktest/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    result = payload["result"]
    key = next(key for key in result if key != "last")
    rows = result[key][:-1]  # exclude currently forming candle
    if len(rows) < 100:
        raise RuntimeError(f"Only {len(rows)} completed candles returned")
    return [{
        "time": int(float(row[0])),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4])
    } for row in rows[-CANDLE_LIMIT:]]


def ema(values, period):
    alpha = 2.0 / (period + 1)
    value = values[0]
    for price in values[1:]:
        value = alpha * price + (1 - alpha) * value
    return value


def rsi(values, period=14):
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = changes[-period:]
    gains = sum(max(change, 0.0) for change in recent) / period
    losses = sum(max(-change, 0.0) for change in recent) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def simulate(candles, config):
    cash = START_CASH_PER_COIN
    position = None
    trades = []
    closes = []

    for index, candle in enumerate(candles):
        closes.append(candle["close"])
        if index < 55 or index + 1 >= len(candles):
            continue

        window = closes[-50:]
        fast = ema(window, config["fast"])
        slow = ema(window, config["slow"])
        strength = rsi(closes)
        bullish = fast > slow
        previous_bullish = False
        if index >= 1:
            previous_window = closes[-51:-1]
            previous_bullish = ema(previous_window, config["fast"]) > ema(previous_window, config["slow"])

        next_open = candles[index + 1]["open"]

        if position:
            stop_price = position["entry"] * (1 - config["stop"])
            target_price = position["entry"] * (1 + config["target"])
            # Conservative intrabar handling: if stop and target both touched, assume stop first.
            if candle["low"] <= stop_price:
                # A stop executes inside this candle; use its open for a gap below the stop.
                exit_price = candle["open"] if candle["open"] <= stop_price else stop_price
                reason = "Stop-Loss"
            elif candle["high"] >= target_price:
                # A target limit fills at the target, or better if the candle gaps above it.
                exit_price = candle["open"] if candle["open"] >= target_price else target_price
                reason = "Take-Profit"
            elif config["exit_confirm"] and not bullish and not previous_bullish:
                exit_price, reason = next_open, "EMA exit"
            else:
                continue

            proceeds = position["quantity"] * exit_price * (1 - FEE)
            profit = proceeds - position["cost"]
            cash += proceeds
            trades.append({"profit": round(profit, 6), "reason": reason})
            position = None
            continue

        confirmed = bullish and previous_bullish
        if config["entry_confirm"] and not confirmed:
            continue
        if not config["entry_confirm"] and not bullish:
            continue
        if not (config["rsi_min"] <= strength <= config["rsi_max"]):
            continue

        budget = min(MAX_BUY, cash * 0.20)
        if budget < 10:
            continue
        quantity = budget * (1 - FEE) / next_open
        cash -= budget
        position = {"entry": next_open, "quantity": quantity, "cost": budget}

    # Close any remaining test position at the last close so equity is comparable.
    if position:
        exit_price = candles[-1]["close"]
        proceeds = position["quantity"] * exit_price * (1 - FEE)
        profit = proceeds - position["cost"]
        cash += proceeds
        trades.append({"profit": round(profit, 6), "reason": "End of test"})
    wins = [trade["profit"] for trade in trades if trade["profit"] > 0]
    losses = [trade["profit"] for trade in trades if trade["profit"] < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "ending_equity": round(cash, 2),
        "net_profit": round(cash - START_CASH_PER_COIN, 2),
        "closed_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_percent": round(100 * len(wins) / len(trades), 1) if trades else 0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2)
    }


def main():
    configs = {
        "current_v4_2": {
            "fast": 9, "slow": 21, "entry_confirm": True,
            "exit_confirm": True, "rsi_min": 52, "rsi_max": 65,
            "stop": 0.03, "target": 0.06
        },
        "wider_rsi": {
            "fast": 9, "slow": 21, "entry_confirm": True,
            "exit_confirm": True, "rsi_min": 50, "rsi_max": 68,
            "stop": 0.03, "target": 0.06
        },
        "ema_trend_20_50": {
            "fast": 20, "slow": 50, "entry_confirm": True,
            "exit_confirm": True, "rsi_min": 50, "rsi_max": 68,
            "stop": 0.03, "target": 0.06
        }
    }
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notice": "Historical research only; no live orders. Kraken public OHLC is limited to recent history. Signals use candle close and execute at next candle open; fees included.",
        "candles_per_coin": {},
        "results": {}
    }
    datasets = {}
    for coin, pair in PAIRS.items():
        try:
            datasets[coin] = fetch_ohlc(pair)
            output["candles_per_coin"][coin] = len(datasets[coin])
        except Exception as error:
            output["candles_per_coin"][coin] = {"error": str(error)}

    for name, config in configs.items():
        coin_results = {}
        for coin, candles in datasets.items():
            coin_results[coin] = simulate(candles, config)
        output["results"][name] = coin_results
        output["results"][name]["TOTAL_EQUAL_ALLOCATION"] = {
            "starting_equity": round(START_CASH_PER_COIN * len(datasets), 2),
            "ending_equity": round(sum(item["ending_equity"] for item in coin_results.values()), 2),
            "net_profit": round(sum(item["net_profit"] for item in coin_results.values()), 2),
            "closed_trades": sum(item["closed_trades"] for item in coin_results.values()),
            "wins": sum(item["wins"] for item in coin_results.values()),
            "losses": sum(item["losses"] for item in coin_results.values())
        }

    with open("backtest_results.json", "w") as file:
        json.dump(output, file, indent=2)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
