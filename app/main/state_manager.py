# app/main/state_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal # <-- CORREGIDO: Usar nombre con mayúsculas
from app.models.user_state import UserState
from app.utils.logger import logger
import datetime

# Constantes para las marcas y el mapeo
VALID_BRANDS = ["Fundacion", "Ehecatl", "Javier Bazan", "UDD", "FES"]
BRAND_SELECTION_MAP = {
    "1": "Fundacion", "fundacion": "Fundacion",
    "2": "Ehecatl", "ehecatl": "Ehecatl",
    "3": "Javier Bazan", "javier bazan": "Javier Bazan", "bazan": "Javier Bazan",
    "4": "UDD", "udd": "UDD", "universidad": "UDD",
    "5": "FES", "fes": "FES", "frente": "FES",
}

async def get_or_create_user_state(session: AsyncSession, user_id: str, platform: str) -> UserState:
    """Obtiene el estado del usuario de la DB, creándolo si no existe."""
    stmt = select(UserState).where(UserState.user_id == user_id, UserState.platform == platform)
    result = await session.execute(stmt)
    user_state = result.scalar_one_or_none()

    if user_state is None:
        logger.info(f"Nuevo usuario: {platform}:{user_id}. Creando estado en DB.")
        user_state = UserState(user_id=user_id, platform=platform, stage="selecting_brand")
        session.add(user_state)
        try:
            # Intentar hacer flush para asegurar que el objeto está en la sesión antes de devolverlo
            await session.flush()
            await session.refresh(user_state) # Opcional, para obtener defaults de DB si los hubiera
        except Exception as flush_err:
            # Si el flush falla (ej. por commit externo concurrente o error DB), loguear y continuar si es posible
            logger.error(f"Error durante flush/refresh al crear UserState para {platform}:{user_id}: {flush_err}")
            # Puede ser necesario re-obtener el estado si el error fue por concurrencia
            # Por simplicidad, devolvemos el objeto creado, pero podría estar detached
    else:
         # Actualizar timestamp de última interacción al obtener el estado
         user_state.last_interaction_at = datetime.datetime.now(datetime.timezone.utc)
         logger.debug(f"Estado encontrado para {platform}:{user_id}: Brand='{user_state.current_brand}', Stage='{user_state.stage}'")

    return user_state

async def update_user_state_db(session: AsyncSession, user_state_obj: UserState, updates: dict):
    """
    Actualiza campos específicos del objeto UserState gestionado por SQLAlchemy.
    NOTA: Esta función modifica el objeto en la sesión, el commit se hace fuera.
    """
    updated = False
    # Siempre actualizar timestamp
    updates["last_interaction_at"] = datetime.datetime.now(datetime.timezone.utc)

    for key, value in updates.items():
        if hasattr(user_state_obj, key):
            if getattr(user_state_obj, key) != value: # Solo actualiza si hay cambio
                setattr(user_state_obj, key, value)
                updated = True
        else:
            logger.warning(f"Intentando actualizar campo inexistente '{key}' en UserState para {user_state_obj.platform}:{user_state_obj.user_id}")

    if updated:
        logger.info(f"Estado preparado para actualización en DB para {user_state_obj.platform}:{user_state_obj.user_id}: {updates}")
        # Marcar el objeto como 'sucio' para que el commit lo guarde
        session.add(user_state_obj)
    else:
         # Aunque no haya cambios en 'updates', actualizamos timestamp
         session.add(user_state_obj)
         logger.debug(f"Timestamp actualizado para {user_state_obj.platform}:{user_state_obj.user_id}")


async def set_user_brand_db(session: AsyncSession, user_id: str, platform: str, user_input: str) -> str | None:
    """
    Intenta establecer la marca en la DB basada en la entrada del usuario.
    Devuelve el nombre de la marca si es válido y se actualiza, o None si no.
    """
    normalized_input = user_input.strip().lower()
    selected_brand = BRAND_SELECTION_MAP.get(normalized_input)

    if selected_brand in VALID_BRANDS:
        user_state = await get_or_create_user_state(session, user_id, platform)
        await update_user_state_db(session, user_state, {"current_brand": selected_brand, "stage": "main_chat"})
        logger.info(f"Marca seleccionada y estado actualizado en DB para {platform}:{user_id}: {selected_brand}")
        return selected_brand
    else:
        logger.warning(f"Input de selección de marca inválido para {platform}:{user_id}: '{user_input}'")
        return None

def get_brand_welcome_message(brand_name: str) -> str:
    """Devuelve el mensaje de bienvenida específico de la marca."""
    welcomes = {
        "Fundacion": "¡Bienvenido/a! Estás en la sección de la Fundación Desarrollemos México. ¿En qué puedo ayudarte sobre becas, donativos u obra pública?",
        "Ehecatl": "Has ingresado a Corporativo Ehecatl SA de CV. ¿Necesitas información sobre soluciones tecnológicas, servicios residenciales o coaching inmobiliario?",
        "Javier Bazan": "Bienvenido/a al espacio de Javier Bazán, Consultor. ¿Te interesa asesoría en imagen, comunicación o estrategia electoral?",
        "UDD": "¡Hola! Estás explorando la Universidad para el Desarrollo Digital (UDD). Recuerda que estamos en consolidación (sin RVOE aún). ¿Quieres saber sobre nuestra visión o áreas de estudio futuras?",
        "FES": "¡Qué onda! Estás en el Frente Estudiantil Social (FES), nuestro laboratorio experimental y NO FORMAL de IA. ¿Quieres saber cómo participar o qué proyectos hay?"
    }
    return welcomes.get(brand_name, f"Bienvenido a {brand_name}.")

def get_initial_brand_selection_message() -> str:
     """Devuelve el mensaje inicial para seleccionar marca."""
     return """¡Hola! 👋 Gracias por contactarnos. Para poder ayudarte mejor, por favor selecciona la marca o área de tu interés:
1️⃣ Fundación
2️⃣ Ehecatl
3️⃣ Javier Bazan
4️⃣ UDD
5️⃣ FES

Escribe el número o nombre de la marca."""