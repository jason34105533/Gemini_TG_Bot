# Telegram Bot + Gemini AI — Setup Guide

## Step 1: Get a Gemini API Key

1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click **"Get API key"** → **"Create API key"**
4. Copy the key — you'll use it as `GEMINI_API_KEY`

---

## Step 2: Create a Telegram Bot via @BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts — choose a name (e.g. "My Gemini Bot") and a username ending in `bot` (e.g. `my_gemini_bot`)
4. BotFather replies with your **bot token** — looks like `123456789:AAF...`
5. Copy it — you'll use it as `TELEGRAM_BOT_TOKEN`

---

## Step 3: Deploy to Railway

1. Push this folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial Telegram + Gemini bot"
   # Create a repo on github.com, then:
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. Go to https://railway.app and sign in with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"** → select your repo
4. Railway detects the `Procfile` and deploys automatically

5. Add environment variables in Railway:
   - Go to your project → **"Variables"** tab
   - Add these two:
     ```
     TELEGRAM_BOT_TOKEN = <your value>
     GEMINI_API_KEY     = <your value>
     ```

6. Copy your Railway deployment URL — looks like `https://your-app-name.up.railway.app`

---

## Step 4: Register the Webhook with Telegram

Open this URL in your browser (replace the two placeholders):

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-app-name>.up.railway.app/<TELEGRAM_BOT_TOKEN>
```

You should see `{"ok":true,"result":true}`. That's it — Telegram will now forward messages to your server.

---

## Step 5: Chat with Your Bot

- Search for your bot's username on Telegram and tap **Start**
- Send any message — Gemini replies!
- The bot remembers your conversation context per session.

---

## Bot Commands

| Command / Message | Action |
| ----------------- | ------ |
| `/start` | Show welcome message |
| `/reset` | Clear your conversation history with Gemini |
| Any other text | Forwarded to Gemini, AI reply sent back |

---

## Local Testing (No Deployment Needed)

```bash
# Activate your conda environment
conda activate linebot_env

# Create .env from template
cp .env.example .env
# Fill in your keys in .env

# Run in polling mode (no webhook needed locally)
python app.py
```

When run directly (`python app.py`), the bot uses long-polling instead of webhooks — no public URL required. Perfect for testing on airplane wifi too.
