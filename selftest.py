"""Самопроверка бота: связь с API + зарегистрированные обработчики."""
import asyncio
from pathlib import Path

from maxapi import Bot

import bot as bot_module  # импортируем наш bot.py (хэндлеры зарегистрируются)

token = Path(__file__).with_name("token.txt").read_text(encoding="utf-8").strip()


def show_handlers():
    ev = bot_module.dp.message_created
    handlers = getattr(ev, "handlers", None)
    print("Зарегистрировано обработчиков message_created:",
          len(handlers) if handlers is not None else "?")
    if handlers:
        for h in handlers:
            func = getattr(h, "func_event", getattr(h, "handler", h))
            name = getattr(func, "__name__", repr(func))
            print("  -", name)


async def check_api():
    b = Bot(token)
    try:
        me = await b.get_me()
        print("Связь с API: OK")
        print("  username:", getattr(me, "username", "?"))
        print("  id:", getattr(me, "user_id", "?"))
    except Exception as e:
        print("Связь с API: ОШИБКА:", type(e).__name__, e)
    finally:
        try:
            await b.session.close()
        except Exception:
            pass


show_handlers()
asyncio.run(check_api())
