import re


def validate_phone_number(phone: str) -> tuple[bool, str | None]:
    cleaned_phone = re.sub(r"[\s\-\(\)]", "", phone)

    if not cleaned_phone.isdigit():
        return False, "El número de teléfono debe contener solo dígitos"

    if len(cleaned_phone) != 10:
        return (
            False,
            f"El número de teléfono debe tener exactamente 10 dígitos. Se recibieron {len(cleaned_phone)} dígitos.",
        )

    return True, None


def extract_phone_number(text: str) -> str | None:
    pattern = r"\b\d{10}\b"
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]

    cleaned = re.sub(r"[^\d]", "", text)
    if len(cleaned) == 10:
        return cleaned
    elif len(cleaned) == 11:
        return cleaned[-10:]  # Tomar últimos 10 dígitos

    return None


def validate_amount(amount_text: str) -> tuple[bool, float | None, str | None]:
    cleaned = re.sub(r"[\s\$]", "", amount_text.lower())
    cleaned = re.sub(r",(\d{1,2})$", r".\1", cleaned)
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    
    numbers = re.findall(r"\d+\.?\d*", cleaned)
    if not numbers:
        return False, None, "No se pudo encontrar un monto válido en tu mensaje"

    try:
        amount = float(numbers[0])
        if amount <= 0:
            return False, None, "El monto debe ser mayor a 0"
        return True, amount, None
    except ValueError:
        return False, None, "El monto proporcionado no es válido"


def extract_amount(text: str) -> float | None:
    is_valid, amount, _ = validate_amount(text)
    if is_valid:
        return amount
    return None


def is_transfer_related(message: str, conversation_context: list[dict] | None = None) -> bool:
    """
    Verifica si el mensaje está relacionado con transferencias de dinero.
    Enfoque permisivo: solo bloquea temas claramente fuera de contexto.
    Si hay contexto de conversación, es muy permisivo para permitir conversaciones naturales.
    
    Args:
        message: El mensaje a validar
        conversation_context: Lista de mensajes previos en la conversación (opcional)
    
    Retorna True si el mensaje está relacionado o si no se puede determinar claramente,
    False solo para temas claramente fuera de contexto.
    """
    message_lower = message.lower().strip()
    
    # Si el mensaje está vacío, permitirlo
    if not message_lower:
        return True
    
    # Verificar si hay contexto previo de conversación
    has_conversation_context = False
    if conversation_context and len(conversation_context) > 1:
        # Si hay más de un mensaje, hay contexto de conversación
        has_conversation_context = True
    
    # Lista muy específica de temas que claramente NO son transferencias
    # Solo bloquear temas obviamente fuera de contexto
    clearly_out_of_context = [
        # Astronomía y espacio
        "distancia del sol",
        "distancia de la luna",
        "distancia del sol a la luna",
        "distancia entre el sol y la luna",
        "tamaño del sol",
        "tamaño de la luna",
        "planeta",
        "planetas",
        "estrella",
        "estrellas",
        "galaxia",
        "galaxias",
        "universo",
        "astronomía",
        "astronomia",
        "astronauta",
        "nasa",
        "satélite",
        "satelite",
        # Ciencia general (solo si es muy específico)
        "fórmula química",
        "formula quimica",
        "ecuación física",
        "ecuacion fisica",
        "teorema matemático",
        "teorema matematico",
        # Historia y geografía (solo si es muy específico)
        "año de independencia",
        "año de independencia de",
        "capital de",
        "país más grande",
        "pais mas grande",
        # Clima (solo si es muy específico)
        "temperatura en",
        "clima en",
        "pronóstico del tiempo",
        "pronostico del tiempo",
    ]
    
    # Verificar si el mensaje contiene temas claramente fuera de contexto
    # Solo bloquear si es muy específico y obviamente no relacionado
    for keyword in clearly_out_of_context:
        if keyword in message_lower:
            return False
    
    # Si hay contexto de conversación, ser MUY permisivo
    # Permitir casi todo excepto temas claramente fuera de contexto
    if has_conversation_context:
        return True
    
    # Si no hay contexto, ser un poco más estricto pero aún permisivo
    # Permitir saludos y preguntas generales
    greetings = [
        "hola", "hi", "hello", "buenos días", "buenos dias", "buenas tardes",
        "buenas noches", "good morning", "good afternoon", "good evening",
        "hey", "saludos", "greetings", "qué tal", "que tal", "what's up"
    ]
    
    if any(greeting in message_lower for greeting in greetings):
        return True
    
    # Permitir preguntas sobre ayuda, proceso, instrucciones
    help_keywords = [
        "ayuda", "help", "cómo", "como", "how", "qué", "que", "what",
        "dime", "cuéntame", "cuentame", "tell me", "explicar", "explain",
        "paso", "pasos", "proceso", "instrucciones", "siguiente", "next",
        "luego", "después", "despues", "after", "hacer", "do"
    ]
    
    if any(keyword in message_lower for keyword in help_keywords):
        return True
    
    # Por defecto, permitir (ser permisivo y confiar en el system prompt)
    # Solo bloquear si es claramente fuera de contexto
    return True
