"""Разовый тест подключения к GigaChat."""
import asyncio
from pathlib import Path
from gigachat import GigaChat

key = Path(__file__).with_name("gigachat_key.txt").read_text(encoding="utf-8").strip()

async def main():
    try:
        async with GigaChat(credentials=key, verify_ssl_certs=False) as giga:
            response = await giga.achat("Привет! Ответь одним коротким предложением.")
            print("GigaChat ответил:", response.choices[0].message.content)
    except Exception as e:
        print("ОШИБКА:", type(e).__name__, e)

asyncio.run(main())
