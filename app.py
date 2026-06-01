import os
import logging
import traceback
import requests
import telebot
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Per-user chat sessions (in-memory; resets on server restart)
chat_sessions: dict[int, genai.ChatSession] = {}


def get_chat_session(user_id: int) -> genai.ChatSession:
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    return chat_sessions[user_id]


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    log.info("Received /start from user %s", message.from_user.id)
    bot.reply_to(
        message,
        "Hi! I'm your Gemini AI assistant.\n"
        "Just send me any message and I'll reply using Google Gemini.\n\n"
        "Commands:\n"
        "/reset — Clear conversation history\n"
        "/start — Show this message",
    )


@bot.message_handler(commands=["reset"])
def handle_reset(message: telebot.types.Message):
    log.info("Received /reset from user %s", message.from_user.id)
    chat_sessions.pop(message.from_user.id, None)
    bot.reply_to(message, "Conversation reset! Starting fresh.")


@bot.message_handler(func=lambda _: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()
    log.info("Message from user %s: %s", user_id, user_text[:80])

    bot.send_chat_action(message.chat.id, "typing")

    try:
        chat = get_chat_session(user_id)
        response = chat.send_message(user_text)
        log.info("Gemini replied (%d chars)", len(response.text))
        bot.reply_to(message, response.text)
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
    """Returns webhook status and a live Gemini test — safe to share publicly."""
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

    # 2. Quick Gemini smoke test
    try:
        resp = model.generate_content("Reply with exactly: OK")
        info["gemini"] = {"status": "ok", "reply": resp.text.strip()}
    except Exception:
        info["gemini"] = {"status": "error", "detail": traceback.format_exc()}

    # 3. Env var presence (never log the actual values)
    info["env"] = {
        "TELEGRAM_BOT_TOKEN": "set" if TELEGRAM_BOT_TOKEN else "MISSING",
        "GEMINI_API_KEY": "set" if GEMINI_API_KEY else "MISSING",
    }

    log.info("Debug endpoint called: %s", info)
    return jsonify(info)


@app.route("/", methods=["GET"])
def health():
    return "Gemini Telegram Bot is running."


if __name__ == "__main__":
    log.info("Running in polling mode...")
    bot.remove_webhook()
    bot.infinity_polling()
