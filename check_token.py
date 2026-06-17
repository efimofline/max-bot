"""Разовая проверка: валиден ли токен и какой у бота профиль."""
import asyncio
from pathlib import Path

from maxapi import Bot

token = Path(__file__).with_name("token.txt").read_text(encoding="utf-8").strip()


async def main():
    bot = Bot(token)
    try:
        me = await bot.get_me()
        print("OK: токен валиден")
        print("Имя бота:", getattr(me, "name", "?"))
        print("Username:", getattr(me, "username", "?"))
        print("ID:", getattr(me, "user_id", getattr(me, "id", "?")))
    except Exception as e:
        print("ОШИБКА:", type(e).__name__, e)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


asyncio.run(main())
