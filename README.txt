PROPLAYERS COMMUNITY BOT
========================

Co bot umí
----------
- Herní a ping role přes tlačítkový panel (/setup-roles)
- Automatické dočasné hlasové místnosti (/setup-voice)
- Uvítání nových členů (/setup-welcome)
- Logy příchodů, odchodů a moderátorských zásahů (/setup-logs)
- Moderace: /clear, /timeout, /kick, /ban
- Informace: /bot-info

1) Vytvoření Discord aplikace
-----------------------------
1. Otevři https://discord.com/developers/applications
2. New Application -> pojmenuj bota.
3. V levém menu otevři Bot -> Add Bot.
4. V části Privileged Gateway Intents zapni:
   - SERVER MEMBERS INTENT
   - MESSAGE CONTENT INTENT
5. Reset Token / Copy Token. Token nikomu neposílej.

2) Pozvání na server
--------------------
V OAuth2 -> URL Generator zaškrtni:
- Scopes: bot, applications.commands
- Bot Permissions:
  Manage Roles, Manage Channels, View Channels, Send Messages,
  Embed Links, Read Message History, Manage Messages,
  Move Members, Connect, View Audit Log, Moderate Members,
  Kick Members, Ban Members

Otevři vygenerovaný odkaz a přidej bota na svůj server.
Nedávej mu Administrator.
DŮLEŽITÉ: roli bota přesuň v Server Settings -> Roles nad role,
které má bot spravovat (herní/ping role). Nedávej ji nad role administrátorů.

3) Instalace na Windows
-----------------------
Nainstaluj Python 3.11 nebo novější.
Rozbal ZIP do vlastní složky.
V terminálu v této složce spusť:

  py -m pip install -r requirements.txt

Zkopíruj .env.example na .env a doplň token a ID serveru.
ID serveru získáš po zapnutí Developer Mode v Discordu:
User Settings -> Advanced -> Developer Mode, pak pravým tlačítkem na server -> Copy Server ID.

Spuštění:
  py bot.py

Nech terminál běžet. Zavřením okna se bot vypne.

4) První nastavení na Discordu
------------------------------
Na serveru spusť jako správce:
  /setup-roles       vytvoří role a panel tlačítek
  /setup-voice       vytvoří lobby pro dočasné místnosti
  /setup-logs        vytvoří a nastaví #bot-logs
  /setup-welcome     nastaví kanál, ve kterém příkaz spustíš, jako uvítací

5) Trvalý provoz
----------------
Bot musí běžet na zařízení, které je stále zapnuté.
Doporučeno: Linux VPS (např. Debian/Ubuntu) jako systemd služba.
Na VPS nahraj obsah ZIP, vytvoř .env, nainstaluj závislosti a spusť.
Podrobný příklad systemd služby:

  sudo nano /etc/systemd/system/proplayers-bot.service

Vlož (uprav cestu a uživatele):
  [Unit]
  Description=ProPlayers Discord Bot
  After=network.target

  [Service]
  Type=simple
  User=BOTUSER
  WorkingDirectory=/opt/proplayers-bot
  ExecStart=/opt/proplayers-bot/venv/bin/python /opt/proplayers-bot/bot.py
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target

Pak:
  sudo systemctl daemon-reload
  sudo systemctl enable --now proplayers-bot
  sudo systemctl status proplayers-bot

Logy:
  journalctl -u proplayers-bot -f

Poznámky
--------
- config.json a bot.log se vytvoří automaticky.
- Zálohuj config.json; obsahuje ID vytvořených kanálů a rolí.
- Pokud bota přesuneš na jiný server, spusť setup příkazy znovu.
- Bot nevytváří automaticky všechny herní kategorie/kanály; stará se o role,
  hlasové místnosti, uvítání, logy a moderaci.
- Příkazy /kick a /ban používej pouze v souladu s pravidly serveru.
