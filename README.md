# DnD Session scheduler bot

Simple Telegram bot created for small friend group DnD session scheduling. For this bot was used SQLite and pyTelegramBotAPI (telebot).

    - Python automatically handles SQLite database. This file exists in the same directory with main.py and created if not already presented;
    - Bot have menu for invoking bot commands;
    - Bot focused on presenting a calendar view of preferred days for sessions, based on peoples choices;
    - Bot automatically takes BOT_TOKEN from .env file or from system environment variable.

# Usage
1. Clone repository into your suitable directory:
``` bash
git clone https://github.com/komardinec/DnDSchedulerBot.git
```

2. Install `Python`, `pip` and `pip-venv` (example for Debian-based distributive):
``` bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

3.1. Create Python virtual environment:
``` bash
cd /path/to/bot/directory
python3 -m venv .venv
```

3.2. Enter virtual environment:
``` bash
source .venv/bin/activate 
```

3.3. (Optional) Update pip:
``` bash
pip python -m pip install --upgrade pip
```

4. Install packages from `requirements.txt`:
``` bash
pip install -r requirements.txt
```

5. Create `.env` file with your `BOT_TOKEN`:
```bash
echo "BOT_TOKEN=your_token_string" > .env
chmod 640 .env
```

Now bot is ready to run, and you can use any comfort way to run it. But my recommendation is to use a systemd unit file from repository.

6. Move unit file to systemd directory:
``` bash
sudo mv dndschedulerbot.service /etc/systemd/system/
```

6.1. It can be optionally renamed, since name of `.service` file are name of systemd service:
```bash 
sudo mv /etc/systemd/system/dndschedulerbot.service /etc/systemd/system/pybot.service
```

7. In that file change path to `.py` file and working directory. You can continue configuring this unit file to follow your environment requirements:
``` bash 
nano /etc/systemd/system/dndschedulerbot.service
```
``` bash 
...
WorkingDirectory=/path/to/your/bot/dir/
ExecStart=/path/to/your/bot/dir/.venv/bin/python /path/to/your/bot/dir/DnDSchedulerBot/main.py --serve-in-foreground
...
```

8. Reload systemd daemon list:
``` bash
sudo systemctl daemon-reload
```

9. Start your bot service and enable auto start for it:
``` bash
sudo systemctl enable --now dndschedulerbot
```

