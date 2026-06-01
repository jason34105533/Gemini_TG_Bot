import os
import telebot
from flask import Flask, request
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Per-user chat sessions (in-memory; resets on server restart)
chat_sessions: dict[int, genai.ChatSession] = {}


def get_chat_session(user_id: int) -> genai.ChatSession:
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    return chat_sessions[user_id]


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
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
    chat_sessions.pop(message.from_user.id, None)
    bot.reply_to(message, "Conversation reset! Starting fresh.")


@bot.message_handler(func=lambda _: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()

    # Show typing indicator while Gemini thinks
    bot.send_chat_action(message.chat.id, "typing")

    try:
        chat = get_chat_session(user_id)
        response = chat.send_message(user_text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Sorry, something went wrong: {e}")


app = Flask(__name__)


@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data(as_text=True))
    bot.process_new_updates([update])
    return "OK"


@app.route("/", methods=["GET"])
def health():
    return "Gemini Telegram Bot is running."


if __name__ == "__main__":
    # Local polling mode (no webhook needed)
    print("Running in polling mode...")
    bot.remove_webhook()
    bot.infinity_polling()
