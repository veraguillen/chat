# app/main/webhook_handler.py
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, List, Any, Union
from datetime import date, timedelta, datetime, timezone

from unidecode import unidecode
import re
import httpx

from app.models.webhook_models import (
    WhatsAppPayload, WhatsAppMessage, WhatsAppInteractive,
    WhatsAppButtonReply, WhatsAppInteractiveListReply, WhatsAppContact
)
from app.models.user_state import UserState
from app.models.scheduling_models import Company
from app.core.config import settings, get_brand_context
from app.utils.logger import logger
import app.utils.validation_utils as local_validators

from app.main.state_manager import (
    get_or_create_user_state,
    update_user_state_db,
    get_company_selection_message, get_action_selection_message,
    get_company_id_by_selection, get_company_by_id,
    reset_user_to_brand_selection,
    update_user_subscription_status, is_user_subscribed,
    get_conversation_history, add_to_conversation_history,
    STAGE_SELECTING_BRAND, STAGE_AWAITING_ACTION,
    STAGE_MAIN_CHAT_RAG, STAGE_PROVIDING_SCHEDULING_INFO,
    STAGE_COLLECTING_NAME, STAGE_COLLECTING_EMAIL, STAGE_COLLECTING_PHONE, STAGE_COLLECTING_PURPOSE
)

from app.api.meta import send_whatsapp_message
from app.api.calendly import get_available_slots, get_scheduling_link
from app.api.llm_client import get_llm_response
from app.ai.rag_retriever import search_relevant_documents
from app.ai.rag_prompt_builder import build_llm_prompt, BRAND_PROFILES

RESET_KEYWORDS = {"menu", "menú", "inicio", "reset", "/reset", "/menu", "volver", "cambiar marca", "salir", "cancelar", "principal"}
OPT_OUT_KEYWORDS = {"stop", "parar", "baja", "unsubscribe", "no quiero mensajes", "cancelar mensajes", "detener mensajes", "adios", "adiós", "gracias por tu ayuda"}
OPT_IN_KEYWORDS = {"start", "alta", "subscribe", "quiero mensajes", "iniciar mensajes", "continuar mensajes"}

# --- Funciones Helper ---
def normalize_brand_name(brand_name: str) -> str:
    if not isinstance(brand_name, str): logger.warning(f"norm_brand: no str {type(brand_name)}"); return "default_brand_error"
    if not brand_name.strip(): logger.warning("norm_brand: vacío"); return "default_brand_empty"
    s=unidecode(brand_name).lower();s=re.sub(r'[^\w-]','_',s);s=re.sub(r'_+','_',s).strip('_');
    if not s: logger.warning(f"norm '{brand_name}' a vacío"); return "default_brand_normalized_empty"
    return s

def format_context_from_docs(docs: List[Any], brand_name: str) -> str:
    if not docs: 
        logger.debug(f"format_context_from_docs: No docs received for brand '{brand_name}'.")
        return ""
    context_parts = []
    for i, doc in enumerate(docs):
        if hasattr(doc, 'page_content') and isinstance(doc.page_content, str) and doc.page_content.strip():
            context_parts.append(doc.page_content.strip())
        else:
            logger.warning(f"format_context_from_docs: Doc {i} for brand '{brand_name}' has no valid page_content.")
            
    if not context_parts:
        logger.warning(f"format_context_from_docs: No valid page_content found in docs for brand '{brand_name}'.")
        return ""
    return "\n\n---\n\n".join(context_parts)

def format_available_slots_message(slots: List[Dict[str, str]]) -> str:
    if not slots: return "Lo siento, no encontré horarios disponibles en los próximos días."
    options = [f"• {slot['display_time']}" for slot in slots[:5] if isinstance(slot, dict) and slot.get('display_time')]
    if not options: return "No pude formatear los horarios disponibles. Por favor, intenta más tarde o usa el enlace de agendamiento."
    timezone_display = settings.calendly_timezone if settings.calendly_timezone else "la zona horaria configurada"
    return f"Estos son algunos de los próximos horarios disponibles (en {timezone_display}):\n" + "\n".join(options) + "\n"

async def _handle_providing_scheduling_info(db_session: AsyncSession, current_user_state_obj: UserState, current_brand_id: Optional[int]) -> Optional[Union[str, Dict[str, Any]]]:
    sender_user_id_for_log = f"{current_user_state_obj.platform}:{current_user_state_obj.user_id}"
    sender_phone_simple = current_user_state_obj.user_id 
    if current_user_state_obj.platform == "whatsapp" and "whatsapp:" in sender_phone_simple:
        sender_phone_simple = sender_phone_simple.replace("whatsapp:","")

    logger.info(f"Ejecutando _handle_providing_scheduling_info para {sender_user_id_for_log}")
    if not settings.calendly_event_type_uri or not settings.calendly_api_key:
        logger.error("CRÍTICO: CALENDLY_EVENT_TYPE_URI o CALENDLY_API_KEY no configurados.")
        await update_user_state_db(db_session, current_user_state_obj, {"stage": STAGE_AWAITING_ACTION})
        return "Lo siento, problema con configuración de agendamiento. Intenta 'menu'."

    company = await get_company_by_id(db_session, current_brand_id) if current_brand_id else None
    company_name_display = company.name if company else "nuestro equipo"
    user_first_name = current_user_state_obj.collected_name.split()[0] if current_user_state_obj.collected_name else "tú"

    response_parts = [f"¡Perfecto, {user_first_name}!"]
    response_parts.append(f"Para agendar tu cita sobre '{current_user_state_obj.purpose_of_inquiry or 'tu consulta'}' con *{company_name_display}*, aquí tienes:")
    slots_message_part = "No pude obtener horarios."; 
    try:
        slots_days=settings.calendly_days_to_check or 7; slots_data=await get_available_slots(settings.calendly_event_type_uri,date.today(),date.today()+timedelta(days=slots_days)); slots_msg=format_available_slots_message(slots_data or [])
        slots_message_part = slots_msg
    except Exception as e: logger.error(f"Error slots Calendly {sender_user_id_for_log}: {e}",exc_info=True)
    response_parts.append(slots_message_part)
    link_message_part="No pude generar enlace."; 
    try:
        name_cal=current_user_state_obj.collected_name or "Invitado"; email_cal=current_user_state_obj.collected_email
        link_url=await get_scheduling_link(settings.calendly_event_type_uri,name=name_cal,email=email_cal)
        if link_url: link_message_part=f"\nO reserva aquí:\n{link_url}"
    except Exception as e: logger.error(f"Error enlace Calendly {sender_user_id_for_log}: {e}",exc_info=True)
    response_parts.append(link_message_part)
    response_parts.append("\nAl agendar recibirás confirmación. 'menu' para otras opciones.")
    final_response="\n\n".join(filter(None,response_parts)); await update_user_state_db(db_session,current_user_state_obj,{"stage":STAGE_AWAITING_ACTION})
    return final_response

async def handle_whatsapp_message(
    message_obj_from_payload: WhatsAppMessage,
    user_profile_name_from_webhook: Optional[str],
    platform_name: str,
    db_session: AsyncSession,
    request: Request
):
    user_id_for_state_col: Optional[str] = None 
    sender_phone_simple_for_meta_api: Optional[str] = None
    current_user_state_obj: Optional[UserState] = None
    response_to_send: Optional[Union[str, Dict[str, Any]]] = None
    
    try:
        if not message_obj_from_payload.from_number: logger.error("Mensaje WA sin from_number."); return
        sender_phone_simple_for_meta_api = message_obj_from_payload.from_number
        user_id_for_state_col = sender_phone_simple_for_meta_api

        effective_display_name = user_profile_name_from_webhook if user_profile_name_from_webhook else "Usuario"
        
        current_user_state_obj = await get_or_create_user_state(db_session, user_id_for_state_col, platform_name, effective_display_name)
        
        if not current_user_state_obj:
            logger.critical(f"Fallo: No UserState para {platform_name}:{user_id_for_state_col}.")
            await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload="Problema técnico al identificarte.")
            return

        user_key_for_history = f"{current_user_state_obj.platform}:{current_user_state_obj.user_id}"
        message_text_for_history: Optional[str] = None
        if message_obj_from_payload.type=='text' and message_obj_from_payload.text: message_text_for_history=message_obj_from_payload.text.body.strip()
        elif message_obj_from_payload.type=='interactive' and message_obj_from_payload.interactive:
            if message_obj_from_payload.interactive.list_reply: message_text_for_history=f"Lista: {message_obj_from_payload.interactive.list_reply.title} (ID: {message_obj_from_payload.interactive.list_reply.id})"
            elif message_obj_from_payload.interactive.button_reply: message_text_for_history=f"Botón: {message_obj_from_payload.interactive.button_reply.title} (ID: {message_obj_from_payload.interactive.button_reply.id})"
        if message_text_for_history: add_to_conversation_history(user_key_for_history, "user", message_text_for_history)
        
        initial_stage: str = current_user_state_obj.stage
        current_brand_id: Optional[int] = current_user_state_obj.current_brand_id
        message_text_raw: Optional[str] = None

        if message_obj_from_payload.type=='text' and message_obj_from_payload.text: message_text_raw=message_obj_from_payload.text.body.strip()
        elif message_obj_from_payload.type=='interactive' and message_obj_from_payload.interactive:
            interactive_payload=message_obj_from_payload.interactive
            if interactive_payload.list_reply and interactive_payload.list_reply.id: message_text_raw=interactive_payload.list_reply.id.strip()
            elif interactive_payload.button_reply and interactive_payload.button_reply.id: message_text_raw=interactive_payload.button_reply.id.strip()
            else: 
                response_to_send = "Problema con selección. 'menu'."
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send)
                add_to_conversation_history(user_key_for_history,"assistant",response_to_send); return
        else: 
            response_to_send = "Solo texto/opciones. 'menu'."
            await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send)
            add_to_conversation_history(user_key_for_history,"assistant",response_to_send); return
        if not message_text_raw: 
            response_to_send = "Mensaje vacío. 'menu'."
            await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send)
            add_to_conversation_history(user_key_for_history,"assistant",response_to_send); return

        normalized_message_text = message_text_raw.lower()
        logger.info(f"Procesando WA de {user_key_for_history} (BrandID:{current_brand_id}, Stage: {initial_stage}, Subscrito: {current_user_state_obj.is_subscribed}): '{message_text_raw[:100]}'")

        if normalized_message_text in OPT_OUT_KEYWORDS:
            if not current_user_state_obj.is_subscribed: response_to_send = "Ya estabas de baja. Envía 'ALTA' para resuscribirte."
            else:
                try: 
                    await update_user_subscription_status(db_session, current_user_state_obj.user_id, current_user_state_obj.platform, False)
                    response_to_send = "Has sido dado de baja. Envía 'ALTA' o 'START' para resuscribirte."
                except Exception as e: logger.error(f"Err opt-out {user_key_for_history}: {e}"); response_to_send = "Problema con tu baja."
            await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send)
            add_to_conversation_history(user_key_for_history, "assistant", response_to_send); return

        if normalized_message_text in OPT_IN_KEYWORDS:
            opt_in_msg: Optional[str] = None
            if current_user_state_obj.is_subscribed: opt_in_msg = "¡Gracias! Ya estás suscrito. ¿En qué te ayudo? ('menu')"
            else:
                try: 
                    await update_user_subscription_status(db_session, current_user_state_obj.user_id, current_user_state_obj.platform, True)
                    current_user_state_obj.is_subscribed = True # Actualizar en memoria para este request
                    opt_in_msg = "¡Bienvenido! Te has suscrito. ¿En qué te ayudo? ('menu')"
                    await reset_user_to_brand_selection(db_session, current_user_state_obj)
                except Exception as e: logger.error(f"Err opt-in {user_key_for_history}: {e}"); opt_in_msg = "Problema con tu suscripción."
            if opt_in_msg: 
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=opt_in_msg)
                add_to_conversation_history(user_key_for_history, "assistant", opt_in_msg)
        
        # Re-chequear suscripción por si un opt-in falló y no actualizó el objeto en memoria correctamente
        if not await is_user_subscribed(db_session, current_user_state_obj.user_id, current_user_state_obj.platform):
             # Actualizar el objeto en memoria si la DB dice otra cosa
            current_user_state_obj.is_subscribed = False 
            logger.info(f"Msg de {user_key_for_history} ignorado (opted-out tras re-check).")
            return

        if normalized_message_text in RESET_KEYWORDS and normalized_message_text not in OPT_OUT_KEYWORDS:
            await reset_user_to_brand_selection(db_session, current_user_state_obj)
            response_to_send = await get_company_selection_message(db_session, current_user_state_obj)

        elif response_to_send is None: 
            initial_stage = current_user_state_obj.stage 
            current_brand_id = current_user_state_obj.current_brand_id
            
            if initial_stage == STAGE_SELECTING_BRAND:
                # ... (Lógica como antes) ...
                selected_company_id=await get_company_id_by_selection(db_session,message_text_raw)
                if selected_company_id:
                    company=await get_company_by_id(db_session,selected_company_id)
                    if not company:response_to_send="Error. 'menu'."
                    else:await update_user_state_db(db_session,current_user_state_obj,{"current_brand_id":selected_company_id,"stage":STAGE_AWAITING_ACTION});response_to_send=await get_action_selection_message(company.name,current_user_state_obj)
                else:response_to_send=f"Opción '{message_text_raw}' no válida.\n\n{await get_company_selection_message(db_session, current_user_state_obj)}"
            
            elif initial_stage == STAGE_AWAITING_ACTION:
                # ... (Lógica como antes) ...
                company=await get_company_by_id(db_session,current_brand_id)
                company_name_display=company.name if company else "empresa"
                if message_text_raw=="action_a":await update_user_state_db(db_session,current_user_state_obj,{"stage":STAGE_COLLECTING_NAME});response_to_send="¿Nombre completo?"
                elif message_text_raw=="action_b":await update_user_state_db(db_session,current_user_state_obj,{"stage":STAGE_MAIN_CHAT_RAG});response_to_send=f"¿Consulta para {company_name_display}?"
                elif message_text_raw=="action_menu":await reset_user_to_brand_selection(db_session,current_user_state_obj);response_to_send=await get_company_selection_message(db_session,current_user_state_obj)
                else:response_to_send=await get_action_selection_message(company_name_display,current_user_state_obj)

            elif initial_stage == STAGE_COLLECTING_NAME:
                # ... (Lógica como antes) ...
                await update_user_state_db(db_session,current_user_state_obj,{"collected_name":message_text_raw,"stage":STAGE_COLLECTING_EMAIL});response_to_send=f"¡Gracias, {message_text_raw.split()[0]}! Correo?"
            
            elif initial_stage == STAGE_COLLECTING_EMAIL:
                # ... (Lógica como antes) ...
                if local_validators.is_valid_email(message_text_raw):await update_user_state_db(db_session,current_user_state_obj,{"collected_email":message_text_raw,"stage":STAGE_COLLECTING_PHONE});response_to_send="Correo ok. ¿Teléfono?"
                else:response_to_send="Correo no válido."
            
            elif initial_stage == STAGE_COLLECTING_PHONE:
                # ... (Lógica como antes) ...
                if local_validators.is_valid_phone(message_text_raw):await update_user_state_db(db_session,current_user_state_obj,{"collected_phone":message_text_raw,"stage":STAGE_COLLECTING_PURPOSE});response_to_send="Teléfono ok. ¿Motivo?"
                else:response_to_send="Teléfono no válido."
            
            elif initial_stage == STAGE_COLLECTING_PURPOSE:
                # ... (Lógica como antes) ...
                await update_user_state_db(db_session,current_user_state_obj,{"purpose_of_inquiry":message_text_raw,"stage":STAGE_PROVIDING_SCHEDULING_INFO});response_to_send=await _handle_providing_scheduling_info(db_session,current_user_state_obj,current_brand_id)

            elif initial_stage == STAGE_PROVIDING_SCHEDULING_INFO:
                # ... (Lógica como antes) ...
                company=await get_company_by_id(db_session,current_brand_id);response_to_send=await get_action_selection_message(company.name if company else "empresa",current_user_state_obj);await update_user_state_db(db_session,current_user_state_obj,{"stage":STAGE_AWAITING_ACTION})
            
            elif initial_stage == STAGE_MAIN_CHAT_RAG:
                if not current_brand_id: 
                    await reset_user_to_brand_selection(db_session, current_user_state_obj)
                    response_to_send = "Error con selección previa. " + await get_company_selection_message(db_session, current_user_state_obj)
                else:
                    company = await get_company_by_id(db_session, current_brand_id)
                    current_brand_name = company.name if company else "la empresa seleccionada"
                    
                    context_from_rag: Optional[str] = None
                    context_from_brand_file: Optional[str] = None
                    final_context_for_llm: str

                    try:
                        retriever=getattr(request.app.state,'retriever',None);is_rag_ready=getattr(request.app.state,'is_rag_ready',False)
                        logger.debug(f"RAG_Debug: Iniciando RAG para '{current_brand_name}', query: '{message_text_raw}'") # LOG
                        
                        if is_rag_ready and retriever:
                            brand_norm_rag=normalize_brand_name(current_brand_name)
                            logger.debug(f"RAG_Debug: Marca normalizada para RAG: '{brand_norm_rag}'") # LOG
                            relevant_docs=await search_relevant_documents(retriever,message_text_raw,brand_norm_rag,settings.rag_default_k)
                            logger.debug(f"RAG_Debug: Documentos RAG encontrados: {len(relevant_docs) if relevant_docs else 0}") # LOG
                            if relevant_docs:
                                # --- LOG DETALLADO DE DOCUMENTOS RAG ---
                                logger.debug(f"RAG_Debug: Documentos individuales encontrados ({len(relevant_docs)}):")
                                for i, doc_item in enumerate(relevant_docs):
                                    doc_content_preview = getattr(doc_item, 'page_content', 'NO PAGE_CONTENT ATTRIBUTE')
                                    if isinstance(doc_content_preview, str): doc_content_preview = doc_content_preview[:100] # Preview
                                    logger.debug(f"  RAG Doc {i}: metadata={getattr(doc_item, 'metadata', {})}, content_preview='{doc_content_preview}'")
                                # --- FIN LOG DETALLADO ---
                                context_from_rag=format_context_from_docs(relevant_docs,current_brand_name)
                                logger.debug(f"RAG_Debug: Contexto desde RAG (len: {len(context_from_rag) if context_from_rag else 0}, preview: '{context_from_rag[:200] if context_from_rag else 'N/A'}')") # LOG
                        else:
                            logger.warning("RAG_Debug: Retriever no está listo o no disponible.")

                        if not context_from_rag or len(context_from_rag.strip()) < 20:
                            logger.info(f"RAG_Debug: Contexto RAG insuficiente/nulo. Fallback a get_brand_context para '{current_brand_name}'.")
                            context_from_brand_file=await get_brand_context(current_brand_name)
                            logger.debug(f"RAG_Debug: Contexto de get_brand_context (len: {len(context_from_brand_file) if context_from_brand_file else 0}, preview: '{context_from_brand_file[:200] if context_from_brand_file else 'N/A'}')") # LOG
                            final_context_for_llm = context_from_rag if context_from_rag and len(context_from_rag.strip()) >=10 else context_from_brand_file
                        else:
                            final_context_for_llm = context_from_rag
                        
                        if not final_context_for_llm or len(final_context_for_llm.strip()) < 10: # Si AÚN no hay contexto útil
                            logger.warning(f"RAG/Context: Contexto final (RAG y/o archivo) nulo o insuficiente para '{current_brand_name}'. Se pasará 'No se encontró...' al LLM.")
                            final_context_for_llm = "No se encontró información de contexto específica para esta consulta en nuestros documentos." # Mensaje para el LLM
                        
                        logger.debug(f"RAG/Context: Contexto FINAL para LLM (longitud: {len(final_context_for_llm.strip())}): '{final_context_for_llm[:200]}...'") # LOG

                        history=get_conversation_history(user_key_for_history)
                        is_bot_first_turn_in_this_interaction = not any(msg["role"]=="assistant" for msg in history)
                        
                        logger.debug(f"LLM_Prompt_Builder: Llamando build_llm_prompt: brand='{current_brand_name}', query='{message_text_raw[:50]}...', context_len={len(final_context_for_llm)}, history_len={len(history)}, first_turn={is_bot_first_turn_in_this_interaction}") # LOG

                        prompt_for_llm=build_llm_prompt(
                            brand_name=current_brand_name, user_query=message_text_raw,
                            context=final_context_for_llm, conversation_history=history,
                            user_collected_name=current_user_state_obj.collected_name,
                            is_first_turn=is_bot_first_turn_in_this_interaction
                        )
                        ai_response_text=await get_llm_response(prompt_for_llm)
                        logger.debug(f"LLM_Response: Respuesta cruda del LLM: '{ai_response_text}'") # LOG

                        if(ai_response_text and isinstance(ai_response_text,str)and len(ai_response_text.strip())>1 and not ai_response_text.lower().startswith("error")):
                            response_to_send=f"{ai_response_text.strip()}\n\n¿Algo más? ('menu')"
                        else:
                            profile=BRAND_PROFILES.get(current_brand_name,BRAND_PROFILES.get("default",{}))
                            fallback_text=profile.get("fallback_llm_error","Lo siento, problema al procesar. 'menu'.")
                            response_to_send=fallback_text.replace("[tema de la pregunta]","tu consulta")
                            logger.warning(f"LLM_Response: Respuesta LLM inválida: '{ai_response_text}'. Usando fallback: '{response_to_send}'") # LOG
                    except httpx.TimeoutException: 
                        response_to_send="Nuestros sistemas están tardando. 'menu'."
                    except Exception as e: 
                        logger.error(f"Error RAG/LLM para {user_key_for_history}: {e}",exc_info=True)
                        response_to_send="Lo siento, problema técnico. 'menu'."
            else: 
                logger.warning(f"UserState {user_key_for_history} en stage no manejado: '{initial_stage}'. Reseteando.")
                await reset_user_to_brand_selection(db_session, current_user_state_obj)
                response_to_send = await get_company_selection_message(db_session, current_user_state_obj)

        if response_to_send:
            final_stage_log = current_user_state_obj.stage
            final_subscribed_log = current_user_state_obj.is_subscribed
            logger.info(f"Enviando a {sender_phone_simple_for_meta_api} (Stage: {final_stage_log}, Subscrito: {final_subscribed_log}): '{str(response_to_send)[:150]}...'")
            
            response_text_for_history = response_to_send["text"] if isinstance(response_to_send, dict) and "text" in response_to_send else response_to_send if isinstance(response_to_send, str) else ""
            if response_text_for_history: add_to_conversation_history(user_key_for_history, "assistant", response_text_for_history)

            if isinstance(response_to_send, dict) and "text" in response_to_send and "buttons" in response_to_send: 
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send["text"], interactive_buttons=response_to_send["buttons"])
            elif isinstance(response_to_send, str): 
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload=response_to_send)
            else: 
                logger.error(f"Tipo response_to_send no manejable: {type(response_to_send)}.")
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload="Error al preparar la respuesta. Por favor, intenta con 'menu'.")
        else:
             logger.info(f"No se preparó respuesta explícita para {user_key_for_history} (Stage: {current_user_state_obj.stage}).")

    except Exception as e:
        user_id_log = user_id_for_state_col if 'user_id_for_state_col' in locals() and user_id_for_state_col else 'ID Desconocido'
        platform_log = platform_name if 'platform_name' in locals() and platform_name else 'Plataforma Desconocida'
        logger.error(f"Error FATAL en handle_whatsapp_message para {user_id_log} ({platform_log}): {e}", exc_info=True)
        if sender_phone_simple_for_meta_api:
            try: 
                await send_whatsapp_message(to=sender_phone_simple_for_meta_api, message_payload="Lo siento, ocurrió un error inesperado en nuestro sistema. Por favor, intenta más tarde o escribe 'menu'.")
            except: pass

async def process_webhook_payload(payload: dict, db_session: AsyncSession, request: Request):
    try:
        object_type = payload.get("object")
        if object_type != "whatsapp_business_account": return

        try: data = WhatsAppPayload.model_validate(payload)
        except Exception as p_error: logger.error(f"Error validación payload WA: {p_error}", exc_info=True); return

        if data.entry:
            for entry_item in data.entry:
                if entry_item.changes:
                    for change_item in entry_item.changes:
                        value_item = change_item.value
                        if not value_item: continue

                        if value_item.statuses:
                            for status_detail in value_item.statuses: 
                                log_parts = [f"WA Status: ID {status_detail.id}", f"To {status_detail.recipient_id}", f"St {status_detail.status}"]
                                if status_detail.timestamp: log_parts.append(f"Ts {status_detail.timestamp}")
                                logger.info(", ".join(log_parts))
                                if status_detail.errors:
                                    for err_s in status_detail.errors: logger.error(f"  Error Status WA: {err_s.code} - {err_s.title}")
                        elif value_item.errors:
                            for err_d in value_item.errors: logger.error(f"Error API Meta WA: {err_d.code} - {err_d.title}")
                        elif change_item.field == "messages" and value_item.messages:
                            for msg_obj_payload in value_item.messages:
                                user_profile_name_extracted: Optional[str] = None
                                if value_item.contacts and value_item.contacts[0] and value_item.contacts[0].profile:
                                    user_profile_name_extracted = value_item.contacts[0].profile.name
                                
                                current_platform = "whatsapp" 

                                if msg_obj_payload.type in ['text', 'interactive']:
                                    await handle_whatsapp_message(msg_obj_payload, user_profile_name_extracted, current_platform, db_session, request)
                                elif msg_obj_payload.type == 'button' and hasattr(msg_obj_payload, 'button') and msg_obj_payload.button and msg_obj_payload.button.payload:
                                    pseudo_interactive_message = WhatsAppMessage(
                                        from_number=msg_obj_payload.from_number, 
                                        id=msg_obj_payload.id, 
                                        timestamp=msg_obj_payload.timestamp,
                                        type='interactive',
                                        interactive=WhatsAppInteractive(
                                            type='button_reply',
                                            button_reply=WhatsAppButtonReply(id=msg_obj_payload.button.payload, title=msg_obj_payload.button.text or "Botón")
                                        )
                                    )
                                    await handle_whatsapp_message(pseudo_interactive_message, user_profile_name_extracted, current_platform, db_session, request)
                                else:
                                    logger.info(f"Msg WA tipo '{msg_obj_payload.type}' de {msg_obj_payload.from_number} no procesado.")
    except Exception as e_main:
        logger.critical(f"Error CRÍTICO en process_webhook_payload: {e_main}", exc_info=True)