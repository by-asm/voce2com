from fastapi import HTTPException

_MESSAGES: dict[str, dict[str, str]] = {
    "UNAUTHORIZED": {
        "en": "Invalid or missing API key",
        "es": "Clave de API inválida o ausente",
        "gl": "Clave de API inválida ou ausente",
    },
    "TEXT_EMPTY": {
        "en": "The 'text' parameter cannot be empty",
        "es": "El parámetro 'text' no puede estar vacío",
        "gl": "O parámetro 'text' non pode estar baleiro",
    },
    "TEXT_TOO_LONG": {
        "en": "Text exceeds the maximum allowed length",
        "es": "El texto supera la longitud máxima permitida",
        "gl": "O texto supera a lonxitude máxima permitida",
    },
    "LANGUAGE_NOT_FOUND": {
        "en": "The requested language is not available",
        "es": "El idioma solicitado no está disponible",
        "gl": "O idioma solicitado non está dispoñible",
    },
    "VOICE_NOT_FOUND": {
        "en": "The requested voice is not available for this language",
        "es": "La voz solicitada no está disponible para este idioma",
        "gl": "A voz solicitada non está dispoñible para este idioma",
    },
    "RATE_LIMIT_EXCEEDED": {
        "en": "Too many requests, please try again later",
        "es": "Demasiadas solicitudes, inténtalo de nuevo más tarde",
        "gl": "Demasiadas solicitudes, téntao de novo máis tarde",
    },
}

_SUPPORTED_LOCALES = {"en", "es", "gl"}
_DEFAULT_LOCALE = "en"


def resolve_locale(accept_language: str | None) -> str:
    if not accept_language:
        return _DEFAULT_LOCALE
    for tag in accept_language.split(","):
        lang = tag.strip().split(";")[0].strip()[:2].lower()
        if lang in _SUPPORTED_LOCALES:
            return lang
    return _DEFAULT_LOCALE


def tts_error(code: str, locale: str, status: int, **extra) -> HTTPException:
    messages = _MESSAGES.get(code, {})
    message = messages.get(locale) or messages.get(_DEFAULT_LOCALE, code)
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})
