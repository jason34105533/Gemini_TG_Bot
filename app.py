import os
import logging
import traceback
import requests
import telebot
from flask import Flask, request, jsonify
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = "llama-3.3-70b-versatile"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
groq_client = Groq(api_key=GROQ_API_KEY)

# Per-user message history for multi-turn conversation
chat_histories: dict[int, list[dict]] = {}


def get_history(user_id: int) -> list[dict]:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]


def chat(user_id: int, user_text: str) -> str:
    history = get_history(user_id)
    history.append({"role": "user", "content": user_text})
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=history,
        max_tokens=2048,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return reply


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    log.info("Received /start from user %s", message.from_user.id)
    bot.reply_to(
        message,
        "Hi! I'm your AI assistant powered by Llama 3.3 70B via Groq.\n"
        "Just send me any message and I'll reply.\n\n"
        "Commands:\n"
        "/reset — Clear conversation history\n"
        "/start — Show this message",
    )


@bot.message_handler(commands=["reset"])
def handle_reset(message: telebot.types.Message):
    log.info("Received /reset from user %s", message.from_user.id)
    chat_histories.pop(message.from_user.id, None)
    bot.reply_to(message, "Conversation reset! Starting fresh.")


@bot.message_handler(func=lambda _: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()
    log.info("Message from user %s: %s", user_id, user_text[:80])

    bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = chat(user_id, user_text)
        log.info("Groq replied (%d chars)", len(reply))
        bot.reply_to(message, reply)
    except Exception:
        log.error("Error handling message:\n%s", traceback.format_exc())
        bot.reply_to(message, "Sorry, something went wrong. Check server logs.")


app = Flask(__name__)


@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    log.info("Webhook received: %s", body[:200])
    try:
        update = telebot.types.Update.de_json(body)
        bot.process_new_updates([update])
    except Exception:
        log.error("Error processing update:\n%s", traceback.format_exc())
    return "OK"


@app.route("/debug", methods=["GET"])
def debug():
    info: dict = {}

    # 1. Check Telegram webhook info
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo",
            timeout=5,
        )
        wh = r.json().get("result", {})
        info["webhook"] = {
            "url": wh.get("url"),
            "pending_updates": wh.get("pending_update_count"),
            "last_error": wh.get("last_error_message"),
            "last_error_time": wh.get("last_error_date"),
        }
    except Exception:
        info["webhook"] = {"error": traceback.format_exc()}

    # 2. Quick Groq smoke test
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=10,
        )
        reply = response.choices[0].message.content.strip()
        info["groq"] = {"status": "ok", "model": GROQ_MODEL, "reply": reply}
    except Exception:
        info["groq"] = {"status": "error", "model": GROQ_MODEL, "detail": traceback.format_exc()}

    # 3. Env var presence check
    info["env"] = {
        "TELEGRAM_BOT_TOKEN": "set" if TELEGRAM_BOT_TOKEN else "MISSING",
        "GROQ_API_KEY": "set" if GROQ_API_KEY else "MISSING",
    }

    log.info("Debug endpoint called: %s", info)
    return jsonify(info)


@app.route("/", methods=["GET"])
def health():
    return "Groq Telegram Bot is running."


if __name__ == "__main__":
    log.info("Running in polling mode...")
    bot.remove_webhook()
    bot.infinity_polling()
