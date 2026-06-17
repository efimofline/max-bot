"""Разовый тест подключения к OpenAI."""
import asyncio
from pathlib import Path
from openai import AsyncOpenAI

key = Path(__file__).with_name("openai_key.txt").read_text(encoding="utf-8").strip()
client = AsyncOpenAI(api_key=key)

async def main():
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Привет! Ответь одним коротким предложением."}],
        )
        print("GPT ответил:", response.choices[0].message.content)
        print("Модель:", response.model)
    except Exception as e:
        print("ОШИБКА:", type(e).__name__, e)

asyncio.run(main())
