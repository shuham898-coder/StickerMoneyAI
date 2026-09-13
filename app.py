import os
from flask import Flask, request
import requests

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )


@app.route("/", methods=["GET"])
def home():
    return "StickerMoneyAI работает! 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}

    message = update.get("message")
    if not message:
        return "OK", 200

    chat_id = message["chat"]["id"]

    if message.get("text") == "/start":
        send_message(
            chat_id,
            "Привет! 👋\n\n"
            "Я StickerMoneyAI 🤖\n"
            "Пришли мне свою фотографию 📸\n\n"
            "Скоро я превращу её в персональный стикер ✨"
        )

    elif message.get("photo"):
        send_message(
            chat_id,
            "Фото получил! 📸✅\n\n"
            "Отлично. Следующий этап — создание твоего стикера 😎"
        )

    else:
        send_message(chat_id, "Пришли мне фотографию 📸")

    return "OK", 200
