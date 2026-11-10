
import json
import urllib.request
from datetime import datetime, timezone

BASE = "https://api.kraken.com/0/public/"

def api(endpoint):
    request = urllib.request.Request(
        BASE + endpoint,
        headers={"User-Agent": "CryptoDemoBot/5.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode())
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data["result"]

def scan():
    pairs = api("AssetPairs")
    tickers = api("Ticker")

    results = []

    for key, info in pairs.items():
        name = info.get("wsname", "")
        status = info.get("status", "")

        if not name.endswith("/USD"):
            continue
        if status != "online":
            continue
        if key not in tickers:
            continue

        ticker = tickers[key]

        try:
            price = float(ticker["c"][0])
            volume = float(ticker["v"][1])
            bid = float(ticker["b"][0])
            ask = float(ticker["a"][0])

            if price <= 0 or bid <= 0 or ask <= 0:
                continue

            volume_usd = price * volume
            spread = ((ask - bid) / price) * 100

            if volume_usd < 100000:
                continue
            if spread > 1.0:
                continue

            results.append({
                "coin": name,
                "price_usd": round(price, 8),
                "volume_usd_24h": round(volume_usd, 2),
                "spread_percent": round(spread, 3)
            })

        except (KeyError, ValueError, TypeError):
            continue

    results.sort(
        key=lambda item: item["volume_usd_24h"],
        reverse=True
    )

    return results[:10]

if __name__ == "__main__":
    print("CRYPTO DEMO BOT 5.0 - COIN SCANNER")
    print("Nur Analyse - keine echten Orders")
    print("Zeit:", datetime.now(timezone.utc).isoformat())

    try:
        coins = scan()
        with open("scan_results.json", "w") as file:
            json.dump(coins, file, indent=2)
        for number, coin in enumerate(coins, 1):
            print(
                number,
                coin["coin"],
                "Preis:", coin["price_usd"],
                "Volumen:", coin["volume_usd_24h"],
                "Spread:", coin["spread_percent"], "%"
            )

        print("Gefundene Kandidaten:", len(coins))

    except Exception as error:
        print("Scanner-Fehler:", str(error))
