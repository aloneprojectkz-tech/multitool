import asyncio
import g4f
from g4f.client import AsyncClient

PROVIDERS = [
    g4f.Provider.PollinationsAI,
    g4f.Provider.DeepInfra,
    g4f.Provider.Qwen_Qwen_3,
    g4f.Provider.Qwen_Qwen_2_5_Max,
    g4f.Provider.ItalyGPT,
    g4f.Provider.TeachAnything,
    g4f.Provider.Yqcloud,
]

client = AsyncClient()

# Кэшируем рабочий провайдер
_working_provider = None


async def _find_working_provider():
    for provider in PROVIDERS:
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model="",
                    messages=[{"role": "user", "content": "hi"}],
                    provider=provider,
                ),
                timeout=10,
            )
            if resp.choices[0].message.content:
                return provider
        except Exception:
            continue
    return None


async def ask_ai(prompt: str, history: list[dict] | None = None) -> str:
    global _working_provider

    if _working_provider is None:
        _working_provider = await _find_working_provider()

    if _working_provider is None:
        return "❌ Ни один провайдер не ответил. Попробуй позже."

    messages = [{"role": "system", "content": "Ты полезный ассистент. Отвечай чётко и по делу."}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model="",
                messages=messages,
                provider=_working_provider,
            ),
            timeout=30,
        )
        answer = resp.choices[0].message.content
        if answer and answer.strip():
            return answer.strip()
        # Провайдер вернул пустоту — сбрасываем кэш
        _working_provider = None
        return "❌ Пустой ответ. Попробуй ещё раз."
    except asyncio.TimeoutError:
        _working_provider = None
        return "⏱ Превышено время ожидания. Попробуй ещё раз."
    except Exception as e:
        _working_provider = None
        return f"❌ Ошибка: {e}"
