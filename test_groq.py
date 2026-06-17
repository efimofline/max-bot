"""Разовый тест подключения к Groq."""
import asyncio
from pathlib import Path
from openai import AsyncOpenAI

key = Path(__file__).with_name("groq_key.txt").read_text(encoding="utf-8").strip()
client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")

async def main():
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Привет! Ответь одним коротким предложением."}],
        )
        print("Groq ответил:", response.choices[0].message.content)
        print("Модель:", response.model)
    except Exception as e:
        print("ОШИБКА:", type(e).__name__, e)

asyncio.run(main())
