import os
import io
import requests
from flask import Flask, request
from PIL import Image, ImageOps, ImageDraw

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    )


def make_sticker(photo_bytes):
    image = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")

    # Делаем квадрат 512x512
    image = ImageOps.fit(
        image,
        (512, 512),
        method=Image.Resampling.LANCZOS
    )

    # Круглая форма с прозрачными углами
    mask = Image.new("L", (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((8, 8, 504, 504), fill=255)

    result = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)

    output = io.BytesIO()
    result.save(output, format="WEBP", quality=90)
    output.seek(0)

    return output


def send_sticker(chat_id, sticker):
    requests.post(
        f"{TELEGRAM_API}/sendSticker",
        data={"chat_id": chat_id},
        files={"sticker": ("sticker.webp", sticker, "image/webp")},
        timeout=30,
    )


def process_photo(chat_id, photos):
    try:
        send_message(chat_id, "Фото получил 📸\nСоздаю стикер... ⏳")

        # Берём фотографию лучшего качества
        file_id = photos[-1]["file_id"]

        file_info = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={"file_id": file_id},
            timeout=20,
        ).json()

        file_path = file_info["result"]["file_path"]

        photo = requests.get(
            f"https://api.telegram.org/file/bot{TOKEN}/{file_path}",
            timeout=30,
        ).content

        sticker = make_sticker(photo)
        send_sticker(chat_id, sticker)

        send_message(
            chat_id,
            "Готово! 😎\n"
            "Твой первый StickerMoneyAI стикер готов ✨"
        )

    except Exception as error:
        print("Sticker error:", error)
        send_message(
            chat_id,
            "Не получилось создать стикер 😕\nПопробуй отправить другое фото."
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
            "Пришли мне фотографию 📸\n\n"
            "Я бесплатно превращу её в простой стикер ✨"
        )

    elif message.get("photo"):
        process_photo(chat_id, message["photo"])

    else:
        send_message(chat_id, "Пришли мне фотографию 📸")

    return "OK", 200


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    base_url = f"https://{request.host}"

    response = requests.get(
        f"{TELEGRAM_API}/setWebhook",
        params={"url": f"{base_url}/webhook"},
        timeout=20,
    )

    return response.json()
