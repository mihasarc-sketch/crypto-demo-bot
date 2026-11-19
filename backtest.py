import json
import math
import urllib.request
from datetime import datetime, timezone

# Historical strategy research only. This script NEVER submits exchange orders.
BASE = "https://api.kraken.com/0/public/"
# Kraken public USD markets. DOGE has an alternate Kraken market symbol fallback.
PAIRS = {
    "BTC": ["XBTUSD"], "ETH": ["ETHUSD"], "SOL": ["SOLUSD"], "XRP": ["XRPUSD"],
    "ADA": ["ADAUSD"], "DOGE": ["DOGEUSD", "XDGUSD"], "LINK": ["LINKUSD"],
    "AVAX": ["AVAXUSD"], "LTC": ["LTCUSD"], "DOT": ["DOTUSD"]
}
FEE = 0.001
START_CASH_PER_COIN = 250.0
MAX_BUY = 100.0
CANDLE_LIMIT = 720


def fetch_ohlc(pair_options, interval=60):
    if isinstance(pair_options, str):
        pair_options = [pair_options]
    errors = []
    for pair in pair_options:
        try:
            url = f"{BASE}OHLC?pair={pair}&interval={interval}"
            request = urllib.request.Request(url, headers={"User-Agent": "CryptoDemoBacktest/2.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode())
            if payload.get("error"):
                errors.append(f"{pair}: {payload['error']}")
                continue
            result = payload["result"]
            key = next(key for key in result if key != "last")
            rows = result[key][:-1]
            if len(rows) < 100:
                errors.append(f"{pair}: only {len(rows)} completed candles returned")
                continue
            return [{"time": int(float(row[0])), "open": float(row[1]), "high": float(row[2]),
                     "low": float(row[3]), "close": float(row[4])}
                    for row in rows[-CANDLE_LIMIT:]]
        except Exception as error:
            errors.append(f"{pair}: {error}")
    raise RuntimeError("; ".join(errors))

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


def signals_at(closes, index, config):
    kind = config["kind"]
    strength = rsi(closes)
    if kind in ("ema", "ema_cross"):
        fast_period = config["fast"]
        slow_period = config["slow"]
        fast = ema(closes[-max(100, slow_period * 4):], fast_period)
        slow = ema(closes[-max(100, slow_period * 4):], slow_period)
        prev_closes = closes[:-1]
        prev_fast = ema(prev_closes[-max(100, slow_period * 4):], fast_period)
        prev_slow = ema(prev_closes[-max(100, slow_period * 4):], slow_period)
        bull = fast > slow
        prev_bull = prev_fast > prev_slow
        if kind == "ema_cross":
            return (bull and not prev_bull and strength >= config["rsi_min"],
                    (not bull and prev_bull), strength)
        return (bull and prev_bull and config["rsi_min"] <= strength <= config["rsi_max"],
                (not bull and not prev_bull), strength)

    if kind == "breakout":
        lookback = config["lookback"]
        prior_high = max(closes[-lookback-1:-1])
        prior_low = min(closes[-config["exit_lookback"]-1:-1])
        return closes[-1] > prior_high, closes[-1] < prior_low, strength

    if kind == "bollinger":
        window = closes[-config["period"]:]
        mean = sum(window) / len(window)
        deviation = math.sqrt(sum((x - mean) ** 2 for x in window) / len(window))
        lower = mean - config["deviations"] * deviation
        previous_window = closes[-config["period"]-1:-1]
        previous_mean = sum(previous_window) / len(previous_window)
        previous_dev = math.sqrt(sum((x - previous_mean) ** 2 for x in previous_window) / len(previous_window))
        previous_lower = previous_mean - config["deviations"] * previous_dev
        enter = closes[-2] >= previous_lower and closes[-1] < lower and strength <= config["rsi_max"]
        exit_signal = closes[-1] >= mean
        return enter, exit_signal, strength

    raise ValueError(f"Unknown strategy: {kind}")


def warmup_bars(config):
    if config["kind"] in ("ema", "ema_cross"):
        return max(105, config["slow"] * 4 + 2)
    if config["kind"] == "bollinger":
        return max(105, config["period"] + 2)
    if config["kind"] == "breakout":
        return max(105, config["lookback"] + 2, config["exit_lookback"] + 2)
    return 105


def simulate(candles, config):
    cash = START_CASH_PER_COIN
    position = None
    trades = []
    closes = []

    for index, candle in enumerate(candles):
        closes.append(candle["close"])
        if index < 105 or index + 1 >= len(candles):
            continue
        enter, exit_signal, strength = signals_at(closes, index, config)
        next_open = candles[index + 1]["open"]

        if position:
            stop_price = position["entry"] * (1 - config["stop"])
            target_price = position["entry"] * (1 + config["target"])
            # Conservative OHLC assumption: stop wins if stop and target hit in same candle.
            if candle["low"] <= stop_price:
                exit_price = candle["open"] if candle["open"] <= stop_price else stop_price
                reason = "Stop-Loss"
            elif candle["high"] >= target_price:
                exit_price = candle["open"] if candle["open"] >= target_price else target_price
                reason = "Take-Profit"
            elif exit_signal:
                exit_price, reason = next_open, "Strategy exit"
            else:
                continue
            proceeds = position["quantity"] * exit_price * (1 - FEE)
            profit = proceeds - position["cost"]
            cash += proceeds
            trades.append({"profit": round(profit, 6), "reason": reason})
            position = None
            continue

        if not enter:
            continue
        budget = min(MAX_BUY, cash * 0.20)
        if budget < 10:
            continue
        quantity = budget * (1 - FEE) / next_open
        cash -= budget
        position = {"entry": next_open, "quantity": quantity, "cost": budget}

    if position:
        exit_price = candles[-1]["close"]
        proceeds = position["quantity"] * exit_price * (1 - FEE)
        profit = proceeds - position["cost"]
        cash += proceeds
        trades.append({"profit": round(profit, 6), "reason": "End of test"})

    wins = [trade["profit"] for trade in trades if trade["profit"] > 0]
    losses = [trade["profit"] for trade in trades if trade["profit"] < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "ending_equity": round(cash, 2),
        "net_profit": round(cash - START_CASH_PER_COIN, 2),
        "closed_trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate_percent": round(100 * len(wins) / len(trades), 1) if trades else 0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "gross_profit": round(gross_profit, 2), "gross_loss": round(gross_loss, 2)
    }


def main():
    configs = {
        "current_v4_2": {"kind":"ema","fast":9,"slow":21,"rsi_min":52,"rsi_max":65,"stop":0.03,"target":0.06},
        "ema_trend_20_50": {"kind":"ema","fast":20,"slow":50,"rsi_min":50,"rsi_max":68,"stop":0.03,"target":0.06},
        "ema_12_26_crossover": {"kind":"ema_cross","fast":12,"slow":26,"rsi_min":50,"rsi_max":100,"stop":0.03,"target":0.06},
        "donchian_breakout_20_10": {"kind":"breakout","lookback":20,"exit_lookback":10,"stop":0.04,"target":0.08},
        "bollinger_rsi_reversal": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":35,"stop":0.04,"target":0.06}
    }
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notice": "Research only; no live orders. Kraken OHLC is limited to 720 recent candles per interval. Hourly broad comparison and daily ADA/XRP parameter research are separate. Daily research uses a chronological 70/30 train/test split; the test segment includes prior candles only for indicator warm-up. Fees included; OHLC stop/target assumptions are approximate.",
        "candles_per_coin": {}, "results": {}, "focused_daily_ada_xrp": {}
    }
    datasets = {}
    for coin, pair in PAIRS.items():
        try:
            datasets[coin] = fetch_ohlc(pair)
            output["candles_per_coin"][coin] = len(datasets[coin])
        except Exception as error:
            output["candles_per_coin"][coin] = {"error": str(error)}

    for name, config in configs.items():
        coin_results = {coin: simulate(candles, config) for coin, candles in datasets.items()}
        output["results"][name] = coin_results
        output["results"][name]["TOTAL_EQUAL_ALLOCATION"] = {
            "starting_equity": round(START_CASH_PER_COIN * len(datasets), 2),
            "ending_equity": round(sum(item["ending_equity"] for item in coin_results.values()), 2),
            "net_profit": round(sum(item["net_profit"] for item in coin_results.values()), 2),
            "closed_trades": sum(item["closed_trades"] for item in coin_results.values()),
            "wins": sum(item["wins"] for item in coin_results.values()),
            "losses": sum(item["losses"] for item in coin_results.values())
        }

    # Focused, longer-history research for ADA and XRP on daily candles.
    # Parameter variants are compared on the first 70%; the final 30% is held out.
    daily_configs = {
        "bollinger_rsi30_sl4_tp6": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":30,"stop":0.04,"target":0.06},
        "bollinger_rsi35_sl4_tp6": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":35,"stop":0.04,"target":0.06},
        "bollinger_rsi40_sl4_tp6": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":40,"stop":0.04,"target":0.06},
        "bollinger_rsi35_sl5_tp8": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":35,"stop":0.05,"target":0.08},
        "bollinger_rsi40_sl5_tp8": {"kind":"bollinger","period":20,"deviations":2.0,"rsi_max":40,"stop":0.05,"target":0.08},
        "ema20_50_rsi45_sl3_tp6": {"kind":"ema","fast":20,"slow":50,"rsi_min":45,"rsi_max":70,"stop":0.03,"target":0.06},
        "ema20_50_rsi50_sl3_tp6": {"kind":"ema","fast":20,"slow":50,"rsi_min":50,"rsi_max":70,"stop":0.03,"target":0.06},
        "ema20_50_rsi45_sl4_tp8": {"kind":"ema","fast":20,"slow":50,"rsi_min":45,"rsi_max":70,"stop":0.04,"target":0.08},
        "ema20_50_rsi50_sl4_tp8": {"kind":"ema","fast":20,"slow":50,"rsi_min":50,"rsi_max":70,"stop":0.04,"target":0.08}
    }
    for coin in ("ADA", "XRP"):
        try:
            daily = fetch_ohlc(PAIRS[coin], interval=1440)
            split = int(len(daily) * 0.70)
            coin_output = {
                "candles": len(daily),
                "approx_history_days": len(daily),
                "train_candles": split,
                "test_candles": len(daily) - split,
                "split": "chronological 70% train / 30% holdout",
                "strategies": {}
            }
            for name, config in daily_configs.items():
                warmup = warmup_bars(config)
                train_data = daily[:split]
                test_data = daily[max(0, split - warmup):]
                train_result = simulate(train_data, config)
                test_result = simulate(test_data, config)
                coin_output["strategies"][name] = {
                    "train": train_result,
                    "holdout": test_result
                }
            output["focused_daily_ada_xrp"][coin] = coin_output
        except Exception as error:
            output["focused_daily_ada_xrp"][coin] = {"error": str(error)}

    with open("backtest_results.json", "w") as file:
        json.dump(output, file, indent=2)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
