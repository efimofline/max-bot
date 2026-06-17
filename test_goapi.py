"""Тест генерации музыки через GoAPI.ai (Udio)."""
import asyncio
import json
import aiohttp
from pathlib import Path

KEY = Path(__file__).with_name("goapi_key.txt").read_text(encoding="utf-8").strip()
BASE = "https://api.goapi.ai/api/v1"
HEADERS = {"x-api-key": KEY, "Content-Type": "application/json"}


async def main():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Шаг 1 — создаём задачу
        print("Создаю задачу генерации...")
        body = {
            "model": "music-u",
            "task_type": "generate_music",
            "input": {
                "lyrics_type": "generate",
                "prompt": "relaxing lofi hip hop beat",
            },
        }
        async with session.post(
            f"{BASE}/task", json=body,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()
            print("Ответ создания:", json.dumps(data, ensure_ascii=False)[:400])
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                print("ОШИБКА: нет task_id")
                return

        # Шаг 2 — ждём готовности
        print(f"Задача: {task_id}. Жду готовности (до 3 минут)...")
        for attempt in range(20):
            await asyncio.sleep(10)
            async with session.get(
                f"{BASE}/task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                result = await resp.json()
                status = result.get("data", {}).get("status", "?")
                print(f"  Попытка {attempt + 1} — status={status}")

                if status == "failed":
                    print("Генерация провалилась")
                    print(json.dumps(result, ensure_ascii=False)[:400])
                    return

                if status == "completed":
                    songs = result.get("data", {}).get("output", {}).get("songs", [])
                    if songs:
                        audio_url = songs[0].get("song_path")
                        print(f"\nГотово! URL аудио: {audio_url}")
                        async with session.get(
                            audio_url, timeout=aiohttp.ClientTimeout(total=120)
                        ) as ar:
                            audio = await ar.read()
                            out = Path(__file__).with_name("test_goapi_output.mp3")
                            out.write_bytes(audio)
                            print(f"Сохранено: {out} ({len(audio):,} байт)")
                    return

        print("Таймаут")

asyncio.run(main())
