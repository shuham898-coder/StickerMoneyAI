import os
import io
import requests

from flask import Flask, request
from PIL import Image, ImageOps
from rembg import remove

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )


def download_telegram_photo(file_id):
    r = requests.get(
        f"{TELEGRAM_API}/getFile",
        params={"file_id": file_id},
        timeout=30,
    )
    r.raise_for_status()

    file_path = r.json()["result"]["file_path"]

    photo = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_path}",
        timeout=30,
    )
    photo.raise_for_status()

    return photo.content


def make_sticker(photo_bytes):
    # Убираем фон с фотографии
    no_background = remove(photo_bytes)

    image = Image.open(io.BytesIO(no_background)).convert("RGBA")

    # Обрезаем пустое прозрачное пространство
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    # Уменьшаем человека, чтобы вокруг осталось немного места
    image.thumbnail((470, 470), Image.Resampling.LANCZOS)

    # Прозрачный холст Telegram 512x512
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))

    x = (512 - image.width) // 2
    y = (512 - image.height) // 2

    canvas.alpha_composite(image, (x, y))

    output = io.BytesIO()

    # WEBP подходит для обычного Telegram-стикера
    canvas.save(
        output,
        format="WEBP",
        lossless=False,
        quality=85,
        method=6,
    )

    output.seek(0)
    return output


def send_sticker(chat_id, sticker):
    sticker.seek(0)

    response = requests.post(
        f"{TELEGRAM_API}/sendSticker",
        data={"chat_id": chat_id},
        files={
            "sticker": (
                "sticker.webp",
                sticker,
                "image/webp",
            )
        },
        timeout=60,
    )

    return response.json()


@app.route("/", methods=["GET"])
def home():
    return "StickerMoneyAI работает! 🚀", 200


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    base_url = request.host_url.rstrip("/")

    response = requests.get(
        f"{TELEGRAM_API}/setWebhook",
        params={"url": f"{base_url}/webhook"},
        timeout=30,
    )

    return response.json()


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
            "Я StickerMoneyAI 🤖\n\n"
            "Пришли мне фотографию человека 📸\n"
            "Я уберу фон и сделаю Telegram-стикер ✨",
        )
        return "OK", 200

    if message.get("photo"):
        try:
            send_message(
                chat_id,
                "Фото получил 📸\n"
                "Убираю фон и создаю стикер... ⏳",
            )

            file_id = message["photo"][-1]["file_id"]

            photo_bytes = download_telegram_photo(file_id)

            sticker = make_sticker(photo_bytes)

            result = send_sticker(chat_id, sticker)

            if result.get("ok"):
                send_message(
                    chat_id,
                    "Готово! 😎\n"
                    "Это уже настоящий Telegram-стикер ✨",
                )
            else:
                send_message(
                    chat_id,
                    "Не получилось отправить стикер 😕\n"
                    "Попробуй другую фотографию.",
                )

        except Exception as error:
            print("STICKER ERROR:", error)

            send_message(
                chat_id,
                "Произошла ошибка при создании стикера 😕\n"
                "Попробуй ещё раз.",
            )

        return "OK", 200

    send_message(
        chat_id,
        "Пришли мне фотографию 📸",
    )

    return "OK", 200
