# app/main/state_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta # timedelta para expiración de caché

# ### CORRECCIÓN ### Importar UserState desde app.models.user_state
from app.models.user_state import UserState
from app.models.scheduling_models import Company
from app.utils.logger import logger

# --- Constantes de Estados ---
STAGE_SELECTING_BRAND = "selecting_brand"
STAGE_AWAITING_ACTION = "awaiting_action_choice"
STAGE_AWAITING_QUERY_FOR_RAG = "awaiting_query_for_rag"  # Estado para recibir la consulta después de seleccionar "Consultar información"
STAGE_MAIN_CHAT_RAG = "main_chat_rag"
STAGE_CALENDLY_INITIATE = "calendly_initiate"  # Estado para iniciar proceso de agendamiento
STAGE_PROVIDING_SCHEDULING_INFO = "providing_scheduling_info"
STAGE_COLLECTING_NAME = "collecting_name"
STAGE_COLLECTING_EMAIL = "collecting_email"
STAGE_COLLECTING_PHONE = "collecting_phone"
STAGE_COLLECTING_PURPOSE = "collecting_purpose"

# --- Caché de Compañías ---
_company_cache: Optional[List[Company]] = None
_cache_last_loaded_at: Optional[datetime] = None
_CACHE_EXPIRATION_MINUTES = 60

async def get_all_companies(session: AsyncSession, use_cache: bool = True, force_reload_cache: bool = False) -> List[Company]:
    global _company_cache, _cache_last_loaded_at
    
    now = datetime.now(timezone.utc)
    cache_expired = False
    if _cache_last_loaded_at:
        if (now - _cache_last_loaded_at).total_seconds() > _CACHE_EXPIRATION_MINUTES * 60:
            cache_expired = True
            logger.info("Caché de compañías expirada.")

    if force_reload_cache or cache_expired:
        logger.info(f"get_all_companies: Forzando recarga de caché (force: {force_reload_cache}, expired: {cache_expired}).")
        _company_cache = None

    if use_cache and _company_cache is not None:
        logger.debug("Usando caché de compañías.")
        return _company_cache

    logger.info("Consultando compañías desde la DB...")
    stmt = select(Company).order_by(Company.id)
    result = await session.execute(stmt)
    companies_from_db = list(result.scalars().all())
    
    if companies_from_db:
        _company_cache = companies_from_db
        _cache_last_loaded_at = now
        logger.info(f"Se cargaron {len(companies_from_db)} compañías y se almacenaron en caché.")
    else:
        logger.warning("No se encontraron compañías en la DB.")
        _company_cache = []
        _cache_last_loaded_at = now
        
    return _company_cache

async def get_company_by_id(session: AsyncSession, company_id: Optional[int]) -> Optional[Company]:
    if company_id is None: return None
    await get_all_companies(session) # Asegura que caché esté poblada/fresca
    if _company_cache:
        for company_obj_cache in _company_cache:
            if company_obj_cache.id == company_id:
                 return company_obj_cache
    
    company_obj_db = await session.get(Company, company_id)
    if not company_obj_db: logger.warning(f"Compañía ID {company_id} NO encontrada en DB.")
    return company_obj_db

async def get_brand_name_by_id(session: AsyncSession, brand_id: Optional[int]) -> Optional[str]:
    if brand_id is None: return None
    company = await get_company_by_id(session, brand_id)
    return company.name if company else None

async def get_company_id_by_selection(session: AsyncSession, user_input: str) -> Optional[int]:
    normalized_input = user_input.strip().lower()
    companies = await get_all_companies(session)
    if not companies: return None

    if normalized_input.isdigit():
        try:
            option_number = int(normalized_input)
            if 1 <= option_number <= len(companies):
                return companies[option_number - 1].id
        except ValueError: pass

    company_map: Dict[str, int] = {comp.name.lower(): comp.id for comp in companies}
    # Añadir alias comunes
    for comp in companies:
        name_lower = comp.name.lower()
        if "fundaci" in name_lower: company_map["fundacion"] = comp.id
        if "ehecatl" in name_lower: company_map["ehecatl"] = comp.id
        if "bazan" in name_lower: company_map["bazan"] = comp.id; company_map["javier bazan"] = comp.id
        if "udd" in name_lower: company_map["udd"] = comp.id; company_map["universidad"] = comp.id
        if "fes" in name_lower: company_map["fes"] = comp.id; company_map["frente"] = comp.id
            
    return company_map.get(normalized_input)

# --- Gestión de Estado y Suscripción del Usuario ---
async def get_or_create_user_state(db_session: AsyncSession, user_id: str, platform: str, display_name: Optional[str] = None) -> UserState:
    """
    Obtiene un UserState existente o crea uno nuevo.
    Usa (user_id, platform) como clave.
    """
    stmt = select(UserState).filter_by(user_id=user_id, platform=platform)
    result = await db_session.execute(stmt)
    user_state = result.scalar_one_or_none()
    
    current_time_utc = datetime.now(timezone.utc)

    if user_state is None:
        logger.info(f"Nuevo UserState para {platform}:{user_id}. Creando...")
        user_state = UserState(
            user_id=user_id,
            platform=platform,
            collected_name=display_name,
            stage=STAGE_SELECTING_BRAND,
            is_subscribed=True,
            last_interaction_at=current_time_utc
        )
        db_session.add(user_state)
        try:
            await db_session.commit()
            await db_session.refresh(user_state)
            logger.info(f"Nuevo UserState creado y guardado para {platform}:{user_id}. ID: {user_state.id}, Stage: {user_state.stage}")
        except Exception as e:
            logger.error(f"Error al guardar nuevo UserState para {platform}:{user_id}: {e}", exc_info=True)
            await db_session.rollback()
            raise
    else:
        # Actualizar solo el timestamp y el nombre si es necesario
        user_state.last_interaction_at = current_time_utc
        if display_name and user_state.collected_name != display_name:
            user_state.collected_name = display_name
            db_session.add(user_state)
            try:
                await db_session.commit()
                logger.debug(f"Nombre de usuario actualizado para {platform}:{user_id}")
            except Exception as e:
                logger.error(f"Error al actualizar nombre de usuario {platform}:{user_id}: {e}", exc_info=True)
                await db_session.rollback()
        
        logger.debug(f"UserState existente para {platform}:{user_id}. Stage:'{user_state.stage}'. Timestamp actualizado.")
    
    return user_state

async def update_user_state_db(db_session: AsyncSession, user_state_obj: UserState, updates: Dict[str, Any]):
    """Actualiza campos de un objeto UserState existente y lo marca para commit."""
    updated_fields_log = {}
    changed_besides_timestamp = False
    user_key = f"{user_state_obj.platform}:{user_state_obj.user_id}"
    
    for key, value in updates.items():
        if hasattr(user_state_obj, key):
            current_value = getattr(user_state_obj, key)
            if current_value != value:
                setattr(user_state_obj, key, value)
                updated_fields_log[key] = value
                changed_besides_timestamp = True
        else:
            logger.warning(f"Intento de actualizar campo inexistente '{key}' en UserState para {user_key}.")
    
    user_state_obj.last_interaction_at = datetime.now(timezone.utc) # Asegurar que onupdate funcione o actualizar manualmente
    
    try:
        # Asegurar que obtenemos la referencia más reciente desde la DB
        db_user_state = await db_session.get(UserState, (user_state_obj.user_id, user_state_obj.platform))
        
        if db_user_state:
            # Actualizar también la referencia de DB directamente
            for key, value in updates.items():
                if hasattr(db_user_state, key):
                    setattr(db_user_state, key, value)
            db_user_state.last_interaction_at = user_state_obj.last_interaction_at
            
            # Marcar ambos objetos para actualización
            db_session.add(db_user_state)
        
        # En cualquier caso, marcar el objeto original también
        db_session.add(user_state_obj)
        
        # Forzar flush para asegurar persistencia inmediata
        await db_session.flush()
        
        # Intentar commit inmediato para mayor seguridad
        await db_session.commit()
        
        if changed_besides_timestamp:
            logger.info(f"UserState {user_key} actualizado y guardado en DB con: {updated_fields_log}")
            
            # Verificación adicional de diagnóstico
            if "stage" in updates and updates["stage"] == STAGE_MAIN_CHAT_RAG:
                # Verificar que el cambio a RAG se haya guardado correctamente
                verification = await db_session.get(UserState, (user_state_obj.user_id, user_state_obj.platform))
                if verification and verification.stage == STAGE_MAIN_CHAT_RAG:
                    logger.debug(f"DIAGNÓSTICO-RAG: Verificado que el estado {user_key} se actualizó correctamente a STAGE_MAIN_CHAT_RAG en DB")
                else:
                    logger.warning(f"DIAGNÓSTICO-RAG: ¡ALERTA! El estado {user_key} NO se actualizó correctamente a STAGE_MAIN_CHAT_RAG en DB")
    
    except Exception as e:
        logger.error(f"Error al actualizar UserState en DB para {user_key}: {e}", exc_info=True)
        await db_session.rollback()
        # A pesar del error, actualizamos el objeto en memoria para mantener la consistencia del flujo
        if changed_besides_timestamp:
            logger.info(f"UserState {user_key} actualizado SOLO EN MEMORIA con: {updated_fields_log} (falló persistencia en DB)")
    
    if updates.get("stage") == STAGE_SELECTING_BRAND:
        clear_conversation_history(f"{user_state_obj.platform}:{user_state_obj.user_id}")

async def reset_user_to_brand_selection(db_session: AsyncSession, user_state_obj: UserState):
    """Resetea el estado del UserState a la selección de marca inicial."""
    fields_to_reset = {
        "current_brand_id": None,
        "stage": STAGE_SELECTING_BRAND,
        "purpose_of_inquiry": None,
        "session_explicitly_ended": False,  # Reiniciar el flag de fin de sesión
        # No resetear collected_name, email, phone, o is_subscribed aquí por defecto
    }
    await update_user_state_db(db_session, user_state_obj, fields_to_reset)
    # clear_conversation_history ya se llama dentro de update_user_state_db si stage es STAGE_SELECTING_BRAND
    logger.info(f"UserState {user_state_obj.platform}:{user_state_obj.user_id} reseteado a selección de marca.")

async def update_user_subscription_status(db_session: AsyncSession, user_id: str, platform: str, is_subscribed: bool):
    """Actualiza el estado de suscripción (is_subscribed) de un UserState."""
    # Primero, obtener o crear el usuario para asegurar que exista
    user_state = await get_or_create_user_state(db_session, user_id, platform)
    
    if user_state.is_subscribed != is_subscribed:
        user_state.is_subscribed = is_subscribed
        user_state.last_interaction_at = datetime.now(timezone.utc) # Actualizar timestamp
        db_session.add(user_state) # Marcar para guardar
        logger.info(f"Estado de suscripción para {platform}:{user_id} actualizado a: {is_subscribed} en DB.")
    else:
        logger.info(f"Estado de suscripción para {platform}:{user_id} ya era {is_subscribed}. No cambios en DB.")
    # El commit se hará al final del request en webhook_handler.

async def is_user_subscribed(db_session: AsyncSession, user_id: str, platform: str) -> bool:
    """Verifica si un UserState está suscrito. Si no existe, se considera no suscrito."""
    stmt = select(UserState.is_subscribed).filter_by(user_id=user_id, platform=platform)
    result = await db_session.execute(stmt)
    subscription_status = result.scalar_one_or_none()

    if subscription_status is None:
        logger.debug(f"UserState {platform}:{user_id} no encontrado al verificar suscripción. Considerado NO suscrito.")
        return False
    return subscription_status

# --- Conversation History Management (en memoria) ---
_conversation_history: Dict[str, List[Dict[str, str]]] = {}
_MAX_HISTORY_TURNS = 10 # Guardar N turnos (1 turno = 1 user + 1 assistant)

def get_conversation_history(user_key: str) -> List[Dict[str, str]]:
    """Obtiene el historial de conversación para un usuario."""
    return _conversation_history.get(user_key, [])

def add_to_conversation_history(user_key: str, role: str, content: str):
    """
    Añade un mensaje al historial de conversación del usuario.
    
    Args:
        user_key: Clave única del usuario (ej: 'whatsapp:123456789')
        role: 'user' o 'assistant'
        content: Contenido del mensaje
    """
    if user_key not in _conversation_history:
        _conversation_history[user_key] = []
    
    # Mantener solo los últimos N turnos de conversación
    if len(_conversation_history[user_key]) >= _MAX_HISTORY_TURNS * 2:  # Multiplicar por 2 porque cada turno tiene user+assistant
        _conversation_history[user_key] = _conversation_history[user_key][-((_MAX_HISTORY_TURNS-1)*2):]
    
    _conversation_history[user_key].append({"role": role, "content": content})
    logger.debug(f"Mensaje añadido al historial de {user_key}: {role}: {content[:50]}... (Longitud: {len(_conversation_history[user_key])})")

def clear_conversation_history(user_key: str):
    """Limpia el historial de conversación para un usuario."""
    global _conversation_history
    if user_key in _conversation_history:
        del _conversation_history[user_key]
        logger.debug(f"Historial de conversación limpiado para {user_key}")

def remove_last_user_message_from_history(user_key: str):
    """Elimina el último mensaje del usuario del historial de conversación.
    
    Útil para evitar registrar mensajes de salida como consultas de RAG.
    
    Args:
        user_key: Clave única del usuario (ej: 'whatsapp:123456789')
    """
    global _conversation_history
    if user_key in _conversation_history:
        # Buscar el último mensaje del usuario para eliminarlo
        for i in range(len(_conversation_history[user_key]) - 1, -1, -1):
            if _conversation_history[user_key][i]['role'] == 'user':
                # Eliminar este mensaje
                removed_message = _conversation_history[user_key].pop(i)
                logger.info(f"Mensaje de usuario eliminado del historial para {user_key}: '{removed_message['content']}'")
                break
        logger.debug(f"Historial de conversación limpiado para {user_key}")

# --- MENSAJES DE SELECCIÓN ---
async def get_company_selection_message(db_session: AsyncSession, user_state_obj: UserState) -> str:
    """
    Genera un mensaje de selección de empresa con emojis numéricos y manejo adecuado de caracteres especiales.
    
    Args:
        db_session: Sesión de base de datos asíncrona
        user_state_obj: Objeto UserState con el estado actual del usuario
        
    Returns:
        str: Mensaje formateado con la lista de empresas numeradas
    """
    logger.info(f"get_company_selection_message para: {user_state_obj.platform}:{user_state_obj.user_id}")
    
    # Forzar la recarga de la caché para obtener los datos más recientes
    companies = await get_all_companies(db_session, force_reload_cache=True)
    
    if not companies:
        return "Lo siento, no puedo mostrar opciones ahora. Intenta 'menu' más tarde."
    
    # Crear lista de opciones con emojis numéricos y nombres de empresas
    options_parts = []
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, comp in enumerate(companies):
        if comp.name:
            # Normalizar el nombre de la empresa para asegurar la codificación correcta
            company_name = comp.name.strip()
            # Reemplazar caracteres problemáticos
            company_name = company_name.replace('‚', 'é').replace('¢', 'ó').replace('¡', 'í')
            
            # Acortar nombres largos de empresas para mayor concisión
            if "Corporativo Ehécatl SA de CV" in company_name:
                company_name = company_name.replace("Corporativo Ehécatl SA de CV", "Corporativo Ehécatl")
            elif "Fundación Desarrollemos México A.C." in company_name:
                company_name = company_name.replace("Fundación Desarrollemos México A.C.", "Fundación Desarrollemos México")
            
            # Usar el emoji numérico si está disponible
            if idx < len(number_emojis):
                option = f"{number_emojis[idx]} {company_name}"
            else:
                # Si hay más opciones que emojis, usar números normales
                option = f"{idx + 1}. {company_name}"
            
            # Asegurarse de que la opción esté en formato UTF-8
            if isinstance(option, str):
                options_parts.append(option.encode('utf-8').decode('utf-8'))
            else:
                options_parts.append(option)
    
    if not options_parts:
        return "Lo siento, problema al mostrar opciones."
    
    options_text = "\n".join(options_parts)
    
    # Crear saludo personalizado
    greeting = "¡Hola! 👋"
    if user_state_obj.collected_name:
        user_first_name = user_state_obj.collected_name.split()[0]
        greeting = f"¡Hola de nuevo, {user_first_name}! 👋" if user_state_obj.current_brand_id else f"¡Hola, {user_first_name}! 👋"
    
    # Mensaje final con codificación explícita
    message = f"""{greeting}
Gracias por contactarnos. Para ayudarte mejor, selecciona la empresa o consultor de tu interés:

{options_text}

Escribe el número o el nombre de la opción."""
    
    return message

async def get_action_selection_message(company_name: Optional[str], user_state_obj: UserState) -> Dict[str, Any]:
    effective_company_name = company_name if company_name and company_name.strip() else "la entidad seleccionada"
    
    greeting_name_part = ""
    if user_state_obj.collected_name:
        user_first_name = user_state_obj.collected_name.split()[0]
        greeting_name_part = f", {user_first_name}"

    message_text = (f"¡Excelente{greeting_name_part}! Has seleccionado *{effective_company_name}*.\n"
                   f"¿Qué te gustaría hacer a continuación?")

    # Botones de acción rápida
    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": "action_rag",
                "title": "🗣️ Consultar"
            }
        },
        {
            "type": "reply",
            "reply": {
                "id": "action_schedule",
                "title": "📅 Agendar"
            }
        }
    ]
    
    # Mantener compatibilidad con el código existente
    text_fallback = f"{message_text}\n\n1. Consultar\n2. Agendar"
    
    return {
        "text": message_text,
        "buttons": buttons,
        "text_fallback": text_fallback  # Para compatibilidad
    }

# (Opcional) Funciones adicionales que podrías necesitar
async def get_user_state_details(db_session: AsyncSession, user_id: str, platform: str) -> Optional[Dict[str, Any]]:
    stmt = select(UserState).filter_by(user_id=user_id, platform=platform)
    result = await db_session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        return {
            "user_id": user.user_id,
            "platform": user.platform,
            "current_brand_id": user.current_brand_id,
            "stage": user.stage,
            "collected_name": user.collected_name,
            "collected_email": user.collected_email,
            "collected_phone": user.collected_phone,
            "purpose_of_inquiry": user.purpose_of_inquiry,
            "is_subscribed": user.is_subscribed,
            "last_interaction_at": user.last_interaction_at,
            "location_info": user.location_info, # Añadido
            "created_at": user.created_at
        }
    return None