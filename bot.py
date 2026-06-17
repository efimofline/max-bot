"""
Бот для мессенджера MAX с ИИ-ассистентом на Lovable AI Gateway.

Запуск:
    1. Получи токен у @MasterBot в MAX → сохрани в token.txt
    2. Получи LOVABLE_API_KEY на lovable.dev → сохрани в lovable_key.txt
    3. pip install -r requirements.txt
    4. python bot.py
"""

import asyncio
import os
import traceback
import urllib.parse
from pathlib import Path

import aiohttp
from openai import AsyncOpenAI
from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import Command
from maxapi.types import CallbackButton, InputMediaBuffer, LinkButton, MessageCallback, MessageCreated
from maxapi.types.attachments.upload import UploadType
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

# ── Конфигурация ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "llama-3.3-70b-versatile"

MODELS = {
    "llama-3.3-70b-versatile": "🦙 Llama 3.3 70B — универсальная",
    "llama-3.1-8b-instant":    "⚡ Llama 3.1 8B — быстрая",
    "mixtral-8x7b-32768":      "🌀 Mixtral 8x7B — длинный контекст",
    "openai/gpt-oss-20b":      "🚀 GPT OSS 20B — сверхбыстрая",
}
SYSTEM_PROMPT = "Ты — дружелюбный ассистент. Отвечай кратко и по делу на русском языке."


def _read_file(name: str) -> str:
    f = Path(__file__).with_name(name)
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


TOKEN = _read_file("token.txt") or os.getenv("MAX_BOT_TOKEN", "")
GROQ_KEY = _read_file("groq_key.txt") or os.getenv("GROQ_API_KEY", "")
GOAPI_KEY = _read_file("goapi_key.txt") or os.getenv("GOAPI_KEY", "")

if not TOKEN:
    raise SystemExit(
        "Не задан токен бота!\n"
        "Создай файл token.txt рядом с bot.py и вставь токен от @MasterBot."
    )

if not GROQ_KEY:
    raise SystemExit(
        "Не задан Groq API ключ!\n"
        "Создай файл groq_key.txt рядом с bot.py и вставь ключ с console.groq.com."
    )

openai_client = AsyncOpenAI(
    api_key=GROQ_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ── Состояние и история (в памяти на время работы бота) ──────────────────────

# { chat_id: [{"role": "user"|"assistant", "content": "..."}] }
_history: dict[int, list[dict]] = {}

# Чаты, ожидающие описание для генерации картинки или музыки
_waiting_image: set[int] = set()
_waiting_music: set[int] = set()       # режим «по описанию»
_waiting_music_text: set[int] = set()  # режим «свой текст»: шаг 1 — слова
_waiting_music_style: set[int] = set() # режим «свой текст»: шаг 2 — стиль
_pending_lyrics: dict[int, str] = {}   # текст песни, пока ждём стиль

# Выбранная модель для каждого чата
_chat_model: dict[int, str] = {}

MAX_HISTORY = 20  # максимум сообщений в истории на один чат


def get_history(chat_id: int) -> list[dict]:
    return _history.setdefault(chat_id, [])


def add_to_history(chat_id: int, role: str, content: str) -> None:
    history = get_history(chat_id)
    history.append({"role": role, "content": content})
    # Обрезаем историю, оставляя последние MAX_HISTORY сообщений
    if len(history) > MAX_HISTORY:
        _history[chat_id] = history[-MAX_HISTORY:]


# ── Lovable AI Gateway ────────────────────────────────────────────────────────

async def generate_image(prompt: str) -> bytes:
    """Генерирует картинку через Pollinations AI (бесплатно, без ключа)."""
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status != 200 or "image" not in resp.content_type:
                raise RuntimeError(f"Ошибка генерации ({resp.status})")
            return await resp.read()


GOAPI_BASE = "https://api.goapi.ai/api/v1"


async def generate_music(
    prompt: str = "",
    lyrics: str = "",
    style: str = "",
) -> bytes:
    """Генерирует трек через GoAPI.ai (Udio).

    prompt — описание для режима «AI придумывает сам».
    lyrics + style — режим «свой текст».
    """
    if not GOAPI_KEY:
        raise RuntimeError("NO_CREDITS")

    headers = {"x-api-key": GOAPI_KEY, "Content-Type": "application/json"}

    if lyrics:
        body = {
            "model": "music-u",
            "task_type": "generate_music",
            "input": {
                "lyrics_type": "user",
                "prompt": lyrics,
                "tags": style or "pop",
            },
        }
    else:
        body = {
            "model": "music-u",
            "task_type": "generate_music",
            "input": {
                "lyrics_type": "generate",
                "prompt": prompt,
            },
        }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Создаём задачу
        async with session.post(
            f"{GOAPI_BASE}/task", json=body,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                err = str(data.get("message", "")).lower()
                if "credit" in err or "balance" in err or "quota" in err or "point" in err:
                    raise RuntimeError("NO_CREDITS")
                raise RuntimeError(f"Не удалось создать задачу: {data}")

        # Ждём готовности (до 3 минут)
        for _ in range(20):
            await asyncio.sleep(10)
            async with session.get(
                f"{GOAPI_BASE}/task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                result = await resp.json()
                status = result.get("data", {}).get("status", "")
                if status == "failed":
                    raise RuntimeError("Генерация музыки провалилась")
                if status == "completed":
                    songs = result.get("data", {}).get("output", {}).get("songs", [])
                    if songs:
                        audio_url = songs[0].get("song_path")
                        async with session.get(
                            audio_url, timeout=aiohttp.ClientTimeout(total=120)
                        ) as ar:
                            return await ar.read()

    raise RuntimeError("Таймаут: трек не сгенерирован за 3 минуты")


async def ask_gpt(chat_id: int, user_text: str) -> str:
    """Отправляет сообщение в Groq с учётом истории и выбранной модели."""
    add_to_history(chat_id, "user", user_text)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + get_history(chat_id)
    model = _chat_model.get(chat_id, DEFAULT_MODEL)

    response = await openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )

    answer = response.choices[0].message.content
    add_to_history(chat_id, "assistant", answer)
    return answer


# ── Бот ───────────────────────────────────────────────────────────────────────

bot = Bot(
    TOKEN,
    after_input_media_delay=8.0,    # ждём 8с после загрузки файла
    after_upload_attempts=30,        # до 30 попыток отправки
    after_upload_retry_delay=5.0,    # 5с между попытками (итого до 2.5 мин)
)
dp = Dispatcher()


def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="ℹ️ Помощь", payload="help"),
        CallbackButton(text="🤖 О боте", payload="about"),
    )
    kb.row(
        CallbackButton(text="🎨 Картинку", payload="image"),
        CallbackButton(text="🎵 Написать песню", payload="music_menu"),
    )
    kb.row(
        CallbackButton(text="🧠 Модель ИИ", payload="model_menu"),
    )
    kb.row(
        CallbackButton(text="🗑 Очистить историю", payload="clear"),
        LinkButton(text="🌐 Сайт MAX", url="https://max.ru"),
    )
    return kb.as_markup()


def music_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="🎤 По описанию (AI придумает слова)", payload="music_prompt"))
    kb.row(CallbackButton(text="📝 Свой текст (ввести слова самому)", payload="music_text"))
    kb.row(CallbackButton(text="« Назад", payload="back"))
    return kb.as_markup()


def model_keyboard(current_model: str):
    kb = InlineKeyboardBuilder()
    for model_id, label in MODELS.items():
        mark = "✅ " if model_id == current_model else ""
        kb.row(CallbackButton(text=f"{mark}{label}", payload=f"model:{model_id}"))
    kb.row(CallbackButton(text="« Назад", payload="back"))
    return kb.as_markup()


@dp.message_created(Command("start"))
async def start(event: MessageCreated):
    await event.message.answer(
        "Привет! 👋 Я ИИ-ассистент на базе  AI.\n"
        "Задай мне любой вопрос — я отвечу.\n"
        "А еще я учусь сочинять песни и писать музыку.\n"
        "История нашего диалога сохраняется 🧠\n"
        "Или нажми кнопку ниже 👇",
        attachments=[main_keyboard()],
    )


@dp.message_created(Command("clear"))
async def clear_cmd(event: MessageCreated):
    chat_id = event.message.recipient.chat_id
    _history.pop(chat_id, None)
    await event.message.answer("История диалога очищена ✅")


@dp.message_callback()
async def on_button(event: MessageCallback):
    payload = event.callback.payload
    chat_id = event.chat.chat_id if event.chat else None

    if payload == "help":
        await event.message.answer(
            "Я умею:\n"
            "• Отвечать на любые вопросы 🤖\n"
            "• Рисовать картинки по описанию 🎨\n"
            "• Писать песни — по описанию или на свой текст 🎵\n"
            "• Помнить историю нашего диалога 🧠\n\n"
            "Команды:\n"
            "• /start — главное меню\n"
            "• /clear — очистить историю диалога"
        )
    elif payload == "about":
        await event.message.answer(
            "🤖 О боте\n\n"
            "Версия: 2.0\n\n"
            "Возможности:\n"
            "• ИИ-ассистент на базе Groq (Llama 3.3)\n"
            f"• Модель: {DEFAULT_MODEL}\n"
            "• Помнит историю диалога\n"
            "• /clear — сброс истории"
        )
    elif payload == "model_menu" and chat_id:
        current = _chat_model.get(chat_id, DEFAULT_MODEL)
        await event.message.answer(
            f"🧠 Выбери модель ИИ\nСейчас: {MODELS.get(current, current)}",
            attachments=[model_keyboard(current)],
        )
    elif payload.startswith("model:") and chat_id:
        model_id = payload.removeprefix("model:")
        if model_id in MODELS:
            _chat_model[chat_id] = model_id
            await event.message.answer(f"✅ Модель изменена: {MODELS[model_id]}")
    elif payload == "back":
        await event.message.answer(
            "Главное меню 👇",
            attachments=[main_keyboard()],
        )
    elif payload == "image" and chat_id:
        _waiting_image.add(chat_id)
        await event.message.answer("🎨 Опиши что нарисовать — и я пришлю картинку 👇")
    elif payload == "music_menu" and chat_id:
        if not GOAPI_KEY:
            await event.message.answer("🎵 Генерация музыки не настроена (нет goapi_key.txt)")
            return
        await event.message.answer(
            "🎵 Как написать песню?",
            attachments=[music_keyboard()],
        )
    elif payload == "music_prompt" and chat_id:
        _waiting_music.add(chat_id)
        await event.message.answer(
            "🎤 Опиши музыку — AI придумает слова и мелодию сам 👇\n"
            "Например: весёлая поп-песня про лето, грустный романс о любви"
        )
    elif payload == "music_text" and chat_id:
        _waiting_music_text.add(chat_id)
        await event.message.answer(
            "📝 Введи текст своей песни 👇\n\n"
            "Используй разметку для структуры:\n"
            "[Куплет] — куплет\n"
            "[Припев] — припев\n"
            "[Мост] — мост\n\n"
            "Пример:\n"
            "[Куплет]\n"
            "Я иду сквозь дождь и ветер\n"
            "Не боясь терять пути\n\n"
            "[Припев]\n"
            "Я лечу, я лечу над землёй"
        )
    elif payload == "clear" and chat_id:
        _history.pop(chat_id, None)
        await event.message.answer("История диалога очищена ✅")


@dp.message_created(Command("image"))
async def image_cmd(event: MessageCreated):
    """Генерирует картинку по описанию: /image кот на подоконнике"""
    text = event.message.body.text or ""
    prompt = text.removeprefix("/image").strip()
    if not prompt:
        await event.message.answer("Укажи описание картинки: /image кот на подоконнике")
        return
    await event.message.answer("🎨 Генерирую картинку, подожди 10–20 секунд...")
    try:
        image_bytes = await generate_image(prompt)
        await event.message.answer(
            attachments=[InputMediaBuffer(buffer=image_bytes, filename="image.jpg", type=UploadType.IMAGE)],
        )
    except Exception as e:
        await event.message.answer(f"Ошибка генерации: {e}")


@dp.message_created(F.message.body.text)
async def chat_with_ai(event: MessageCreated):
    """Передаёт сообщение в GPT или генерирует картинку (если нажата кнопка 🎨)."""
    text = event.message.body.text
    chat_id = event.message.recipient.chat_id

    if chat_id in _waiting_image:
        _waiting_image.discard(chat_id)
        await event.message.answer("🎨 Генерирую картинку, подожди 10–20 секунд...")
        try:
            image_bytes = await generate_image(text)
            await event.message.answer(
                attachments=[InputMediaBuffer(buffer=image_bytes, filename="image.jpg", type=UploadType.IMAGE)],
            )
        except Exception as e:
            await event.message.answer(f"Ошибка генерации картинки: {e}")
        return

    if chat_id in _waiting_music:
        _waiting_music.discard(chat_id)
        await event.message.answer("🎵 Генерирую музыку, подожди около 2 минут...")
        try:
            audio_bytes = await generate_music(prompt=text)
            print(f"[music] скачано байт: {len(audio_bytes)}")
            await event.message.answer(
                attachments=[InputMediaBuffer(buffer=audio_bytes, filename="music.mp3", type=UploadType.AUDIO)],
            )
        except Exception as e:
            traceback.print_exc()
            if "NO_CREDITS" in str(e):
                await event.message.answer(
                    "😔 Кредиты на генерацию музыки закончились.\n"
                    "Функция временно недоступна."
                )
            else:
                await event.message.answer(f"Ошибка генерации музыки: {e}")
        return

    if chat_id in _waiting_music_text:
        _waiting_music_text.discard(chat_id)
        _pending_lyrics[chat_id] = text
        _waiting_music_style.add(chat_id)
        await event.message.answer(
            "🎼 Отлично! Теперь укажи стиль музыки 👇\n"
            "Например: поп, рок, джаз, лирика, электронная, акустическая гитара"
        )
        return

    if chat_id in _waiting_music_style:
        _waiting_music_style.discard(chat_id)
        lyrics = _pending_lyrics.pop(chat_id, "")
        await event.message.answer("🎵 Генерирую песню с твоим текстом, подожди около 2 минут...")
        try:
            audio_bytes = await generate_music(lyrics=lyrics, style=text)
            print(f"[song] скачано байт: {len(audio_bytes)}")
            await event.message.answer(
                attachments=[InputMediaBuffer(buffer=audio_bytes, filename="song.mp3", type=UploadType.AUDIO)],
            )
        except Exception as e:
            traceback.print_exc()
            if "NO_CREDITS" in str(e):
                await event.message.answer(
                    "😔 Кредиты на генерацию музыки закончились.\n"
                    "Функция временно недоступна."
                )
            else:
                await event.message.answer(f"Ошибка генерации песни: {e}")
        return

    try:
        answer = await ask_gpt(chat_id, text)
        await event.message.answer(answer)
    except Exception as e:
        await event.message.answer(f"Ошибка ИИ: {e}")


async def main():
    print(f"Бот запущен. Модель: {DEFAULT_MODEL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
