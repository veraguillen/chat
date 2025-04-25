# app/main/routes.py
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import PlainTextResponse
from app.core.config import settings # Importa tu config
from app.main.webhook_handler import process_webhook_payload # Importa el handler principal
from app.core.database import get_db_session # Importa la dependencia de sesión
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.logger import logger # Importa tu logger
import traceback

# Usa el nombre 'router' o 'bp' consistentemente
router = APIRouter() # Usaremos 'router'

VERIFY_TOKEN = settings.verify_token # Lee desde la config

@router.get("/webhook", response_class=PlainTextResponse, tags=["Webhook"])
async def verify_webhook_route(
    # Usa Query para parámetros GET, el alias es correcto
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Verifica el webhook para WhatsApp y Messenger."""
    logger.debug(f"GET /webhook recibido. Mode: {hub_mode}, Token: {hub_verify_token}, Challenge: {hub_challenge}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        if hub_challenge:
             logger.info(f"VERIFICACIÓN WEBHOOK EXITOSA. Challenge: {hub_challenge}")
             return hub_challenge # FastAPI maneja PlainTextResponse si se especifica en response_class
        else:
              logger.error("Falta hub.challenge en verificación.")
              raise HTTPException(status_code=400, detail="Missing hub.challenge")
    else:
        logger.warning(f"VERIFICACIÓN WEBHOOK FALLIDA. Token recibido: '{hub_verify_token}', Token esperado: '{VERIFY_TOKEN}'")
        raise HTTPException(status_code=403, detail="Invalid verification token")


@router.post("/webhook", tags=["Webhook"])
async def receive_webhook_route(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Recibe notificaciones de webhook de Meta (WhatsApp y Messenger)."""
    # --- (Aquí iría la verificación de firma si la implementas) ---
    # signature = request.headers.get("X-Hub-Signature-256")
    # raw_payload = await request.body()
    # if not verify_signature(raw_payload, signature): # Necesitarías la función verify_signature
    #     raise HTTPException(status_code=403, detail="Invalid signature")
    # payload = await request.json() # Parsear DESPUÉS de verificar firma

    # Si no hay verificación de firma (como ahora):
    try:
        payload = await request.json()
        logger.info(f"POST /webhook recibido.")
        logger.debug(f"Payload: {payload}") # Loguea el payload para debug
    except Exception as e:
         logger.error(f"Error al parsear JSON del webhook: {e}")
         # Es útil loguear el cuerpo raw si falla el JSON
         try:
             raw_body = await request.body()
             logger.debug(f"Raw body: {raw_body.decode()}")
         except Exception:
             logger.debug("No se pudo leer el raw body.")
         raise HTTPException(status_code=400, detail="Invalid JSON payload")

    try:
        # Pasa el payload y la sesión de DB al handler principal
        await process_webhook_payload(payload, db=db)
        # Responde OK a Meta inmediatamente
        return {"status": "success"}
    except Exception as e:
        # Captura errores del process_webhook_payload
        logger.error(f"Error inesperado en la ruta /webhook POST durante process_webhook_payload: {e}\n{traceback.format_exc()}")
        # El rollback de 'db' ocurre en la dependencia get_db_session
        # Responde OK a Meta para evitar reintentos, pero el error queda logueado
        return {"status": "error logged"}