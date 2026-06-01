import os
import json
import logging
import traceback
import requests
import telebot
from flask import Flask, request, jsonify
from groq import Groq
from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = "deepseek-r1-distill-llama-70b"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "You are a smart, helpful AI assistant with access to a web search tool. "
    "Use web_search whenever the user asks about current events, news, prices, weather, "
    "sports scores, or anything that may have changed recently. "
    "Always reply in the same language the user writes in."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for up-to-date information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    }
]

# Per-user message history (user/assistant turns only)
chat_histories: dict[int, list[dict]] = {}


def get_history(user_id: int) -> list[dict]:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]


def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found."
        return "\n\n".join(
            f"{r['title']}\n{r['body']}\nURL: {r['href']}" for r in results
        )
    except Exception as e:
        return f"Search failed: {e}"


def chat(user_id: int, user_text: str) -> str:
    history = get_history(user_id)
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_text}]
    )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=4096,
    )
    msg = response.choices[0].message

    if msg.tool_calls:
        tool_results = []
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            log.info("Web search: %s", args["query"])
            result = web_search(args["query"])
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # Second call: give the model the search results
        second_messages = messages + [
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        ] + tool_results

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=second_messages,
            max_tokens=4096,
        )
        reply = response.choices[0].message.content
    else:
        reply = msg.content

    # Store only clean user/assistant turns in history
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    return reply


def send_reply(message: telebot.types.Message, text: str):
    """Split and send text that may exceed Telegram's 4096-char limit."""
    limit = 4096
    if len(text) <= limit:
        bot.reply_to(message, text)
        return
    # Send first chunk as reply, rest as follow-up messages
    bot.reply_to(message, text[:limit])
    for i in range(limit, len(text), limit):
        bot.send_message(message.chat.id, text[i:i + limit])


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    log.info("Received /start from user %s", message.from_user.id)
    bot.reply_to(
        message,
        "Hi! I'm your AI assistant.\n"
        "I can answer questions and search the web for current info.\n\n"
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
        log.info("Reply sent (%d chars)", len(reply))
        send_reply(message, reply)
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

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=10,
        )
        info["groq"] = {
            "status": "ok",
            "model": GROQ_MODEL,
            "reply": response.choices[0].message.content.strip(),
        }
    except Exception:
        info["groq"] = {"status": "error", "model": GROQ_MODEL, "detail": traceback.format_exc()}

    info["env"] = {
        "TELEGRAM_BOT_TOKEN": "set" if TELEGRAM_BOT_TOKEN else "MISSING",
        "GROQ_API_KEY": "set" if GROQ_API_KEY else "MISSING",
    }

    log.info("Debug endpoint called: %s", info)
    return jsonify(info)


@app.route("/", methods=["GET"])
def health():
    return "AI Telegram Bot is running."


if __name__ == "__main__":
    log.info("Running in polling mode...")
    bot.remove_webhook()
    bot.infinity_polling()
