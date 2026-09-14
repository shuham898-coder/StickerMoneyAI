import os
import io
import threading
import requests

from flask import Flask, request
from PIL import Image
from rembg import remove, new_session


app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# Более лёгкая модель удаления фона
REMBG_SESSION = None

# Защита от повторной обработки одного сообщения Telegram
processed_updates = set()
updates_lock = threading.Lock()


def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=20,
        )
    except Exception as error:
        print("SEND MESSAGE ERROR:", error)


def download_telegram_photo(file_id):
    response = requests.get(
        f"{TELEGRAM_API}/getFile",
        params={"file_id": file_id},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise Exception("Telegram не вернул файл")

    file_path = data["result"]["file_path"]

    photo = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_path}",
        timeout=30,
    )
    photo.raise_for_status()

    return photo.content


def get_rembg_session():
    global REMBG_SESSION

    if REMBG_SESSION is None:
        print("Loading rembg model...")
        REMBG_SESSION = new_session("u2netp")
        print("rembg model loaded")

    return REMBG_SESSION


def make_sticker(photo_bytes):
    # Удаляем фон
    session = get_rembg_session()

    result = remove(
        photo_bytes,
        session=session
    )

    image = Image.open(
        io.BytesIO(result)
    ).convert("RGBA")

    # Убираем прозрачные пустые края
    bbox = image.getbbox()

    if bbox:
        image = image.crop(bbox)

    # Человек занимает почти весь стикер
    image.thumbnail(
        (500, 500),
        Image.Resampling.LANCZOS
    )

    # Прозрачный холст 512x512
    canvas = Image.new(
        "RGBA",
        (512, 512),
        (0, 0, 0, 0)
    )

    x = (512 - image.width) // 2
    y = (512 - image.height) // 2

    canvas.alpha_composite(
        image,
        (x, y)
    )

    output = io.BytesIO()

    canvas.save(
        output,
        format="WEBP",
        quality=88,
        method=4
    )

    output.seek(0)

    return output


def send_sticker(chat_id, sticker):
    sticker.seek(0)

    response = requests.post(
        f"{TELEGRAM_API}/sendSticker",
        data={
            "chat_id": chat_id
        },
        files={
            "sticker": (
                "sticker.webp",
                sticker,
                "image/webp"
            )
        },
        timeout=60,
    )

    return response.json()


def process_photo(chat_id, file_id):
    try:
        send_message(
            chat_id,
            "Фото получил 📸\n"
            "Убираю фон и создаю стикер... ⏳"
        )

        photo_bytes = download_telegram_photo(file_id)

        sticker = make_sticker(photo_bytes)

        result = send_sticker(
            chat_id,
            sticker
        )

        print("SEND STICKER RESULT:", result)

        if result.get("ok"):
            send_message(
                chat_id,
                "Готово! 😎\n"
                "Стикер создан ✨"
            )
        else:
            send_message(
                chat_id,
                "Telegram не принял стикер 😕\n"
                "Попробуй другую фотографию."
            )

    except Exception as error:
        print("STICKER ERROR:", repr(error))

        send_message(
            chat_id,
            "Не получилось создать стикер 😕\n"
            "Попробуй ещё раз через минуту."
        )


@app.route("/", methods=["GET"])
def home():
    return "StickerMoneyAI работает! 🚀", 200


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    base_url = request.host_url.rstrip("/")

    response = requests.get(
        f"{TELEGRAM_API}/setWebhook",
        params={
            "url": f"{base_url}/webhook"
        },
        timeout=30,
    )

    return response.json()


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(
        silent=True
    ) or {}

    update_id = update.get("update_id")

    # Telegram иногда повторяет один запрос.
    # Второй раз его не обрабатываем.
    if update_id is not None:
        with updates_lock:
            if update_id in processed_updates:
                return "OK", 200

            processed_updates.add(update_id)

            # Не даём списку бесконечно расти
            if len(processed_updates) > 1000:
                processed_updates.clear()
                processed_updates.add(update_id)

    message = update.get("message")

    if not message:
        return "OK", 200

    chat_id = message["chat"]["id"]

    if message.get("text") == "/start":
        send_message(
            chat_id,
            "Привет! 👋\n\n"
            "Я StickerMoneyAI 🤖\n"
            "Пришли фотографию человека 📸\n\n"
            "Я уберу фон и сделаю стикер ✨"
        )

        return "OK", 200

    if message.get("photo"):
        file_id = message["photo"][-1]["file_id"]

        # Запускаем обработку отдельно,
        # а Telegram сразу получает OK.
        worker = threading.Thread(
            target=process_photo,
            args=(chat_id, file_id),
            daemon=True
        )

        worker.start()

        return "OK", 200

    send_message(
        chat_id,
        "Пришли мне фотографию 📸"
    )

    return "OK", 200
