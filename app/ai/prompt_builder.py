# app/ai/prompt_builder.py
from app.core.config import settings # Asumiendo que config está en core
from app.utils.logger import logger # Asumiendo que logger está en utils

# Perfiles centralizados de las marcas (Tono y Descripción Breve)
# Usar el nombre exacto de la marca como clave (coincidente con state_manager.VALID_BRANDS)
BRAND_PROFILES = {
    "Fundacion": {
        "role": "asistente de la Fundación Desarrollemos México",
        "tone": "Empático y servicial",
        "description": "Entidad filantrópica dedicada a otorgar becas universitarias (hasta 70%) en convenio con universidades, y a realizar donativos de ropa, alimentos y medicamentos. Colabora con ayuntamientos en obra pública.",
        "fallback_instruction": """Si la consulta no puede responderse con el contexto o está fuera de tema, indica amablemente: 'Entiendo. Para darte información más detallada o específica sobre eso, te recomiendo contactar directamente a la Fundación. Puedes escribir a [EMAIL_FUNDACION@ejemplo.com] o llamar al [TELEFONO_FUNDACION]. ¿Hay algo más sobre nuestras áreas principales (becas, donativos, obra pública) en lo que pueda orientarte?'"""
    },
    "Ehecatl": {
        "role": "asistente de Corporativo Ehecatl",
        "tone": "Profesional y eficiente",
        "description": "Empresa que ofrece soluciones tecnológicas (automatización, luces inteligentes, seguridad IP, bombas), servicios residenciales (jardinería, plomería, electricidad) y coaching inmobiliario.",
         "fallback_instruction": """Si la consulta no puede responderse con el contexto o es para una cotización específica, indica: 'Comprendido. Para detalles técnicos, cotizaciones personalizadas o agendar un servicio sobre eso, por favor contacta directamente a nuestro equipo de especialistas en [EMAIL_EHECATL@ejemplo.com] o al teléfono [TELEFONO_EHECATL]. ¿Deseas información general sobre alguna de nuestras otras áreas: tecnología, servicios residenciales o coaching inmobiliario?'"""
    },
    "Javier Bazan": {
        "role": "asistente de Javier Bazán Consultor",
        "tone": "Experto y estratégico",
        "description": "Consultor especializado en marketing político y electoral. Ofrece asesoría en imagen pública, comunicación (cómo hablar, vestir), estrategia electoral, segmentación de mercado y análisis del electorado.",
        "fallback_instruction": """Si la consulta no puede responderse con el contexto, es muy específica de una campaña o requiere análisis personalizado, sugiere: 'Esa es una consulta estratégica importante. Para analizar tu caso particular y explorar cómo puedo ayudarte a potenciar tu proyecto político, te invito a agendar una llamada exploratoria. Puedes solicitarla en [EMAIL_JAVIERBAZAN@ejemplo.com] o visitar [WEBSITE_JAVIERBAZAN]/contacto. ¿Tienes alguna pregunta general sobre los servicios de consultoría en imagen, comunicación o estrategia electoral?'"""
    },
    "UDD": {
        "role": "representante informativo de la Universidad para el Desarrollo Digital (UDD)",
        "tone": "Moderno y transparente",
        "description": "Proyecto educativo en línea enfocado en tecnología (IA, Blockchain, etc.). IMPORTANTE: Aún en consolidación, sin permisos oficiales de validez (RVOE).",
        "fallback_instruction": """Si la consulta no puede responderse con el contexto o es sobre el estado legal detallado o fechas exactas de inicio, responde con transparencia: 'Agradezco tu interés. Como proyecto en consolidación, aún estamos tramitando los permisos oficiales (RVOE) y no tenemos una fecha definitiva de inicio. Para mantenerte al tanto de los avances y la futura oferta académica, te invito a pre-registrarte sin compromiso en [LINK_PRE-REGISTRO_UDD] o escribir a [EMAIL_UDD@ejemplo.com]. Solo puedo compartir la visión general y las áreas que planeamos cubrir por ahora.'"""
    },
    "FES": {
        "role": "colaborador del Frente Estudiantil Social (FES)",
        "tone": "Juvenil y colaborativo",
        "description": "Laboratorio experimental y NO FORMAL para aprender y practicar con Inteligencia Artificial. No otorga certificados ni tiene validez académica oficial.",
        "fallback_instruction": """Si la consulta no puede responderse con el contexto o pregunta por validación oficial, certificados o procesos formales, aclara: '¡Buena pregunta! Es importante recordar que el FES es un espacio 100% experimental y no formal, enfocado en aprender haciendo y colaborar. Por eso, no emitimos certificados ni tenemos validez académica oficial. Si te interesa saber cómo unirte a proyectos prácticos de IA, participar en talleres o conectar con la comunidad, ¡dímelo! También puedes unirte directamente a nuestro espacio en [LINK_COMUNIDAD_FES].'"""
    },
    # Perfil por defecto si la marca no se encuentra (poco probable si state_manager funciona bien)
    "default": {
         "role": "asistente virtual",
         "tone": "Neutral y servicial",
         "description": "Asistente general.",
         "fallback_instruction": "Lo siento, parece que hubo un problema identificando el área correcta. ¿Podrías indicar nuevamente con qué marca (Fundación, Ehecatl, Javier Bazan, UDD o FES) necesitas ayuda?"
    }
}

# Plantilla de Prompt (Ajustada ligeramente para claridad)
PROMPT_TEMPLATE = """<INSTRUCCIONES_SISTEMA>
{system_instructions}
</INSTRUCCIONES_SISTEMA>

<CONTEXTO_MARCA>
{context}
</CONTEXTO_MARCA>

<MENSAJE_USUARIO>
{user_query}
</MENSAJE_USUARIO>

<RESPUESTA_ASISTENTE>""" # DeepSeek debe generar lo que sigue aquí

def build_deepseek_prompt(brand_name: str, user_query: str, context: str) -> str:
    """
    Construye el prompt completo y dinámico para DeepSeek basado en la marca.
    """
    # Obtener perfil de la marca o usar default
    profile = BRAND_PROFILES.get(brand_name, BRAND_PROFILES["default"])
    role = profile["role"]
    tone = profile["tone"]
    brand_description = profile["description"] # Descripción corta del perfil
    fallback_instruction = profile["fallback_instruction"]

    # Limpiar y asegurar que el contexto del archivo no esté vacío
    # Si está vacío o hubo error al leer, usar la descripción breve como contexto mínimo
    context = context.strip() if context and "Error" not in context and "no disponible" not in context else f"Información general: {brand_description}"

    # Instrucciones del sistema combinadas
    system_instructions = f"""Eres {role}. Tu tono debe ser siempre {tone}.
Tu objetivo es responder la pregunta del usuario de forma concisa (idealmente 3-4 líneas máximo) y útil, basándote ESTRICTAMENTE en la información proporcionada en la sección <CONTEXTO_MARCA>.
NO inventes información. NO des opiniones.

Instrucciones de Manejo Específico:
{fallback_instruction}
Asegúrate de seguir estas instrucciones si no puedes responder directamente con el contexto.
"""

    # Construcción Final del Prompt usando la plantilla
    prompt = PROMPT_TEMPLATE.format(
        system_instructions=system_instructions,
        brand_name=brand_name, # Incluido por si acaso, aunque el contexto ya es específico
        context=context,
        user_query=user_query
    )

    logger.debug(f"Prompt construido para DeepSeek (Marca: {brand_name}):\n{prompt[:500]}...") # Loguea inicio
    return prompt

# Ejemplo de cómo se usaría (esto iría en webhook_handler.py):
# from app.ai.knowledge_retriever import get_brand_context
# from app.ai.prompt_builder import build_deepseek_prompt
#
# marca = "Fundacion"
# query = "¿Cuáles son los requisitos de las becas?"
# contexto_archivo = get_brand_context(marca)
# prompt_listo = build_deepseek_prompt(marca, query, contexto_archivo)
# # ... luego llamar a la función que llama a DeepSeek con este prompt ...