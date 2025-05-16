# app/main/routes.py
from fastapi import APIRouter, Query, Depends, Request, HTTPException, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import json # Para el manejo de JSON si es necesario

from app.core.config import settings
from app.core.database import get_db_session
from app.main.webhook_handler import process_webhook_payload # Ruta al handler
from app.utils.logger import logger

router = APIRouter()

VERIFY_TOKEN = settings.webhook_verify_token

if not VERIFY_TOKEN:
    logger.critical(
        "CRÍTICO: WEBHOOK_VERIFY_TOKEN no está configurado. La verificación del webhook fallará."
    )

@router.get("/webhook", response_class=PlainTextResponse, tags=["Webhook"])
async def verify_webhook_route(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    logger.debug(f"GET /webhook. Mode: '{hub_mode}', Token: '{hub_verify_token}', Challenge: '{hub_challenge}'")

    if not VERIFY_TOKEN:
        logger.error("VERIFY_TOKEN no disponible. No se puede verificar webhook.")
        raise HTTPException(status_code=500, detail="Error de configuración del servidor.")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        if hub_challenge:
            logger.info(f"VERIFICACIÓN WEBHOOK EXITOSA. Challenge: '{hub_challenge}'")
            return PlainTextResponse(content=hub_challenge)
        else:
            logger.error("Verificación Webhook: Falta 'hub.challenge'.")
            raise HTTPException(status_code=400, detail="Falta 'hub.challenge'.")
    elif hub_mode == "subscribe":
        logger.warning(f"VERIFICACIÓN WEBHOOK FALLIDA: Token inválido. Recibido: '{hub_verify_token}'")
        raise HTTPException(status_code=403, detail="Token de verificación inválido.")
    else:
        logger.warning(f"VERIFICACIÓN WEBHOOK FALLIDA: Modo incorrecto o parámetros faltantes. Mode: '{hub_mode}'")
        raise HTTPException(status_code=400, detail="Modo o parámetros inválidos.")

@router.post("/webhook", tags=["Webhook"])
async def receive_webhook_route(
    request: Request,
    db_session_dep: AsyncSession = Depends(get_db_session) # Renombrar la variable de dependencia para evitar conflicto
    # payload_body: Dict[str, Any] = Body(...) # Alternativa
):
    logger.info("POST /webhook recibido. Procesando payload...")
    
    payload: Dict[str, Any]
    try:
        payload = await request.json()
        logger.debug(f"Payload JSON recibido: {json.dumps(payload, indent=2, ensure_ascii=False)[:1000]}...") # Limitar log y asegurar no-ascii
    except json.JSONDecodeError as json_error: # Ser específico con la excepción
        logger.error(f"Error al parsear JSON del webhook: {json_error}", exc_info=True)
        raw_body_for_log = "No se pudo leer el cuerpo crudo."
        try:
            raw_body = await request.body()
            raw_body_for_log = raw_body.decode(errors='ignore')[:500]
        except Exception as body_error:
            logger.debug(f"No se pudo leer el cuerpo crudo para logging: {body_error}")
        logger.debug(f"Cuerpo crudo (si se pudo leer, primeros 500 chars): {raw_body_for_log}")
        raise HTTPException(status_code=400, detail=f"Payload JSON inválido: {str(json_error)}")
    except Exception as e_req: # Otros errores al leer request
        logger.error(f"Error al obtener JSON del request: {e_req}", exc_info=True)
        raise HTTPException(status_code=400, detail="Error al leer el cuerpo de la solicitud.")

    try:
        # --- CORRECCIÓN AQUÍ ---
        # Llamar a process_webhook_payload con el nombre de parámetro db_session
        await process_webhook_payload(payload=payload, db_session=db_session_dep, request=request)

        logger.info("Payload procesado exitosamente por process_webhook_payload.")
        return {"status": "success", "message": "Evento de webhook recibido y aceptado."}

    except HTTPException:
        raise # Relanzar HTTPExceptions para que FastAPI las maneje
    except Exception as processing_error:
        logger.error(
            f"Error inesperado durante la ejecución de process_webhook_payload: {processing_error}",
            exc_info=True
        )
        # Devolver 200 OK a Meta para evitar reintentos y desactivación del webhook.
        return {"status": "error_processing_event", "message": "Evento recibido, error interno durante procesamiento."}