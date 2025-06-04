import httpx
import json
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse # Para validación de URL

# Intenta importar settings y logger
try:
    from app.core.config import settings
    from app.utils.logger import logger
    SETTINGS_LOADED = True
except ImportError:
    import logging
    logger = logging.getLogger("app.api.llm_client_fallback")
    if not logger.hasHandlers():
        _h = logging.StreamHandler()
        _f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        _h.setFormatter(_f)
        logger.addHandler(_h)
        logger.setLevel(logging.INFO)
    logger.error("Error importando settings o logger principal. Usando fallback logger para llm_client.")
    settings = None # type: ignore
    SETTINGS_LOADED = False

# --- Constants ---
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_TIMEOUT = 30.0  # Segundos
CHAT_COMPLETIONS_ENDPOINT_PATH = "/chat/completions" # Path relativo al base_url

def _get_validated_base_url() -> str:
    """Obtiene y valida la URL base de OpenRouter desde la configuración."""
    if not SETTINGS_LOADED or not settings or not hasattr(settings, 'OPENROUTER_CHAT_ENDPOINT'):
        logger.warning(f"  OPENROUTER_CHAT_ENDPOINT no encontrado en settings. Usando URL base por defecto: {DEFAULT_OPENROUTER_BASE_URL}")
        return DEFAULT_OPENROUTER_BASE_URL
    
    # Convertir Pydantic HttpUrl a string si es necesario
    configured_url_str = str(settings.OPENROUTER_CHAT_ENDPOINT)
    
    # Intentar remover el path específico si está presente en la URL base configurada
    # La idea es que OPENROUTER_CHAT_ENDPOINT solo contenga la URL base.
    if CHAT_COMPLETIONS_ENDPOINT_PATH in configured_url_str:
        logger.warning(
            f"  OPENROUTER_CHAT_ENDPOINT ('{configured_url_str}') parece contener el path completo del endpoint. "
            f"Se intentará usar solo la parte base de la URL (antes de '{CHAT_COMPLETIONS_ENDPOINT_PATH}')."
        )
        base_url_candidate = configured_url_str.split(CHAT_COMPLETIONS_ENDPOINT_PATH)[0]
    else:
        base_url_candidate = configured_url_str
    
    # Validar el formato de la URL base resultante
    try:
        parsed = urlparse(base_url_candidate)
        if not all([parsed.scheme, parsed.netloc]): # Debe tener scheme (http/https) y netloc (dominio)
            raise ValueError(f"La URL base '{base_url_candidate}' es inválida (falta scheme o netloc).")
        logger.info(f"  URL base para OpenRouter validada: {base_url_candidate}")
        return base_url_candidate
    except ValueError as e_url: # Captura ValueError de urlparse o el nuestro
        logger.error(f"  Error validando la URL base '{base_url_candidate}': {e_url}. Usando URL por defecto: {DEFAULT_OPENROUTER_BASE_URL}")
        return DEFAULT_OPENROUTER_BASE_URL

# --- Client Initialization ---
# Esta sección se ejecuta una vez cuando el módulo se importa.
_llm_client_instance: Optional[httpx.AsyncClient] = None
try:
    if SETTINGS_LOADED and settings: # Solo intentar inicializar si settings está cargado
        _OPENROUTER_API_BASE_URL = _get_validated_base_url()
        _LLM_HTTP_TIMEOUT = float(getattr(settings, 'LLM_HTTP_TIMEOUT', DEFAULT_LLM_TIMEOUT)) # Asumiendo LLM_HTTP_TIMEOUT en settings

        _llm_client_instance = httpx.AsyncClient(
            base_url=_OPENROUTER_API_BASE_URL, # httpx manejará la unión con el path del endpoint
            timeout=_LLM_HTTP_TIMEOUT
        )
        logger.info(
            f"Cliente HTTP Async para LLM (OpenRouter) inicializado exitosamente. "
            f"Base URL: '{_OPENROUTER_API_BASE_URL}', Timeout: {_LLM_HTTP_TIMEOUT}s"
        )
    else:
        logger.error("Settings no cargados. El cliente HTTP para LLM no se pudo inicializar.")
        _llm_client_instance = None

except Exception as e_client_init:
    logger.critical(f"Error CRÍTICO durante la inicialización del cliente HTTP para LLM: {e_client_init}", exc_info=True)
    _llm_client_instance = None


async def get_llm_response(prompt_from_builder: str) -> Optional[str]:
    """
    Obtiene una respuesta de un modelo de lenguaje a través de OpenRouter.
    Devuelve el texto de la respuesta o un mensaje de error como string.
    """
    logger.debug(f"get_llm_response: Iniciando. Preview del prompt recibido (primeros 200 chars): '{prompt_from_builder[:200]}...'")

    if _llm_client_instance is None:
        logger.error("  Error: El cliente HTTP para LLM (OpenRouter) no está inicializado. No se puede hacer la solicitud.")
        return "Error interno: Cliente LLM no disponible."

    if not SETTINGS_LOADED or not settings:
        logger.error("  Error: Settings no disponibles. No se puede acceder a la configuración del LLM.")
        return "Error interno: Configuración de la aplicación no disponible."

    # Validar configuración esencial del LLM desde settings
    openrouter_api_key = getattr(settings, 'OPENROUTER_API_KEY', None)
    openrouter_model_id = getattr(settings, 'OPENROUTER_MODEL_CHAT', None)
    llm_temp = float(getattr(settings, 'LLM_TEMPERATURE', 0.2)) # Default a 0.7 si no está
    llm_max_t = int(getattr(settings, 'LLM_MAX_TOKENS', 200))    # Default a 512 si no está

    if not openrouter_api_key:
        logger.error("  Error: OPENROUTER_API_KEY no está configurada en settings.")
        return "Error interno: Clave API para OpenRouter no configurada."
    if not openrouter_model_id:
        logger.error("  Error: OPENROUTER_MODEL_CHAT (identificador del modelo) no está configurado en settings.")
        return "Error interno: Modelo de OpenRouter no configurado."

    # Headers recomendados por OpenRouter
    # !!! REEMPLAZA "https://tu-proyecto.com" con tu URL real o repo !!!
    site_url_for_header = getattr(settings, 'PROJECT_SITE_URL', "https://github.com/tu_usuario/tu_proyecto")
    site_url_str = str(site_url_for_header)  # Convertir HttpUrl a string
    app_name_for_header = getattr(settings, 'PROJECT_NAME', "ChatbotMultimarca")

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url_str,  # Usar el string en lugar del objeto HttpUrl
        "X-Title": app_name_for_header       
    }
    logger.debug(f"  Headers para OpenRouter (sin API Key): Referer='{site_url_for_header}', X-Title='{app_name_for_header}'")

    # Preparar el payload de mensajes (system y user)
    system_content: str = ""
    user_content: str = prompt_from_builder.strip() # Por defecto, todo el prompt es del usuario

    # Intento de separar el prompt en "system" y "user" si los delimitadores están presentes
    # Esto es específico para cómo `rag_prompt_builder` estructura el prompt.
    # Asumimos que la parte "system" es todo ANTES de "**Pregunta del Usuario:**"
    # y la parte "user" es todo DESPUÉS de "**Pregunta del Usuario:**" y ANTES de "**Tu Respuesta como...**"
    
    system_marker_end = "**Pregunta del Usuario:**" # Lo que sigue es la pregunta del usuario
    user_marker_end = "**Tu Respuesta como" # Lo que sigue es donde el LLM debe empezar a escribir

    try:
        if system_marker_end in prompt_from_builder:
            parts = prompt_from_builder.split(system_marker_end, 1)
            system_content = parts[0].strip()
            
            # La parte del usuario está en parts[1], pero necesitamos quitar lo que viene después de la pregunta real.
            if len(parts) > 1 and parts[1]:
                user_part_full = parts[1].strip()
                if user_marker_end in user_part_full:
                    user_content = user_part_full.split(user_marker_end, 1)[0].strip()
                else:
                    user_content = user_part_full # Tomar todo si el marcador de respuesta no está
            else: # No debería pasar si system_marker_end está, pero por si acaso
                user_content = "" 
            
            logger.debug(f"  Prompt dividido: System content (len {len(system_content)}): '{system_content[:100]}...', User content (len {len(user_content)}): '{user_content[:100]}...'")
        else:
            logger.debug("  Delimitador para system content ('**Pregunta del Usuario:**') no encontrado. Todo el prompt se usará como 'user_content'.")
            # system_content ya es "" y user_content es prompt_from_builder.strip()
    except Exception as e_parse_prompt:
        logger.warning(f"  Advertencia: Ocurrió un error al intentar parsear el prompt para system/user: {e_parse_prompt}. Se usará el prompt completo como user_content.", exc_info=True)
        system_content = "" # Resetear por si acaso
        user_content = prompt_from_builder.strip()


    messages: List[Dict[str, str]] = []
    if system_content: # Solo añadir system message si tiene contenido
        messages.append({"role": "system", "content": system_content})
    
    if not user_content: # user_content no debería estar vacío después de la lógica anterior
        logger.error(f"  Error Crítico: El contenido del usuario (user_content) está vacío después del parseo. Prompt original (preview): '{prompt_from_builder[:100]}...'")
        return "Error interno: La pregunta del usuario resultó vacía después del procesamiento."
        
    messages.append({"role": "user", "content": user_content})

    payload = {
        "model": openrouter_model_id,
        "messages": messages,
        "max_tokens": llm_max_t,
        "temperature": llm_temp,
        "stream": False # No estamos usando streaming aquí
        # Puedes añadir otros parámetros como "top_p", "presence_penalty", etc. si es necesario
    }

    logger.info(f"  Enviando solicitud a OpenRouter. Modelo: '{openrouter_model_id}', Temp: {llm_temp}, MaxTokens: {llm_max_t}.")
    # Loguear el payload de mensajes es muy útil
    logger.debug(f"  Payload messages para OpenRouter: {json.dumps(messages, ensure_ascii=False, indent=2)}")
    # Loguear el payload completo (sin API key) también puede ser útil si se sospecha de otros parámetros
    payload_for_log = payload.copy() # No loguear la API Key si estuviera en el payload (no está aquí)
    logger.debug(f"  Payload completo para OpenRouter (sin API key implícita): {json.dumps(payload_for_log, ensure_ascii=False, indent=2)}")


    try:
        # La URL completa es base_url (del cliente) + CHAT_COMPLETIONS_ENDPOINT_PATH
        response = await _llm_client_instance.post(CHAT_COMPLETIONS_ENDPOINT_PATH, headers=headers, json=payload)
        
        logger.debug(f"  Respuesta HTTP recibida de OpenRouter. Status: {response.status_code}")
        response.raise_for_status() # Lanza HTTPStatusError si status >= 400
        
        response_data = response.json()
        # logger.debug(f"  Respuesta JSON completa de OpenRouter: {json.dumps(response_data, ensure_ascii=False, indent=2)}") # Loguear JSON completo puede ser muy verboso

        # Extraer el contenido del mensaje de la respuesta
        if response_data.get("choices") and isinstance(response_data["choices"], list) and len(response_data["choices"]) > 0:
            first_choice = response_data["choices"][0]
            if isinstance(first_choice, dict) and first_choice.get("message") and \
               isinstance(first_choice["message"], dict) and "content" in first_choice["message"] and \
               isinstance(first_choice["message"]["content"], str):
                
                ai_response_text = first_choice["message"]["content"].strip()
                finish_reason = first_choice.get("finish_reason", "N/A")
                logger.info(f"  Respuesta de OpenRouter procesada exitosamente. Finish reason: '{finish_reason}'. Respuesta (preview): '{ai_response_text[:150]}...'")
                
                # Aquí podrías añadir lógica para manejar diferentes finish_reasons si es necesario
                # ej. if finish_reason == "length": logger.warning("  Respuesta truncada por max_tokens.")
                
                return ai_response_text
            else:
                logger.warning(f"  Estructura inesperada en 'choices[0].message' o 'content' en la respuesta de OpenRouter. Choice[0]: {first_choice}")
        else:
            logger.warning(f"  La respuesta de OpenRouter no contiene 'choices' válidas o la lista está vacía. Respuesta Data: {response_data}")
        
        # Si no se pudo extraer la respuesta por estructura inesperada
        return "Error: El modelo LLM no generó una respuesta con el formato esperado."

    except httpx.HTTPStatusError as e_status:
        error_body_text = "No se pudo leer el cuerpo del error HTTP."
        try:
            # Intentar leer el cuerpo de la respuesta de error de forma asíncrona
            error_response_content = await e_status.response.aread()
            error_body_text = error_response_content.decode(errors='replace') # Decodificar bytes a string
        except Exception as e_read_body:
            logger.error(f"  Error adicional al intentar leer el cuerpo de la respuesta de error HTTP de OpenRouter: {e_read_body}")
        
        logger.error(
            f"  Error HTTP de OpenRouter: Status Code {e_status.response.status_code}. "
            f"URL: {e_status.request.url}. "
            f"Cuerpo de la Respuesta de Error (preview): {error_body_text[:500]}...", # Loguear solo una preview
            exc_info=False # El traceback de HTTPStatusError no es tan útil como el cuerpo del error
        )
        # Devolver un mensaje de error más informativo al usuario/sistema
        return f"Error de comunicación con el servicio LLM (código {e_status.response.status_code}). Por favor, revisa los logs para más detalles."
    
    except httpx.TimeoutException as e_timeout:
        logger.error(f"  Timeout al llamar a OpenRouter. URL: {e_timeout.request.url if e_timeout.request else 'N/A'}. Error: {e_timeout}", exc_info=True)
        return "Error: La solicitud al servicio LLM excedió el tiempo de espera."
    
    except httpx.RequestError as e_req: # Otros errores de red (DNS, conexión rechazada, etc.)
        logger.error(f"  Error de red/solicitud al llamar a OpenRouter. URL: {e_req.request.url if e_req.request else 'N/A'}. Error: {e_req}", exc_info=True)
        return "Error de red al contactar el servicio LLM. Verifica tu conexión y la disponibilidad del servicio."
    
    except json.JSONDecodeError as e_json:
        # Esto podría pasar si la respuesta no es JSON válido a pesar de un status 200
        logger.error(f"  Error al decodificar la respuesta JSON de OpenRouter. Status: {response.status_code if 'response' in locals() else 'N/A'}. Error: {e_json}", exc_info=True)
        # logger.debug(f"   Contenido que falló la decodificación JSON: {response.text if 'response' in locals() else 'N/A'}")
        return "Error: La respuesta del servicio LLM no pudo ser interpretada (formato JSON inválido)."

    except Exception as e_unexpected: # Captura cualquier otra excepción no prevista
        logger.error(f"  Error inesperado y no manejado en get_llm_response (OpenRouter): {e_unexpected}", exc_info=True)
        return "Error inesperado al procesar la respuesta del LLM."