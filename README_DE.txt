CRYPTO DEMO BOT 5.1

Zweck
Automatischer Paper-Trading-Test mit virtuellem Kontostand. Es werden KEINE echten Börsenorders gesendet und es werden keine privaten Börsenschlüssel benötigt.

Aktive Demo-Strategie
- Zeitrahmen: 4 Stunden; nur abgeschlossene Kraken-Kerzen werden ausgewertet.
- Bollinger-Bänder: 20 Kerzen, 2 Standardabweichungen.
- Einstieg: Kurs fällt frisch unter das untere Bollinger-Band und RSI(14) liegt bei höchstens 40.
- Ausstieg: Stop-Loss 5 %, Take-Profit 8 % oder Rückkehr zum Bollinger-Mittelband.
- Stop-Loss wird bei einer Kerze, die Stop und Ziel zugleich berührt, konservativ zuerst angenommen.
- Unterstützte Märkte: BTC, ETH, SOL, XRP, ADA, DOGE, LINK, AVAX, LTC, DOT sowie GOLD (XAU) und SILVER (XAG).

Virtuelles Risikomanagement und Ausführung
- Virtuelles Startkapital: 1.000 USD. Der bestehende Paper-Trading-Kontostand und die Trade-Historie werden bei der Umstellung beibehalten.
- Maximaler Einsatz je Kauf: 100 USD, zusätzlich begrenzt auf 20 % des verfügbaren virtuellen Cash.
- Simulierte Gebühr: 0,10 % je Kauf- und Verkaufsseite.
- Simulierte adverse Slippage: 0,05 % je Seite.
- Ein Coin wird pro neu abgeschlossener 4h-Kerze höchstens einmal ausgewertet; der Workflow kann weiterhin stündlich laufen, handelt aber nicht mehrfach dieselbe 4h-Kerze.
- Kraken OHLC-Daten sind öffentliche Marktdaten. Alle Käufe und Verkäufe sind ausschließlich Einträge im lokalen virtuellen Paper-Trading-Konto.

Gold und Silber
- Gold und Silber werden zusätzlich über öffentliche Kraken-Futures-Chartdaten (PF_XAUUSD und PF_XAGUSD) als Preisreferenz ausgewertet.
- Es werden keine Futures-Orders, keine Hebelpositionen und keine echten Orders eröffnet. Gold und Silber werden ausschließlich als ungehebelte virtuelle Paper-Trades im bestehenden Demo-Konto simuliert.
- Die gleiche Bollinger-/RSI-Strategie, 4h-Kerzen, Stop-Loss-/Take-Profit-Regeln, Gebühren- und Slippage-Annahmen werden angewendet.
- Die Strategie wurde für Gold und Silber noch nicht separat backgetestet; Ergebnisse sind experimentell.

Coin-Scanner
scanner.py liefert weiterhin eine separate Marktübersicht. Scanner-Kandidaten steuern keine Käufe.

Automatisierung
.github/workflows/hourly.yml startet den Scanner und danach den Demo-Bot stündlich sowie manuell über GitHub Actions. Der Bot verarbeitet nur neue abgeschlossene 4h-Kerzen. Ergebnisse werden in state.json und scan_results.json gespeichert.

Sicherheit und Einschränkungen
- PAPER TRADING ONLY: keine echten Börsenorders, keine privaten Börsen-API-Schlüssel und kein Echtgeldhandel.
- Die Strategie ist experimentell. Der 4h-Holdout-Test zeigte einen kleinen positiven Gesamtwert, der Tages-Test blieb negativ; das ist kein Nachweis dauerhafter Profitabilität.
- Gebühren und Slippage werden modelliert. OHLC-basierte Stop-/Take-Profit-Ausführung ist eine Näherung und kann reale Ausführung nicht exakt abbilden.
- Die bisherige Bot-Version 4.2 bleibt als bot_v4_2_backup.py erhalten.

Version 5.1 - Paper Trading only.
