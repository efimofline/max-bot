"""Разовый тест: найти chat_id из последних апдейтов и отправить туда кнопки."""
import asyncio
from pathlib import Path

from maxapi import Bot

import bot as bot_module  # чтобы переиспользовать main_keyboard()

token = Path(__file__).with_name("token.txt").read_text(encoding="utf-8").strip()


def find_chat_id(updates: dict):
    for upd in updates.get("updates", []):
        msg = upd.get("message") or {}
        recipient = msg.get("recipient") or {}
        if recipient.get("chat_id"):
            return recipient["chat_id"], None
        sender = msg.get("sender") or {}
        if sender.get("user_id"):
            return None, sender["user_id"]
        cb = upd.get("callback") or {}
        user = cb.get("user") or {}
        if user.get("user_id"):
            return None, user["user_id"]
    return None, None


async def main():
    b = Bot(token)
    try:
        updates = await b.get_updates(timeout=5)
        n = len(updates.get("updates", []))
        print(f"Получено апдейтов: {n}")
        chat_id, user_id = find_chat_id(updates)
        if not chat_id and not user_id:
            print("Не нашёл, кому писать. Напиши боту любое сообщение и запусти тест снова.")
            return
        print(f"Отправляю кнопки -> chat_id={chat_id}, user_id={user_id}")
        await b.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text="Тест кнопок 👇 Если видишь кнопки — всё работает!",
            attachments=[bot_module.main_keyboard()],
        )
        print("Отправлено. Проверь чат с ботом в MAX.")
    except Exception as e:
        print("ОШИБКА:", type(e).__name__, e)
    finally:
        try:
            await b.session.close()
        except Exception:
            pass


asyncio.run(main())
