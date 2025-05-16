# app/api/meta.py
import httpx
import json # Para loggear el payload de forma legible
from datetime import datetime, timezone, timedelta 
from typing import Union, Dict, List, Any, Optional

# Usar la instancia 'settings' global que se carga en config.py
# Esto evita problemas si get_settings() se llama antes de que _settings_instance esté lista.
from app.core.config import settings # Importar la instancia global
from app.utils.logger import logger


class TokenManager:
    def __init__(self):
        self.token: Optional[str] = None
        self.expiration: Optional[datetime] = None 
        self.phone_number_id: Optional[str] = None
        self.messenger_token: Optional[str] = None
        self.messenger_expiration: Optional[datetime] = None
        self._load_initial_tokens()

    def _load_initial_tokens(self):
        # 'settings' ya es la instancia cargada
        if not settings:
            logger.critical("TokenManager: Settings no disponibles al inicializar.")
            return # No se puede continuar si settings no está cargado
            
        if settings.whatsapp_access_token:
            self.token = settings.whatsapp_access_token
            # Asumir una expiración si no se obtiene de la API (los tokens de usuario suelen durar ~1 hora, los de sistema más)
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1) 
            logger.info(f"TokenManager: WhatsApp token inicial cargado desde settings. Validez asumida por ~1 hora.")
            logger.debug(f"TokenManager (inicial): WhatsApp token cargado. Comienza con: {self.token[:10] if self.token else 'N/A'}..., Longitud: {len(self.token) if self.token else 0}")
        else:
            logger.warning("TokenManager: WHATSAPP_ACCESS_TOKEN no encontrado en settings.")

        self.phone_number_id = settings.whatsapp_phone_number_id
        if not self.phone_number_id:
            logger.warning("TokenManager: WHATSAPP_PHONE_NUMBER_ID no encontrado en settings.")

        if settings.messenger_page_access_token:
            self.messenger_token = settings.messenger_page_access_token
            self.messenger_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
            logger.info("TokenManager: Messenger token inicial cargado desde settings.")
        else:
            logger.warning("TokenManager: MESSENGER_PAGE_ACCESS_TOKEN no encontrado en settings.")

    def get_whatsapp_token(self) -> Optional[str]:
        if not settings: return None # No hay settings, no hay token

        # Si el token en settings (leído del .env) es diferente, actualizar.
        # Esto es útil si el .env cambia y la app se recarga (ej. con Uvicorn reload).
        if settings.whatsapp_access_token and self.token != settings.whatsapp_access_token:
            logger.info("TokenManager: El token en settings es diferente. Actualizando token interno.")
            self.token = settings.whatsapp_access_token
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1) 

        if self.token and self.expiration and datetime.now(timezone.utc) < self.expiration:
            return self.token
        elif self.token and self.expiration: # Expiró
            logger.warning(f"TokenManager: Token de WhatsApp ha expirado (según lógica interna).")
            self.token = None 
            if settings.whatsapp_access_token: # Intentar recargar de settings
                self.token = settings.whatsapp_access_token
                self.expiration = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.info(f"TokenManager: Token de WhatsApp recargado de settings tras expiración.")
                return self.token
            logger.error("TokenManager: No se pudo recargar token de WhatsApp tras expiración.")
            return None
        elif not self.token and settings.whatsapp_access_token: # Carga inicial si falló en __init__ pero settings ahora está
            logger.info("TokenManager: Token interno no presente, cargando de settings.")
            self.token = settings.whatsapp_access_token
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1)
            return self.token
            
        logger.error("TokenManager: No hay token de WhatsApp válido disponible.")
        return None

    def get_phone_number_id(self) -> Optional[str]:
        if not settings: return None
        if not self.phone_number_id and settings.whatsapp_phone_number_id: 
             self.phone_number_id = settings.whatsapp_phone_number_id
        return self.phone_number_id

    def invalidate_whatsapp_token(self):
        logger.warning("TokenManager: Invalidando token de WhatsApp actual (probablemente debido a error de API).")
        self.token = None
        self.expiration = None

    def get_messenger_token(self) -> Optional[str]:
        # Lógica similar a get_whatsapp_token para Messenger
        if not settings: return None
        if settings.messenger_page_access_token and self.messenger_token != settings.messenger_page_access_token:
            self.messenger_token = settings.messenger_page_access_token
            self.messenger_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
        
        if self.messenger_token and self.messenger_expiration and datetime.now(timezone.utc) < self.messenger_expiration:
            return self.messenger_token
        # ... (lógica de expiración y recarga para messenger token) ...
        logger.error("TokenManager: No hay token de Messenger válido disponible.")
        return None

token_manager = TokenManager() # Crear una instancia global del manager

# Configurar cliente HTTP para la API de Meta
_BASE_URL_META = f"https://graph.facebook.com/{settings.meta_api_version if settings else 'v19.0'}" 
_HTTP_TIMEOUT_META = 30.0
if settings and hasattr(settings, 'http_client_timeout'):
    _HTTP_TIMEOUT_META = settings.http_client_timeout

try:
    http_client_meta = httpx.AsyncClient(base_url=_BASE_URL_META, timeout=_HTTP_TIMEOUT_META)
    logger.info(f"Cliente HTTP para Meta API inicializado. Base URL: {_BASE_URL_META}, Timeout: {_HTTP_TIMEOUT_META}s")
except Exception as e_client_meta:
    logger.error(f"Error al inicializar el cliente HTTP para Meta API: {e_client_meta}", exc_info=True)
    http_client_meta = None


async def send_whatsapp_message(
    to: str, 
    message_payload: Union[str, Dict[str, Any]], # Puede ser string o dict con 'text'
    interactive_buttons: Optional[List[Dict[str, Any]]] = None # Lista de botones {"type": "reply", "reply": {"id": ..., "title": ...}}
) -> Optional[Dict[str, Any]]:
    
    if http_client_meta is None:
        logger.error("Cliente HTTP para Meta API no inicializado. No se puede enviar mensaje.")
        return {"error": True, "status_code": "CLIENT_NOT_INITIALIZED", "details": "HTTP client for Meta not ready."}

    access_token = token_manager.get_whatsapp_token()
    phone_number_id = token_manager.get_phone_number_id()
    
    if not access_token or not phone_number_id:
        logger.error("Configuración de WhatsApp (token o ID de número de teléfono) incompleta o no disponible.")
        return {"error": True, "status_code": "CONFIG_ERROR", "details": "Missing WhatsApp token or Phone ID."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    recipient_waid = to.replace("+", "")
    api_version = settings.meta_api_version # Usar la versión de settings
    url_path = f"/{phone_number_id}/messages" # Path relativo al base_url del cliente

    data_to_send: Dict[str, Any]

    if interactive_buttons and isinstance(interactive_buttons, list) and len(interactive_buttons) > 0:
        logger.info(f"Preparando mensaje interactivo con botones para {recipient_waid}")
        
        api_buttons_formatted = []
        for btn_def in interactive_buttons:
            # Asumimos que btn_def ya tiene la estructura {"type": "reply", "reply": {"id": ..., "title": ...}}
            # proveniente de state_manager.py
            if isinstance(btn_def, dict) and btn_def.get("type") == "reply" and \
               isinstance(btn_def.get("reply"), dict) and \
               isinstance(btn_def["reply"].get("id"), str) and \
               isinstance(btn_def["reply"].get("title"), str):
                
                button_title = btn_def["reply"]["title"]
                if len(button_title) > 20: # Límite de WhatsApp para títulos de botón
                    logger.warning(f"Título de botón '{button_title}' excede 20 caracteres. Será truncado.")
                    button_title = button_title[:17] + "..."
                
                button_id = btn_def["reply"]["id"]
                if len(button_id) > 256: # Límite de WhatsApp para IDs de botón
                    logger.warning(f"ID de botón '{button_id}' excede 256 caracteres. Será truncado.")
                    button_id = button_id[:256]

                api_buttons_formatted.append({
                    "type": "reply", # Tipo de botón
                    "reply": {"id": button_id, "title": button_title}
                })
            else:
                logger.error(f"Formato de botón interactivo no válido recibido y omitido: {btn_def}")

        if not api_buttons_formatted: # Si ningún botón fue válido
            logger.error(f"No se pudieron formatear botones válidos para {recipient_waid}. Enviando como texto simple.")
            # Fallback a mensaje de texto si los botones no son válidos o la lista está vacía
            text_fallback = message_payload if isinstance(message_payload, str) else \
                            (message_payload.get("text", "Error al mostrar opciones.") if isinstance(message_payload, dict) else "Error.")
            return await send_whatsapp_message(to, text_fallback) # Llamada recursiva sin botones

        # Determinar el texto del cuerpo para el mensaje interactivo
        body_text_interactive = ""
        if isinstance(message_payload, str):
            body_text_interactive = message_payload
        elif isinstance(message_payload, dict) and "text" in message_payload:
            body_text_interactive = message_payload["text"]
        else:
            logger.warning(f"message_payload para interactivo no es string ni dict con 'text': {message_payload}. Usando texto genérico de cuerpo.")
            body_text_interactive = "Por favor, selecciona una opción:" # Un texto genérico si no se provee

        data_to_send = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_waid,
            "type": "interactive",
            "interactive": {
                "type": "button", 
                "body": {"text": body_text_interactive},
                "action": {"buttons": api_buttons_formatted}
            }
        }
    else: # Mensaje de texto simple
        text_content_simple = message_payload if isinstance(message_payload, str) else \
                              (message_payload.get("text") if isinstance(message_payload, dict) and "text" in message_payload else str(message_payload))
        
        logger.info(f"Preparando mensaje de texto simple para {recipient_waid}: '{text_content_simple[:70]}...'")
        data_to_send = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_waid,
            "type": "text",
            "text": {"preview_url": False, "body": text_content_simple}
        }

    logger.debug(f"Enviando solicitud a Meta API. Endpoint: {_BASE_URL_META}{url_path}")
    logger.debug(f"Payload de WhatsApp a enviar: {json.dumps(data_to_send, ensure_ascii=False, indent=2)}")

    try:
        response = await http_client_meta.post(url_path, headers=headers, json=data_to_send)
        response.raise_for_status() 
        response_data = response.json()
        logger.info(f"Mensaje de WhatsApp enviado a {recipient_waid}. Respuesta de Meta: {response_data}")
        return response_data
    except httpx.HTTPStatusError as e_status:
        error_body_text = "No se pudo leer el cuerpo del error."
        try:
            error_body_bytes = await e_status.response.aread()
            error_body_text = error_body_bytes.decode(errors='replace')
        except Exception: pass
        logger.error(f"Error HTTP ({e_status.response.status_code}) al enviar mensaje de WhatsApp a {recipient_waid}. URL: {e_status.request.url}. Cuerpo del error: {error_body_text}")
        if e_status.response.status_code == 400 or e_status.response.status_code == 401 or e_status.response.status_code == 403 : # Errores relacionados con el token o el payload
            error_json = {}
            try: error_json = json.loads(error_body_text)
            except: pass
            if error_json.get("error", {}).get("code") == 190: # Subcódigo para token inválido/expirado
                token_manager.invalidate_whatsapp_token()
        return {"error": True, "status_code": e_status.response.status_code, "details": error_body_text}
    except httpx.RequestError as e_req:
        logger.error(f"Error de red al enviar WhatsApp a {recipient_waid}: {e_req}", exc_info=True)
        return {"error": True, "status_code": "NETWORK_ERROR", "details": str(e_req)}
    except Exception as e_general:
        logger.error(f"Error inesperado enviando WhatsApp a {recipient_waid}: {e_general}", exc_info=True)
        return {"error": True, "status_code": "UNKNOWN_ERROR", "details": str(e_general)}

async def send_messenger_message(
    recipient_id: str,
    message_text: str,
    quick_replies: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    # (Tu lógica para send_messenger_message se mantiene como estaba)
    if http_client_meta is None:
        logger.error("Cliente HTTP para Meta API no inicializado. No se puede enviar mensaje de Messenger.")
        return {"error": True, "status_code": "CLIENT_NOT_INITIALIZED", "details": "HTTP client for Meta not ready."}

    access_token = token_manager.get_messenger_token() 
    if not access_token:
        logger.error("Token de página de Messenger no configurado o no disponible.")
        return None

    api_version = settings.meta_api_version
    url_path = "/me/messages" # Path para mensajes de Messenger
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    # ... (resto de la lógica de send_messenger_message que ya tenías) ...
    payload: Dict[str, Any] = { 
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE", 
        "message": {"text": message_text}
    }
    # ... (lógica de quick_replies) ...
    logger.debug(f"Enviando Messenger a {recipient_id}. Payload: {payload}")
    try:
        response = await http_client_meta.post(url_path, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Mensaje de Messenger enviado a {recipient_id}. Respuesta Meta: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Error enviando Messenger a {recipient_id}: {e}", exc_info=True)
        return None