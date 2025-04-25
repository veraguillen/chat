# app/main/webhook_handler.py
from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import traceback
from pydantic import ValidationError

from app.models.webhook_models import WhatsAppPayload, MessengerPayload, WhatsAppMessage, MessagingEvent
from app.models.user_state import UserState
from app.core.database import get_db_session
from app.api.meta import send_whatsapp_message, send_messenger_message
from app.api.deepseek import get_deepseek_response
from app.ai.knowledge_retriever import get_brand_context
from app.ai.prompt_builder import build_deepseek_prompt, BRAND_PROFILES
from app.main.state_manager import (
    get_or_create_user_state,
    update_user_state_db,
    set_user_brand_db,
    get_brand_welcome_message,
    get_initial_brand_selection_message,
    VALID_BRANDS,
    BRAND_SELECTION_MAP
)
from app.utils.logger import logger

RESET_KEYWORDS = {"menu", "menú", "inicio", "reset", "/reset", "/menu", "volver", "cambiar marca", "salir"}

async def handle_whatsapp_message(message: WhatsAppMessage, db: AsyncSession):
    sender_id = None
    platform = "whatsapp"
    user_state_obj = None
    try:
        sender_id = message.from_
        user_state_obj = await get_or_create_user_state(db, sender_id, platform)

        message_type = message.type
        message_text_raw = None
        reset_check_text = None

        if message_type == 'text' and message.text:
            message_text_raw = message.text.body.strip()
            reset_check_text = message_text_raw.lower()
        elif message_type == 'interactive' and message.interactive and message.interactive.type == 'list_reply':
            message_text_raw = message.interactive.list_reply.id.strip()
            reset_check_text = message_text_raw.lower()
            logger.info(f"Recibida respuesta de lista interactiva de {sender_id}: ID='{message_text_raw}'")
        else:
            if message_type not in ['reaction', 'image', 'audio', 'document', 'sticker', 'unknown']:
                logger.warning(f"Tipo de mensaje WhatsApp no procesable: {message_type} de {sender_id}.")
                await send_whatsapp_message(sender_id, "Lo siento, solo puedo procesar mensajes de texto o selecciones de las opciones presentadas.")
            return

        if reset_check_text and reset_check_text in RESET_KEYWORDS:
            logger.info(f"Comando RESET/MENU ('{reset_check_text}') recibido de {platform}:{sender_id}. Reseteando estado.")
            await update_user_state_db(db, user_state_obj, {"current_brand": None, "stage": "selecting_brand"})
            response_to_send = get_initial_brand_selection_message()
            await send_whatsapp_message(sender_id, response_to_send)
            logger.info(f"Menú inicial enviado a {sender_id} después de reset.")
            return

        message_text = message_text_raw
        if not message_text:
             logger.warning(f"Mensaje sin texto procesable recibido de {sender_id} (después de check reset)")
             return

        current_stage = user_state_obj.stage
        current_brand = user_state_obj.current_brand
        logger.debug(f"Estado para procesamiento: Stage='{current_stage}', Brand='{current_brand}'")
        logger.info(f"Procesando WhatsApp de {sender_id} (Marca DB: {current_brand}, Etapa DB: {current_stage}): '{message_text}'")

        response_to_send = None

        if current_stage == "selecting_brand":
            potential_brand = BRAND_SELECTION_MAP.get(message_text.lower())
            if potential_brand and potential_brand in VALID_BRANDS:
                await set_user_brand_db(db, sender_id, platform, potential_brand)
                response_to_send = get_brand_welcome_message(potential_brand)
            else:
                logger.warning(f"Selección de marca inválida '{message_text}' de {sender_id}. Pidiendo de nuevo.")
                response_to_send = "Por favor, selecciona una marca válida de la lista.\n" + get_initial_brand_selection_message()

        elif current_stage == "main_chat" and current_brand:
            logger.info(f"Usuario {sender_id} en 'main_chat' con marca {current_brand}. Consultando IA.")
            ai_response = None
            try:
                logger.debug("Obteniendo contexto...")
                context = get_brand_context(current_brand)
                logger.debug(f"Contexto obtenido (primeros 100): {context[:100] if context else 'Vacío o Error'}")

                if not context or "Error interno" in context or "no disponible" in context or "no encontrado" in context:
                     logger.error(f"No se pudo obtener contexto válido para {current_brand}. Usando fallback.")
                     profile = BRAND_PROFILES.get(current_brand, BRAND_PROFILES["default"])
                     response_to_send = profile["fallback_instruction"]
                else:
                    logger.debug("Construyendo prompt...")
                    prompt = build_deepseek_prompt(current_brand, message_text, context)
                    logger.debug(f"Prompt construido (inicio): {prompt[:500]}...")

                    logger.info(f"Llamando a DeepSeek API para {sender_id} sobre {current_brand}...")
                    ai_response = await get_deepseek_response(prompt)
                    logger.info(f"Respuesta recibida de DeepSeek para {sender_id}: {ai_response}")

                    if ai_response and isinstance(ai_response, str) and "Error interno:" not in ai_response and "Error:" not in ai_response:
                        response_to_send = ai_response
                        await update_user_state_db(db, user_state_obj, {})
                    else:
                        logger.warning(f"DeepSeek falló o devolvió respuesta inválida/None para {sender_id}. Usando fallback. Respuesta AI: {ai_response}")
                        profile = BRAND_PROFILES.get(current_brand, BRAND_PROFILES["default"])
                        response_to_send = profile["fallback_instruction"]

            except httpx.TimeoutException:
                 logger.error(f"Timeout llamando a DeepSeek API para {sender_id}.")
                 response_to_send = f"Estoy procesando tu solicitud sobre {current_brand}, pero está tomando un poco más de lo esperado. Por favor, ten paciencia o intenta reformular en un momento."
            except Exception as ai_error:
                 logger.error(f"Error inesperado durante consulta a IA para {sender_id}: {ai_error}", exc_info=True)
                 response_to_send = f"Lo siento, tuve un problema interno al procesar tu consulta sobre {current_brand}. Por favor, intenta de nuevo."

        else:
            logger.error(f"Estado inesperado para {sender_id}: Stage='{current_stage}', Brand='{current_brand}'. Reiniciando flujo.")
            await update_user_state_db(db, user_state_obj, {"current_brand": None, "stage": "selecting_brand"})
            response_to_send = get_initial_brand_selection_message()

        if response_to_send:
            logger.info(f"Enviando respuesta a {sender_id} (WhatsApp): '{response_to_send[:150]}...'")
            await send_whatsapp_message(sender_id, response_to_send)

    except Exception as e:
        logger.error(f"Error fatal procesando mensaje WhatsApp de {sender_id}: {e}\n{traceback.format_exc()}")
        if sender_id:
            try:
                if "Error fatal procesando mensaje WhatsApp" not in str(e):
                    await send_whatsapp_message(sender_id, "Lo siento, ocurrió un error interno inesperado. Intenta de nuevo más tarde.")
            except Exception as send_error:
                logger.error(f"No se pudo enviar mensaje de error a {sender_id} (WhatsApp): {send_error}")


async def handle_messenger_message(messaging_event: MessagingEvent, db: AsyncSession):
    sender_id = None
    platform = "facebook"
    user_state_obj = None
    try:
        sender_id = messaging_event.sender.id
        message_info = messaging_event.message

        if not message_info or not message_info.text:
            logger.debug(f"Evento Messenger no es mensaje de texto. Ignorando.")
            return

        message_text_raw = message_info.text.strip()
        reset_check_text = message_text_raw.lower()

        if not message_text_raw:
             logger.warning(f"Mensaje vacío recibido de {sender_id} en Messenger")
             return

        user_state_obj = await get_or_create_user_state(db, sender_id, platform) # Obtener estado antes de check reset

        if reset_check_text and reset_check_text in RESET_KEYWORDS:
            logger.info(f"Comando RESET/MENU ('{reset_check_text}') recibido de {platform}:{sender_id}. Reseteando estado.")
            await update_user_state_db(db, user_state_obj, {"current_brand": None, "stage": "selecting_brand"})
            response_to_send = get_initial_brand_selection_message()
            await send_messenger_message(sender_id, response_to_send)
            logger.info(f"Menú inicial enviado a {sender_id} (Messenger) después de reset.")
            return

        message_text = message_text_raw
        current_stage = user_state_obj.stage
        current_brand = user_state_obj.current_brand
        logger.debug(f"Estado para procesamiento: Stage='{current_stage}', Brand='{current_brand}'")
        logger.info(f"Procesando Messenger de {sender_id} (Marca DB: {current_brand}, Etapa DB: {current_stage}): '{message_text}'")

        response_to_send = None

        if current_stage == "selecting_brand":
            potential_brand = BRAND_SELECTION_MAP.get(message_text.lower())
            if potential_brand and potential_brand in VALID_BRANDS:
                await set_user_brand_db(db, sender_id, platform, potential_brand)
                response_to_send = get_brand_welcome_message(potential_brand)
            else:
                logger.warning(f"Selección de marca inválida '{message_text}' de {sender_id} (Messenger).")
                response_to_send = "Por favor, escribe el nombre o número de la marca.\n" + get_initial_brand_selection_message()

        elif current_stage == "main_chat" and current_brand:
            logger.info(f"Usuario {sender_id} (Messenger) en 'main_chat' con marca {current_brand}. Consultando IA.")
            ai_response = None
            try:
                logger.debug("Obteniendo contexto...")
                context = get_brand_context(current_brand)
                logger.debug(f"Contexto obtenido (primeros 100): {context[:100] if context else 'Vacío o Error'}")

                if not context or "Error interno" in context or "no disponible" in context or "no encontrado" in context:
                     logger.error(f"No se pudo obtener contexto válido para {current_brand} (Messenger). Usando fallback.")
                     profile = BRAND_PROFILES.get(current_brand, BRAND_PROFILES["default"])
                     response_to_send = profile["fallback_instruction"]
                else:
                    logger.debug("Construyendo prompt...")
                    prompt = build_deepseek_prompt(current_brand, message_text, context)
                    logger.debug(f"Prompt construido (inicio): {prompt[:500]}...")

                    logger.info(f"Llamando a DeepSeek API para {sender_id} (Messenger)...")
                    ai_response = await get_deepseek_response(prompt)
                    logger.info(f"Respuesta recibida de DeepSeek para {sender_id} (Messenger): {ai_response}")

                    if ai_response and isinstance(ai_response, str) and "Error interno:" not in ai_response and "Error:" not in ai_response:
                        response_to_send = ai_response
                        await update_user_state_db(db, user_state_obj, {})
                    else:
                        logger.warning(f"DeepSeek falló para {sender_id} (Messenger). Usando fallback. Respuesta AI: {ai_response}")
                        profile = BRAND_PROFILES.get(current_brand, BRAND_PROFILES["default"])
                        response_to_send = profile["fallback_instruction"]

            except httpx.TimeoutException:
                 logger.error(f"Timeout llamando a DeepSeek API para {sender_id} (Messenger).")
                 response_to_send = f"Estoy procesando tu solicitud sobre {current_brand}, dame un momento por favor..."
            except Exception as ai_error:
                 logger.error(f"Error inesperado durante consulta a IA para {sender_id} (Messenger): {ai_error}", exc_info=True)
                 response_to_send = f"Lo siento, tuve un problema interno al procesar tu consulta sobre {current_brand}. Intenta de nuevo."

        else:
            logger.error(f"Estado inesperado para {sender_id} (Messenger). Reiniciando.")
            await update_user_state_db(db, user_state_obj, {"current_brand": None, "stage": "selecting_brand"})
            response_to_send = get_initial_brand_selection_message()

        if response_to_send:
            logger.info(f"Enviando respuesta a {sender_id} (Messenger): '{response_to_send[:150]}...'")
            await send_messenger_message(sender_id, response_to_send)

    except Exception as e:
        logger.error(f"Error fatal procesando mensaje Messenger de {sender_id}: {e}\n{traceback.format_exc()}")
        if sender_id:
             try:
                 if "Error fatal procesando mensaje Messenger" not in str(e):
                    await send_messenger_message(sender_id, "Lo siento, ocurrió un error interno inesperado. Intenta de nuevo más tarde.")
             except Exception as send_error:
                 logger.error(f"No se pudo enviar mensaje de error a {sender_id} (Messenger): {send_error}")


async def process_webhook_payload(payload: dict, db: AsyncSession):
    try:
        object_type = payload.get("object")
        logger.info(f"Procesando payload tipo: {object_type}")

        if object_type == "whatsapp_business_account":
            try:
                data = WhatsAppPayload.model_validate(payload)
                if data.entry:
                    for entry in data.entry:
                        if entry.changes:
                            for change in entry.changes:
                                value = change.value
                                if value and value.statuses:
                                    logger.debug(f"Detectado webhook de estado (statuses) en change.field='{change.field}'")
                                    for status in value.statuses:
                                         logger.info(f"Recibido estado WhatsApp: WAMID={status.id}, Status={status.status}, To={status.recipient_id}, Timestamp={status.timestamp}")
                                elif value and value.errors:
                                     logger.error(f"Detectado webhook de error de Meta en change.field='{change.field}'")
                                     for error in value.errors:
                                         error_details = error.error_data.details if error.error_data else 'N/A'
                                         logger.error(f"Error Meta: Code={error.code}, Title='{error.title}', Details='{error_details}'")
                                elif change.field == "messages" and value and value.messages:
                                    logger.debug(f"Detectado webhook de mensaje (messages) en change.field='{change.field}'")
                                    for message in value.messages:
                                        await handle_whatsapp_message(message, db)
                                else:
                                     value_dump = value.model_dump(exclude_unset=True) if value else 'None'
                                     logger.debug(f"Cambio WhatsApp no procesable: field='{change.field}', Value Keys: {value_dump.keys() if isinstance(value_dump, dict) else 'N/A'}")
            except ValidationError as e:
                 logger.error(f"Error de validación Pydantic para WhatsApp: {e}")
                 logger.debug(f"Payload WhatsApp que falló validación: {payload}")

        elif object_type == "page": # Messenger
             try:
                data = MessengerPayload.model_validate(payload)
                if data.entry:
                    for entry in data.entry:
                        if entry.messaging:
                            for messaging_event in entry.messaging:
                                 if messaging_event.message and messaging_event.message.text:
                                     await handle_messenger_message(messaging_event, db)
                                 else:
                                     logger.debug(f"Evento Messenger no procesado: {messaging_event.model_dump(exclude_unset=True)}")
             except ValidationError as e:
                 logger.error(f"Error de validación Pydantic para Messenger: {e}")
                 logger.debug(f"Payload Messenger que falló validación: {payload}")

        else:
            logger.warning(f"Payload con 'object' no reconocido: '{object_type}'")

    except Exception as e:
        logger.error(f"Error inesperado procesando payload general: {e}\n{traceback.format_exc()}")