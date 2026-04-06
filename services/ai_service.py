import asyncio
from g4f.client import AsyncClient


# Пробуем провайдеров по очереди пока один не ответит
PROVIDERS = ["DDG", "ChatGpt", "Pizzagpt", "FreeChatgpt", "Liaobots"]


async def ask_ai(prompt: str) -> str:
    client = AsyncClient()

    for provider_name in PROVIDERS:
        try:
            import g4f.Provider as P
            provider = getattr(P, provider_name, None)
            kwargs = {"provider": provider} if provider else {}

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ты полезный ассистент. Отвечай чётко и по делу."},
                        {"role": "user", "content": prompt},
                    ],
                    **kwargs,
                ),
                timeout=25,
            )
            text = response.choices[0].message.content
            if text and text.strip():
                return text.strip()
        except asyncio.TimeoutError:
            continue
        except Exception:
            continue

    return "❌ Все провайдеры недоступны. Попробуй позже."
