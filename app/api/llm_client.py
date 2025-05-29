import httpx
import json
from app.core.config import settings
from app.utils.logger import logger 
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

# --- Constants ---
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 30.0
CHAT_COMPLETIONS_PATH = "/chat/completions"

def get_base_url() -> str:
    """Get and validate the OpenRouter base URL from settings."""
    if not settings or not hasattr(settings, 'OPENROUTER_CHAT_ENDPOINT'):
        logger.warning(f"OPENROUTER_CHAT_ENDPOINT no encontrado. Usando default: {DEFAULT_BASE_URL}")
        return DEFAULT_BASE_URL
    
    # Convert Pydantic HttpUrl to string if needed
    base_url = str(settings.OPENROUTER_CHAT_ENDPOINT)
    
    # Remove /chat/completions if present
    if "/chat/completions" in base_url:
        logger.warning(
            f"OPENROUTER_CHAT_ENDPOINT ('{base_url}') contiene endpoint completo. "
            "Se usará solo la URL base."
        )
        base_url = base_url.split('/chat/completions')[0]
    
    # Validate URL format
    try:
        parsed = urlparse(base_url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("URL inválida")
        return base_url
    except Exception as e:
        logger.error(f"URL base inválida ({base_url}): {e}")
        return DEFAULT_BASE_URL

# --- Client Initialization ---
try:
    _BASE_URL_OPENROUTER_API = get_base_url()
    _TIMEOUT_LLM = getattr(settings, 'http_client_timeout', DEFAULT_TIMEOUT)

    client = httpx.AsyncClient(
        base_url=str(_BASE_URL_OPENROUTER_API),
        timeout=float(_TIMEOUT_LLM)
    )
    logger.info(
        f"Cliente HTTP para LLM inicializado. "
        f"Base URL: {_BASE_URL_OPENROUTER_API}, "
        f"Timeout: {_TIMEOUT_LLM}s"
    )
except Exception as e_client:
    logger.error(f"Error inicializando cliente HTTP: {e_client}", exc_info=True)
    client = None



async def get_llm_response(prompt_from_builder: str) -> Optional[str]:
    """
    Obtiene una respuesta de un modelo de lenguaje a través de OpenRouter.
    """
    if client is None:
        logger.error("El cliente HTTP para LLM (OpenRouter) no está inicializado.")
        return "Error interno: Cliente LLM no disponible."

    if not settings:
        logger.error("Settings no disponibles. No se puede acceder a la configuración del LLM.")
        return "Error interno: Configuración no disponible."

    if not settings.OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY no está configurada en settings.")
        return "Error interno: Clave API para OpenRouter no configurada."
    if not settings.OPENROUTER_MODEL_CHAT:
        logger.error("OPENROUTER_MODEL_CHAT no está configurado en settings.")
        return "Error interno: Modelo de OpenRouter no configurado."

    api_key = settings.OPENROUTER_API_KEY
    model_identifier = settings.OPENROUTER_MODEL_CHAT
    
    your_site_url = "https://tu-proyecto.com" # REEMPLAZA ESTO con tu URL de sitio/app o repo
    your_app_name = settings.PROJECT_NAME if settings.PROJECT_NAME else "ChatbotWhatsApp"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": your_site_url, 
        "X-Title": your_app_name       
    }

    system_content: str = ""
    user_content: str = prompt_from_builder 
    try:
        if "**Pregunta Usuario:**" in prompt_from_builder:
            parts = prompt_from_builder.split("**Pregunta Usuario:**", 1)
            system_content = parts[0].strip() 
            user_content = parts[1].strip()
            if "**Respuesta:**" in user_content:
                user_content = user_content.split("**Respuesta:**", 1)[0].strip()
        else:
            logger.debug("Delimitador '**Pregunta Usuario:**' no encontrado. Todo el prompt como 'user_content'.")
    except Exception as e_parse:
        logger.warning(f"Error parseando prompt para system/user: {e_parse}. Usando prompt completo como user_content.")
        system_content = "" 
        user_content = prompt_from_builder

    messages: List[Dict[str, str]] = []
    if system_content:
        messages.append({"role": "system", "content": system_content})
    
    if not user_content or not user_content.strip():
        logger.error(f"User content vacío. Prompt original: '{prompt_from_builder[:100]}...'")
        return "Error interno: Pregunta del usuario vacía."
        
    messages.append({"role": "user", "content": user_content})

# En app/api/llm_client.py, línea 105
    llm_temperature = settings.LLM_TEMPERATURE # Cambiar a mayúsculas
# Lo mismo para llm_max_tokens si también da error
    llm_max_tokens = settings.LLM_MAX_TOKENS

    payload = {
        "model": model_identifier,
        "messages": messages,
        "max_tokens": llm_max_tokens,
        "temperature": llm_temperature,
        "stream": False
    }

    # Definir el path del endpoint de chat
    _OPENROUTER_CHAT_PATH = CHAT_COMPLETIONS_PATH

    # La URL completa será _BASE_URL_OPENROUTER_API + _OPENROUTER_CHAT_PATH
    logger.info(f"Enviando solicitud a OpenRouter. Modelo: {model_identifier}, Endpoint Path: {_OPENROUTER_CHAT_PATH}")
    logger.debug(f"Payload messages para OpenRouter: {messages}")
    logger.debug(f"Payload completo (sin API key): {json.dumps(payload, ensure_ascii=False, indent=2)}")


    try:
        # Llamada POST al path específico del endpoint de chat
        response = await client.post(_OPENROUTER_CHAT_PATH, headers=headers, json=payload)
        
        response.raise_for_status() 
        data = response.json()
        logger.debug(f"Respuesta completa de OpenRouter (JSON): {data}")

        if data.get("choices") and isinstance(data["choices"], list) and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if isinstance(choice, dict) and choice.get("message") and isinstance(choice["message"], dict) and \
               "content" in choice["message"] and isinstance(choice["message"]["content"], str):
                ai_message = choice["message"]["content"].strip()
                logger.info(f"Respuesta de OpenRouter recibida (primeros 100 chars): '{ai_message[:100]}...'")
                return ai_message
            else:
                logger.warning(f"Estructura inesperada en 'message' o 'content' en OpenRouter: {choice}")
        else:
            logger.warning(f"Respuesta de OpenRouter no contiene 'choices' válidas: {data}")
        return "Modelo no generó respuesta válida."

    except httpx.HTTPStatusError as e_status:
        error_body = "No se pudo leer cuerpo del error."
        try:
            error_body_bytes = await e_status.response.aread()
            error_body = error_body_bytes.decode(errors='replace')
        except Exception as read_err:
            logger.error(f"Error adicional leyendo cuerpo de error HTTP de OpenRouter: {read_err}")
        logger.error(f"Error HTTP de OpenRouter: {e_status.response.status_code} - URL: {e_status.request.url} - Cuerpo: {error_body}", exc_info=False)
        return f"Error de comunicación con servicio LLM ({e_status.response.status_code}). Detalles: {error_body[:200]}"
    except httpx.RequestError as e_req:
        logger.error(f"Error de red/solicitud llamando a OpenRouter: {e_req} - URL: {e_req.request.url if e_req.request else 'N/A'}: {e_req}", exc_info=True)
        return "Error de red contactando servicio LLM."
    except Exception as e_unexpected:
        logger.error(f"Error inesperado en get_llm_response (OpenRouter): {e_unexpected}", exc_info=True)
        return "Error inesperado procesando respuesta del LLM."