"""Тест генерации музыки через MusicAPI.ai."""
import asyncio
import json
import aiohttp
from pathlib import Path

KEY = Path(__file__).with_name("musicapi_key.txt").read_text(encoding="utf-8").strip()
BASE = "https://api.musicapi.ai/api/v1/sonic"
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


async def main():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Шаг 1 — создаём задачу
        print("Создаю задачу генерации...")
        async with session.post(f"{BASE}/create", json={
            "custom_mode": False,
            "mv": "sonic-v4",
            "gpt_description_prompt": "relaxing lofi hip hop beat",
            "make_instrumental": True,
        }, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            print("Ответ создания:", data)
            task_id = data.get("task_id")
            if not task_id:
                print("ОШИБКА: нет task_id")
                return

        # Шаг 2 — ждём готовности
        print(f"Задача: {task_id}. Жду готовности (до 3 минут)...")
        for attempt in range(20):
            await asyncio.sleep(10)
            async with session.get(
                f"{BASE}/task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json()
                print(f"  Попытка {attempt+1} — полный ответ:", json.dumps(result, ensure_ascii=False)[:300])

                # data может быть списком треков
                clips = result.get("data") if isinstance(result.get("data"), list) else []
                if clips:
                    clip = clips[0]
                    state = clip.get("state", "?")
                    print(f"  state={state}")
                    if state == "succeeded":
                        audio_url = clip.get("audio_url") or clip.get("url")
                        print(f"\n✅ Готово! URL аудио: {audio_url}")
                        # Скачиваем
                        async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=60)) as ar:
                            audio = await ar.read()
                            out = Path(__file__).with_name("test_output.mp3")
                            out.write_bytes(audio)
                            print(f"Сохранено: {out} ({len(audio):,} байт)")
                        return
                    if state == "failed":
                        print("❌ Генерация провалилась")
                        return
                else:
                    # другой формат
                    state = result.get("state", "?")
                    print(f"  state={state} (другой формат)")
                    if state in ("succeeded", "failed"):
                        return

        print("Таймаут")

asyncio.run(main())
