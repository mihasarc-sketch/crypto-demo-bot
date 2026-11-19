CRYPTO DEMO BOT 4.2

Zweck
Automatischer Paper-Trading-Test mit virtuellen Kontoständen.
Es werden KEINE echten Börsenorders gesendet und es werden keine privaten Börsenschlüssel benötigt.

Marktdaten
Kraken Public API, abgeschlossene 1-Stunden-Kerzen.
Gehandelte Testpaare: BTC/USD, ETH/USD, SOL/USD und XRP/USD.

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