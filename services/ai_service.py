import asyncio
import g4f
from g4f.client import AsyncClient


async def ask_ai(prompt: str) -> str:
    client = AsyncClient()
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты полезный ассистент. Отвечай чётко и по делу."},
                    {"role": "user", "content": prompt},
                ],
                provider=g4f.Provider.Blackbox,
            ),
            timeout=30,
        )
        return response.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        return "⏱ Превышено время ожидания. Попробуй ещё раз."
    except Exception as e:
        return f"❌ Ошибка ИИ: {e}"
