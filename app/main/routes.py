# app/main/routes.py
from fastapi import APIRouter, Query, Depends, Request, HTTPException, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import json
import os

# Importar la instancia 'settings' y la función 'get_db_session'
from app.core.config import settings # Importa la instancia settings ya inicializada
from app.core.database import get_db_session # NOMBRE CORRECTO de la dependencia de BD
from app.main.webhook_handler import process_webhook_payload
from app.utils.logger import logger

router = APIRouter()

# Acceder al token de verificación desde el objeto settings
# Asegúrate de que 'WHATSAPP_VERIFY_TOKEN' sea el nombre del atributo en tu clase Settings
# que se popula desde la variable de entorno VERIFY_TOKEN.
if settings and hasattr(settings, 'WHATSAPP_VERIFY_TOKEN'):
    VERIFY_TOKEN_FROM_SETTINGS = settings.WHATSAPP_VERIFY_TOKEN
else:
    VERIFY_TOKEN_FROM_SETTINGS = None # Fallback si settings o el atributo no están
    logger.error("CRÍTICO [routes.py]: No se pudo cargar WHATSAPP_VERIFY_TOKEN desde settings. La verificación del Webhook fallará.")


@router.get("/", tags=["Root"])
async def read_root():
    # Este endpoint es opcional, principalmente para pruebas de que la app está viva.
    port = os.getenv("WEBSITES_PORT", "Puerto no definido (revisar WEBSITES_PORT en Azure App Service)")
    db_status = "desconocido"
    rag_status = "desconocido"
    if hasattr(Request, 'app') and hasattr(Request.app.state, 'is_db_ready'): # Chequeo más seguro
        db_status = "lista" if Request.app.state.is_db_ready else "no_lista"
    if hasattr(Request, 'app') and hasattr(Request.app.state, 'is_rag_ready'):
        rag_status = "listo" if Request.app.state.is_rag_ready else "no_listo"
        
    return {
        "project_name": getattr(settings, 'PROJECT_NAME', 'Chatbot API'),
        "version": getattr(settings, 'PROJECT_VERSION', 'N/A'),
        "message": "API del Chatbot Multimarca está activa.",
        "database_status": db_status,
        "rag_status": rag_status,
        "expected_azure_port": port,
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@router.get("/webhook", response_class=PlainTextResponse, tags=["Webhook Verification"])
async def verify_webhook_route(
    # Los parámetros vienen de la query de la URL, FastAPI los mapea
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token") # Este es el token que envía Meta
):
    logger.info(f"GET /webhook recibido para verificación. Mode: '{hub_mode}', Token Enviado: '{hub_verify_token}', Challenge: '{hub_challenge}'")

    if not VERIFY_TOKEN_FROM_SETTINGS: # Usar la variable cargada de settings
        logger.error("VERIFY_TOKEN no configurado en la aplicación. No se puede verificar el webhook.")
        # Devolver 500 podría ser apropiado aquí ya que es un error de config del servidor
        raise HTTPException(status_code=500, detail="Error de configuración del servidor: Token de verificación no definido.")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN_FROM_SETTINGS:
        if hub_challenge:
            logger.info(f"VERIFICACIÓN DE WEBHOOK EXITOSA. Devolviendo Challenge: '{hub_challenge}'")
            return PlainTextResponse(content=hub_challenge) # Devolver solo el challenge
        else:
            logger.error("Verificación de Webhook fallida: Falta 'hub.challenge' en la solicitud de Meta.")
            raise HTTPException(status_code=400, detail="Solicitud de verificación inválida: Falta 'hub.challenge'.")
    elif hub_mode == "subscribe": # El modo es correcto pero el token no
        logger.warning(f"VERIFICACIÓN DE WEBHOOK FALLIDA: Token inválido. Recibido de Meta: '{hub_verify_token}', Esperado: '****{VERIFY_TOKEN_FROM_SETTINGS[-4:] if VERIFY_TOKEN_FROM_SETTINGS else ''}'.")
        raise HTTPException(status_code=403, detail="Token de verificación inválido.") # 403 Forbidden es apropiado
    else: # Modo incorrecto o faltan otros parámetros
        logger.warning(f"VERIFICACIÓN DE WEBHOOK FALLIDA: Modo incorrecto ('{hub_mode}') o parámetros faltantes.")
        raise HTTPException(status_code=400, detail="Modo o parámetros de verificación inválidos.")

@router.post("/webhook", tags=["Webhook Messages"])
async def receive_webhook_route(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session) # Cambiado nombre de var para claridad, sigue siendo AsyncSession
):
    logger.info("POST /webhook: Solicitud de mensaje entrante recibida.")
    
    payload_dict: Dict[str, Any]
    try:
        payload_dict = await request.json()
        # Loguear solo una parte del payload para no llenar los logs, o usar un filtro si es sensible
        logger.debug(f"  Payload JSON recibido (preview): {json.dumps(payload_dict, indent=2, ensure_ascii=False)[:1000]}...")
    except json.JSONDecodeError as json_err:
        raw_body_content = "No se pudo leer el cuerpo crudo."
        try:
            raw_body_bytes = await request.body()
            raw_body_content = raw_body_bytes.decode(errors='replace')[:500] # Preview del cuerpo crudo
        except Exception as body_read_err:
            logger.debug(f"  Error adicional al intentar leer el cuerpo crudo: {body_read_err}")
        logger.error(f"Error al parsear JSON del webhook: {json_err}. Cuerpo crudo (preview): {raw_body_content}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Payload JSON inválido: {str(json_err)}")
    except Exception as e_read_req:
        logger.error(f"Error inesperado al obtener JSON del request: {e_read_req}", exc_info=True)
        raise HTTPException(status_code=400, detail="Error al leer el cuerpo de la solicitud.")

    try:
        # Llamar a la función que maneja la lógica principal del webhook
        await process_webhook_payload(payload=payload_dict, db_session=db_session, request=request)
        logger.info("POST /webhook: Payload procesado exitosamente por process_webhook_payload.")
        # Meta espera un 200 OK para confirmar la recepción. El contenido de la respuesta no es crucial para ellos aquí.
        return {"status": "success", "message": "Evento de webhook recibido y aceptado para procesamiento."}

    except HTTPException as http_exc_from_processing:
        # Si process_webhook_payload lanza una HTTPException, relanzarla para que FastAPI la maneje.
        logger.warning(f"POST /webhook: HTTPException durante process_webhook_payload: {http_exc_from_processing.detail}")
        raise http_exc_from_processing
    except Exception as e_processing:
        logger.error(
            f"POST /webhook: Error inesperado y no manejado durante la ejecución de process_webhook_payload: {e_processing}",
            exc_info=True
        )
        # CRÍTICO: Devolver 200 OK a Meta incluso si hay un error interno en nuestro procesamiento.
        # Esto evita que Meta deshabilite el webhook por fallos repetidos de nuestro lado.
        # El error ya está logueado para nuestra revisión interna.
        return {"status": "error_during_processing", "message": "Evento recibido, pero ocurrió un error interno durante el procesamiento detallado."}