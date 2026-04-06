from deep_translator import GoogleTranslator


def translate(text: str, source: str = "auto", target: str = "en") -> str:
    try:
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        return f"[Ошибка перевода: {e}]"
