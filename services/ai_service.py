import asyncio
from g4f.client import AsyncClient


async def ask_ai(prompt: str) -> str:
    client = AsyncClient()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты полезный ассистент. Отвечай чётко и по делу."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()
