"""Тест генерации картинки через Pollinations AI (без ключа)."""
import asyncio
from pathlib import Path
import aiohttp
import urllib.parse

async def main():
    prompt = "a cute cat sitting on a window sill, digital art"
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    print(f"Генерирую картинку: {prompt}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            print(f"Статус: {resp.status}, Content-Type: {resp.content_type}")
            if resp.status == 200 and "image" in resp.content_type:
                data = await resp.read()
                out = Path(__file__).with_name("test_output.jpg")
                out.write_bytes(data)
                print(f"Готово! Сохранена: {out} ({len(data):,} байт)")
            else:
                print("Ошибка:", await resp.text())

asyncio.run(main())
