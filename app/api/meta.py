# app/api/meta.py
# app/api/meta.py
import httpx
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Union, Dict, List, Any, Optional

from app.core.config import settings
from app.utils.logger import logger

# Crear instancia global de TokenManager al inicio
token_manager = None
http_client_meta = None

class TokenManager:
    def __init__(self):
        self.token: Optional[str] = None
        self.expiration: Optional[datetime] = None 
        self.phone_number_id: Optional[str] = None
        self.messenger_token: Optional[str] = None
        self.messenger_expiration: Optional[datetime] = None
        self._load_initial_tokens()

    def _load_initial_tokens(self):
        if not settings:
            logger.critical("TokenManager: Settings no disponibles al inicializar.")
            return
            
        # --- CORRECCIONES AQUÍ ---
        if settings.WHATSAPP_ACCESS_TOKEN: # Usar MAYÚSCULAS
            self.token = settings.WHATSAPP_ACCESS_TOKEN
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1) 
            logger.info(f"TokenManager: WhatsApp token inicial cargado desde settings. Validez asumida por ~1 hora.")
            logger.debug(f"TokenManager (inicial): WhatsApp token: '{self.token[:10] if self.token else 'N/A'}...', Len: {len(self.token) if self.token else 0}")
        else:
            logger.warning("TokenManager: WHATSAPP_ACCESS_TOKEN no encontrado en settings.")

        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID # Usar MAYÚSCULAS
        if not self.phone_number_id:
            logger.warning("TokenManager: WHATSAPP_PHONE_NUMBER_ID no encontrado en settings.")

        if settings.MESSENGER_PAGE_ACCESS_TOKEN: # Usar MAYÚSCULAS
            self.messenger_token = settings.MESSENGER_PAGE_ACCESS_TOKEN
            self.messenger_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
            logger.info("TokenManager: Messenger token inicial cargado desde settings.")
        else:
            logger.warning("TokenManager: MESSENGER_PAGE_ACCESS_TOKEN no encontrado en settings.")
        # --- FIN CORRECCIONES ---

    def get_whatsapp_token(self) -> Optional[str]:
        if not settings: 
            logger.error("TokenManager: get_whatsapp_token llamado pero settings no está disponible.")
            return None

        # --- CORRECCIONES AQUÍ ---
        if settings.WHATSAPP_ACCESS_TOKEN and self.token != settings.WHATSAPP_ACCESS_TOKEN:
            logger.info("TokenManager: WhatsApp token en settings ha cambiado, actualizando token interno.")
            self.token = settings.WHATSAPP_ACCESS_TOKEN
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1) 

        if self.token and self.expiration and datetime.now(timezone.utc) < self.expiration:
            logger.debug("TokenManager: Devolviendo token de WhatsApp existente y válido.")
            return self.token
        
        if self.token and self.expiration: # Expiró o está a punto de expirar
            logger.warning(f"TokenManager: Token de WhatsApp ha expirado (según lógica interna) o está ausente y settings lo tiene.")
            if settings.WHATSAPP_ACCESS_TOKEN:
                self.token = settings.WHATSAPP_ACCESS_TOKEN
                self.expiration = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.info(f"TokenManager: Token de WhatsApp (re)cargado de settings.")
                return self.token
            else: 
                logger.error("TokenManager: Token de WhatsApp expirado y no se pudo recargar de settings (WHATSAPP_ACCESS_TOKEN no presente).")
                self.token = None 
                self.expiration = None
                return None
        
        if not self.token and settings.WHATSAPP_ACCESS_TOKEN:
            logger.info("TokenManager: Token interno era None, cargando de settings.")
            self.token = settings.WHATSAPP_ACCESS_TOKEN
            self.expiration = datetime.now(timezone.utc) + timedelta(hours=1)
            return self.token
        # --- FIN CORRECCIONES ---
            
        logger.error("TokenManager: No hay token de WhatsApp válido disponible y no se pudo obtener de settings.")
        return None

    def get_phone_number_id(self) -> Optional[str]:
        if not settings: return None
        # --- CORRECCIÓN AQUÍ ---
        if settings.WHATSAPP_PHONE_NUMBER_ID and self.phone_number_id != settings.WHATSAPP_PHONE_NUMBER_ID:
             self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
             logger.info(f"TokenManager: WHATSAPP_PHONE_NUMBER_ID actualizado/cargado desde settings: {self.phone_number_id}")
        # --- FIN CORRECCIÓN ---
        return self.phone_number_id

    def invalidate_whatsapp_token(self):
        logger.warning("TokenManager: Invalidando token de WhatsApp actual (probablemente debido a error 401/403 de API).")
        self.token = None
        self.expiration = None

    def get_messenger_token(self) -> Optional[str]:
        if not settings: return None
        # --- CORRECCIÓN AQUÍ ---
        if settings.MESSENGER_PAGE_ACCESS_TOKEN and self.messenger_token != settings.MESSENGER_PAGE_ACCESS_TOKEN:
            self.messenger_token = settings.MESSENGER_PAGE_ACCESS_TOKEN
            self.messenger_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
        # --- FIN CORRECCIÓN ---
        
        if self.messenger_token and self.messenger_expiration and datetime.now(timezone.utc) < self.messenger_expiration:
            return self.messenger_token
        # ... (lógica de expiración y recarga para messenger token si es necesaria) ...
        logger.error("TokenManager: No hay token de Messenger válido disponible.")
        return None


# Inicializar el cliente HTTP y el token_manager
def init_meta_client():
    global token_manager, http_client_meta
    
    # Inicializar TokenManager
    token_manager = TokenManager()
    
    # Configurar cliente HTTP para la API de Meta
    _BASE_URL_META_CLIENT = "https://graph.facebook.com"
    _HTTP_TIMEOUT_META_CLIENT = 30.0
    
    if settings and hasattr(settings, 'http_client_timeout'):
        _HTTP_TIMEOUT_META_CLIENT = float(settings.http_client_timeout)
    
    http_client_meta = httpx.AsyncClient(
        base_url=f"{_BASE_URL_META_CLIENT}/{settings.META_API_VERSION}",
        timeout=_HTTP_TIMEOUT_META_CLIENT,
        headers={"Content-Type": "application/json"}
    )
    
    logger.info(f"Cliente HTTP para Meta API inicializado. Base URL: {http_client_meta.base_url}")

# Inicializar el cliente al importar el módulo
if settings:
    init_meta_client()
else:
    logger.warning("No se pudo inicializar el cliente HTTP de Meta: settings no disponible")

async def send_whatsapp_message(
    to: str, 
    message_payload: Union[str, Dict[str, Any]],
    interactive_buttons: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    
    if http_client_meta is None:
        logger.error("send_whatsapp_message: Cliente HTTP para Meta API no inicializado. No se puede enviar mensaje.")
        return {"error": True, "status_code": "CLIENT_NOT_INITIALIZED", "details": "HTTP client for Meta not ready."}

    access_token = token_manager.get_whatsapp_token()
    phone_number_id = token_manager.get_phone_number_id()
    
    if not access_token:
        logger.error("send_whatsapp_message: No se pudo obtener el token de acceso de WhatsApp.")
        return {"error": True, "status_code": "TOKEN_ERROR", "details": "Missing WhatsApp Access Token."}
    if not phone_number_id:
        logger.error("send_whatsapp_message: No se pudo obtener el WhatsApp Phone Number ID.")
        return {"error": True, "status_code": "CONFIG_ERROR", "details": "Missing WhatsApp Phone Number ID."}

    # Asegurar que el 'to' no tenga '+' u otros caracteres que Meta no espera para el WABA ID
    recipient_waid = re.sub(r'\D', '', to)  # Quita todo lo que no sea dígito
    
    # Usar la versión de la API desde la configuración del cliente HTTP
    # La URL base ya incluye la versión correcta
    url_path = f"/{phone_number_id}/messages"
    
    data_to_send: Dict[str, Any]

    if interactive_buttons and isinstance(interactive_buttons, list) and len(interactive_buttons) > 0:
        logger.info(f"Preparando mensaje interactivo con botones para {recipient_waid}")
        # ... (tu lógica de formateo de botones, que parece buena) ...
        api_buttons_formatted = []
        for btn_def in interactive_buttons:
            if isinstance(btn_def, dict) and btn_def.get("type") == "reply" and \
               isinstance(btn_def.get("reply"), dict) and \
               isinstance(btn_def["reply"].get("id"), str) and \
               isinstance(btn_def["reply"].get("title"), str):
                
                button_title = btn_def["reply"]["title"][:20] # Truncar a 20 chars
                button_id = btn_def["reply"]["id"][:256]     # Truncar a 256 chars
                api_buttons_formatted.append({"type": "reply", "reply": {"id": button_id, "title": button_title}})
            else:
                logger.error(f"Formato de botón interactivo no válido omitido: {btn_def}")

        if not api_buttons_formatted:
            logger.error(f"No se pudieron formatear botones válidos para {recipient_waid}. Intentando enviar como texto simple.")
            text_fallback = message_payload if isinstance(message_payload, str) else \
                            (message_payload.get("text", "Se produjo un error al mostrar las opciones.") if isinstance(message_payload, dict) else "Error.")
            # Evitar recursión infinita si message_payload es complejo y no string/dict con text
            if isinstance(text_fallback, str):
                return await send_whatsapp_message(to, text_fallback) 
            else:
                logger.error("Fallback a texto simple falló porque el payload no es string/dict con 'text'. No se envía mensaje.")
                return {"error": True, "status_code": "PAYLOAD_ERROR", "details": "Invalid payload for text fallback."}


        body_text_interactive = (message_payload if isinstance(message_payload, str) else
                                 message_payload.get("text", "Por favor, selecciona una opción:") if isinstance(message_payload, dict) else
                                 "Por favor, selecciona una opción:")

        data_to_send = {
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient_waid,
            "type": "interactive",
            "interactive": {"type": "button", "body": {"text": body_text_interactive},"action": {"buttons": api_buttons_formatted}}
        }
    else: 
        text_content_simple = (message_payload if isinstance(message_payload, str) else
                               message_payload.get("text") if isinstance(message_payload, dict) and "text" in message_payload else
                               str(message_payload)) # Fallback a convertir a string
        
        logger.info(f"Preparando mensaje de texto simple para {recipient_waid}: '{text_content_simple[:70]}...'")
        data_to_send = {
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient_waid,
            "type": "text", "text": {"preview_url": False, "body": text_content_simple}
        }

    logger.debug(f"Enviando POST a Meta API. Path con versión: {url_path}")
    logger.debug(f"Payload de WhatsApp a enviar: {json.dumps(data_to_send, ensure_ascii=False, indent=2)}")

    try:
        response = await http_client_meta.post(url_path, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=data_to_send)
        # Loguear siempre la respuesta de Meta, incluso si no es un error de status
        response_status = response.status_code
        response_content_text = "No se pudo leer contenido de respuesta."
        try:
            response_content_bytes = await response.aread()
            response_content_text = response_content_bytes.decode(errors='replace')
        except Exception as e_read_resp:
            logger.warning(f"No se pudo leer/decodificar contenido de respuesta de Meta: {e_read_resp}")

        logger.debug(f"Respuesta de Meta API: Status={response_status}, Contenido (preview)='{response_content_text[:300]}...'")

        response.raise_for_status() # Lanza error para >= 400
        
        try:
            response_data = json.loads(response_content_text) # Parsear el texto que ya leímos
            logger.info(f"Mensaje de WhatsApp enviado exitosamente a {recipient_waid}. Respuesta de Meta (parseada): {response_data}")
            return response_data
        except json.JSONDecodeError:
            logger.error(f"Respuesta exitosa (status {response_status}) de Meta pero no es JSON válido: '{response_content_text}'")
            return {"error": False, "status_code": response_status, "details": "Success status but invalid JSON response from Meta.", "raw_response": response_content_text}

    except httpx.HTTPStatusError as e_status:
        # El cuerpo del error ya fue logueado arriba si response_content_text se leyó
        logger.error(f"Error HTTP ({e_status.response.status_code}) al enviar mensaje de WhatsApp a {recipient_waid}. URL: {e_status.request.url}.")
        
        error_json_details = {}
        try:
            # Intenta parsear response_content_text (que ya contiene el cuerpo del error)
            error_json_details = json.loads(response_content_text) 
        except json.JSONDecodeError: # Si el cuerpo del error no es JSON
            logger.warning("El cuerpo del error HTTP de Meta no es JSON válido.")
            error_json_details = {"raw_error_body": response_content_text}
        
        # Chequeo específico para invalidar token
        error_code_from_meta = error_json_details.get("error", {}).get("code")
        if error_code_from_meta == 190: # Subcódigo para token inválido/expirado
            logger.warning(f"Error de token de Meta (código {error_code_from_meta}). Invalidando token de WhatsApp.")
            token_manager.invalidate_whatsapp_token()
        
        return {"error": True, "status_code": e_status.response.status_code, "details_dict": error_json_details, "raw_body": response_content_text}
    
    except httpx.RequestError as e_req: # Errores de red, DNS, etc.
        logger.error(f"Error de red al enviar mensaje de WhatsApp a {recipient_waid}: {e_req}", exc_info=True)
        return {"error": True, "status_code": "NETWORK_ERROR", "details": str(e_req)}
    except Exception as e_general: # Cualquier otra excepción
        logger.error(f"Error inesperado al enviar mensaje de WhatsApp a {recipient_waid}: {e_general}", exc_info=True)
        return {"error": True, "status_code": "UNKNOWN_SEND_ERROR", "details": str(e_general)}


async def send_messenger_message(
    recipient_id: str,
    message_text: str,
    quick_replies: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    # (Mantén tu lógica para Messenger, similar a WhatsApp para logging y errores)
    # ...
    logger.warning("Función send_messenger_message no completamente implementada con el nuevo logging.")
    return None