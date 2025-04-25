# app/api/meta.py
import httpx # Usar httpx que es compatible con async y viene con fastapi[all]
from typing import Union, Dict, List, Any, Optional
from app.core.config import settings # Importar la instancia de configuración
from app.utils.logger import logger

# Considera usar una versión más específica o leerla de config si cambia a menudo
BASE_URL = "https://graph.facebook.com/v22.0" # Ejemplo, usa la versión actual recomendada

# Crear un cliente httpx asíncrono reutilizable
# Ajusta timeouts según necesidad
async_client = httpx.AsyncClient(timeout=20.0)

async def send_whatsapp_message(
    to: str,
    message_payload: Union[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Envía mensajes a través de WhatsApp Business API usando httpx.
    Soporta texto simple y payloads de diccionarios (ej. para interactivos).
    """
    # --- Usar los nombres de atributo definidos en la clase Settings ---
    access_token = settings.whatsapp_access_token
    phone_number_id = settings.whatsapp_phone_number_id
    # ------------------------------------------------------------------

    if not access_token or not phone_number_id:
        logger.error("Configuración de WhatsApp incompleta (WHATSAPP_ACCESS_TOKEN o WHATSAPP_PHONE_NUMBER_ID en .env)")
        return None

    if not to or not isinstance(to, str):
        logger.error(f"Número de destinatario WhatsApp inválido: {to}")
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}/{phone_number_id}/messages"
    recipient_waid = to.replace("+", "")

    # Construir data basado en el tipo de payload
    data: Dict[str, Any]
    if isinstance(message_payload, str): # Mensaje de texto simple
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_waid,
            "type": "text",
            "text": {"preview_url": False, "body": message_payload}
        }
    elif isinstance(message_payload, dict): # Payload como diccionario (ej. interactivo)
        # Asumimos que el diccionario ya tiene la estructura correcta que espera la API
        # Ej: {"type": "interactive", "interactive": {...}}
        # Ej: {"type": "template", "template": {...}}
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_waid,
            **message_payload # Desempaquetar el diccionario payload aquí
        }
        # Validación básica del tipo
        if "type" not in data:
             logger.error(f"Payload de diccionario WhatsApp no tiene 'type': {message_payload}")
             return None
    else:
        logger.error(f"Tipo de payload de mensaje WhatsApp no soportado: {type(message_payload)}")
        return None

    try:
        logger.debug(f"Enviando WhatsApp a {recipient_waid}. URL: {url}")
        logger.debug(f"Payload WhatsApp: {data}") # Loguear payload completo para debug
        response = await async_client.post(url, headers=headers, json=data)

        # Loguear respuesta incluso si hay error HTTP
        response_text = "N/A"
        try:
            response_text = await response.aread() # Leer como bytes si puede ser no-JSON
            response_text = response_text.decode('utf-8', errors='replace') # Decodificar
        except Exception:
            logger.warning("No se pudo leer el cuerpo de la respuesta de Meta API.")

        logger.debug(f"Respuesta API WhatsApp status: {response.status_code}, body: {response_text}")
        response.raise_for_status() # Lanza excepción para errores HTTP 4xx/5xx

        response_data = response.json() # Intentar parsear JSON solo si no hubo error HTTP
        logger.info(f"Mensaje WhatsApp enviado a {recipient_waid}. Respuesta API: {response_data}")
        return response_data

    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP de API Meta (WhatsApp) para {recipient_waid}: {e.response.status_code} - {response_text}")
        # Intentar extraer detalles del error si es JSON
        try:
            error_details = e.response.json().get("error", {})
            logger.error(f"Detalles del error Meta: {error_details}")
        except Exception:
            pass # El cuerpo de error podría no ser JSON
        return None
    except httpx.RequestError as e: # Errores de red, timeout, etc.
        logger.error(f"Error de red enviando WhatsApp a {recipient_waid}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado enviando WhatsApp a {recipient_waid}: {e}", exc_info=True)
        return None


async def send_messenger_message(
    to_psid: str,
    message_text: str,
    quick_replies: Optional[List[Dict[str, Any]]] = None # Hacer opcional explícito
) -> Optional[Dict[str, Any]]:
    """
    Envía mensajes de texto (con quick replies opcionales) a través de Facebook Messenger API usando httpx.
    """
    # --- Usar los nombres de atributo definidos en la clase Settings ---
    page_access_token = settings.messenger_page_access_token
    # --------------------------------------------------------------------

    if not page_access_token:
        logger.error("Token de Página de Messenger (MESSENGER_PAGE_ACCESS_TOKEN en .env) faltante.")
        return None

    if not to_psid or not isinstance(to_psid, str):
        logger.error(f"ID de destinatario Messenger inválido: {to_psid}")
        return None

    headers = {
        "Authorization": f"Bearer {page_access_token}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}/me/messages" # Endpoint para enviar

    # Construir payload base
    payload: Dict[str, Any] = {
        "recipient": {"id": to_psid},
        "messaging_type": "RESPONSE",
        "message": {"text": message_text}
    }

    # Añadir quick replies si existen
    if quick_replies:
        valid_qrs = []
        for qr in quick_replies:
            if isinstance(qr, dict) and qr.get("title"):
                 valid_qrs.append({
                     "content_type": "text",
                     "title": qr["title"][:20], # Límite de caracteres FB
                     "payload": qr.get("payload", qr["title"]) # Usar título como payload si no se especifica
                 })
            else:
                 logger.warning(f"Quick reply inválido ignorado: {qr}")
        if valid_qrs:
             payload["message"]["quick_replies"] = valid_qrs

    try:
        logger.debug(f"Enviando Messenger a {to_psid}.")
        logger.debug(f"Payload Messenger: {payload}")
        response = await async_client.post(url, headers=headers, json=payload)

        # Loguear respuesta
        response_text = "N/A"
        try:
            response_text = (await response.aread()).decode('utf-8', errors='replace')
        except Exception:
             logger.warning("No se pudo leer el cuerpo de la respuesta de Meta API (Messenger).")

        logger.debug(f"Respuesta API Messenger status: {response.status_code}, body: {response_text}")
        response.raise_for_status()

        response_data = response.json()
        logger.info(f"Mensaje Messenger enviado a {to_psid}. Respuesta API: {response_data}")
        return response_data

    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP de API Meta (Messenger) para {to_psid}: {e.response.status_code} - {response_text}")
        try:
            error_details = e.response.json().get("error", {})
            logger.error(f"Detalles del error Meta: {error_details}")
        except Exception:
            pass
        return None
    except httpx.RequestError as e:
        logger.error(f"Error de red enviando Messenger a {to_psid}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado enviando Messenger a {to_psid}: {e}", exc_info=True)
        return None