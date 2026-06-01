# Telegram Bot + Groq AI — Setup Guide

## Step 1: Get a Groq API Key (Free, No Card)

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Click **"API Keys"** in the left sidebar → **"Create API Key"**
3. Give it a name, copy the key — you will use it as `GROQ_API_KEY`

---

## Step 2: Create a Telegram Bot via @BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts — choose a name (e.g. "My AI Bot") and a username ending in `bot` (e.g. `my_ai_bot`)
4. BotFather replies with your **bot token** — looks like `123456789:AAF...`
5. Copy it — you will use it as `TELEGRAM_BOT_TOKEN`

---

## Step 3: Deploy to Render (Free)

Render has a free tier that requires no credit card.

1. Push this folder to a GitHub repository:

   ```bash
   git add .
   git commit -m "Switch to Groq AI"
   git push
   ```

2. Go to [render.com](https://render.com) and sign in with GitHub (free account)
3. Click **"New"** → **"Web Service"** → select your repo
4. Fill in the settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance type:** Free
5. Under **"Environment Variables"**, add:

   ```env
   TELEGRAM_BOT_TOKEN = paste your token here
   GROQ_API_KEY       = paste your key here
   ```

6. Click **"Create Web Service"** — Render builds and starts the app
7. Copy your URL — looks like `https://your-app-name.onrender.com`

> **About the free tier spin-down:** Render pauses a free service after 15 minutes of no traffic.
> The first Telegram message after a long idle takes ~30 seconds to arrive while the server wakes up.
> Telegram retries automatically, so the message always comes through eventually.
> See the **Keep-Alive** section below if you want instant responses every time.

---

## Step 4: Register the Webhook with Telegram

Open this URL in your browser (replace both placeholders):

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-app-name>.onrender.com/<TELEGRAM_BOT_TOKEN>
```

You should get back `{"ok":true,"result":true}`. Telegram will now push every message to your server.

---

## Step 5: Chat with Your Bot

Search for your bot username on Telegram and tap **Start**. Send any message — the AI replies!

---

## Bot Commands

| Command        | Action                               |
| -------------- | ------------------------------------ |
| `/start`       | Show welcome message                 |
| `/reset`       | Clear your conversation history      |
| Any other text | Sent to Groq AI, reply comes back    |

---

## Keep-Alive (Optional, Free)

To prevent the Render spin-down, use [cron-job.org](https://cron-job.org) (free account) to ping your bot every 14 minutes:

- URL to ping: `https://your-app-name.onrender.com/`
- Schedule: every 14 minutes
- This keeps the server warm so responses are always instant.

---

## Local Testing (No Deployment Needed)

```bash
conda activate linebot_env
cp .env.example .env
# Fill in your keys in .env

python app.py
```

Running `python app.py` directly uses long-polling — no public URL required. Great for quick testing before you deploy.
