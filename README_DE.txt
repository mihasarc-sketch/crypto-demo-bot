CRYPTO DEMO BOT 4.2

Zweck
Automatischer Paper-Trading-Test mit virtuellen Kontoständen.
Es werden KEINE echten Börsenorders gesendet und es werden keine privaten Börsenschlüssel benötigt.

Marktdaten
Kraken Public API, abgeschlossene 1-Stunden-Kerzen.
Historische Backtest-Testpaare (Kraken USD-Märkte): BTC, ETH, SOL, XRP, ADA, DOGE, LINK, AVAX, LTC und DOT. Der Backtest verwendet je Coin bis zu 720 abgeschlossene Stundenkerzen. Nicht verfügbare Märkte werden als Fehler ausgewiesen und aus der Gesamtsumme ausgeschlossen.

Strategie (experimentell, nicht als profitabel nachgewiesen)
- EMA 9 und EMA 21 werden aus den letzten 50 abgeschlossenen Stundenkerzen berechnet.
- Kauf nur bei zwei aufeinanderfolgenden abgeschlossenen Kerzen mit EMA 9 über EMA 21.
- RSI-Kaufbereich: 52 bis 65.
- Ein EMA-Verkaufssignal wird erst nach zwei aufeinanderfolgenden bearishen Kerzen ausgeführt.
- Stop-Loss: 3 %; Take-Profit: 6 %; geprüft auf abgeschlossenen Stundenkerzen.

Virtuelles Risikomanagement
- Startkapital: 1.000 USD (virtuell).
- Maximaler Einsatz je Kauf: 100 USD, zusätzlich begrenzt auf 20 % des verfügbaren Cash.
- Simulierte Gebühr: 0,1 % beim Kauf und Verkauf.

Coin-Scanner
scanner.py listet liquide USD-Märkte nach 24h-Volumen und Spread.
Die Scanner-Kandidaten sind derzeit nur Information für das Dashboard und steuern KEINE Käufe im Bot.

Automatisierung
.github/workflows/hourly.yml startet den Scanner und danach den Demo-Bot stündlich sowie manuell über GitHub Actions.
Die Ergebnisse werden in state.json und scan_results.json gespeichert.

Wichtige Einschränkungen
- Die Strategie ist experimentell und kann Verluste erzeugen.
- Die Trefferquote allein beweist keine Profitabilität; Gebühren, Gewinn/Verlust-Verhältnis und ausreichend viele Tests sind wichtig.
- Stop-Loss und Take-Profit werden anhand abgeschlossener Stundenkerzen geprüft; schnelle Kursbewegungen innerhalb einer Stunde können daher anders verlaufen.
- Erst Backtests und längere Paper-Trading-Beobachtung durchführen. Kein Echtgeldbetrieb.

Version 4.2 - Paper Trading only.

Weitere historische Strategietests
Der manuelle Workflow Crypto Demo Backtest vergleicht zusätzlich:
- EMA 12/26 Crossover
- Donchian-Ausbruch 20/10
- Bollinger-Band-Umkehr mit RSI unter/gleich 35

Der Backtest umfasst zehn Coins: BTC, ETH, SOL, XRP, ADA, DOGE, LINK, AVAX, LTC und DOT. Diese Erweiterung betrifft ausschließlich die historische Auswertung. Der laufende Demo-Bot handelt weiterhin nur seine bisher konfigurierten Coins.
Diese Varianten sind reine Forschungs-Backtests und werden nicht automatisch vom laufenden Demo-Bot gehandelt.

Vertiefte ADA-/XRP-Forschung
- Zusätzlich werden ADA und XRP mit täglichen Kraken-Kerzen (bis zu 720 Tage) untersucht.
- Neun Varianten aus Bollinger/RSI und EMA 20/50 werden verglichen.
- Chronologischer Split: 70 % Trainingsdaten und 30 % unangetasteter Holdout-Test.
- Die zusätzlichen Tests dienen nur der Forschung. Sie ändern weder Coins noch Strategie des laufenden Paper-Trading-Bots.


Erweiterter Bollinger-Robustheitstest
- Die drei besten Bollinger/RSI-Kandidaten werden zusätzlich über alle zehn unterstützten Coins getestet.
- Zeitrahmen: 4 Stunden und 1 Tag, jeweils bis zu 720 abgeschlossene Kerzen pro Markt.
- Chronologischer Split: 70 % Training und 30 % Holdout-Test; Indikator-Warmup aus früheren Kerzen wird nicht gehandelt.
- Kostenmodell: 0,1 % simulierte Gebühr je Seite plus 0,05 % konservativer Slippage je Seite.
- Stop-/Take-Profit-Ausführung bleibt eine Näherung auf Basis von OHLC-Kerzen. Ergebnisse sind keine Garantie für zukünftige Renditen.
- Ausschließlich historische Forschung; der laufende Bot bleibt unverändert und handelt weiterhin nur virtuell.
