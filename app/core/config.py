# app/core/config.py
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, validator, Field, HttpUrl
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- 1. Definición de PROJECT_ROOT_DIR y carga de .env ---
try:
    PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
except NameError: # Ocurre si se ejecuta de forma interactiva donde __file__ no está definido
    PROJECT_ROOT_DIR = Path(".").resolve()

ENV_FILE_PATH = PROJECT_ROOT_DIR / '.env'
if ENV_FILE_PATH.is_file():
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    # Usar print aquí es más seguro ya que el logger de este módulo se configura después
    print(f"INFO [config.py - Pre-Log]: Archivo .env cargado desde {ENV_FILE_PATH}")
else:
    print(f"INFO [config.py - Pre-Log]: Archivo .env NO encontrado en {ENV_FILE_PATH}")

# --- 2. Logger Mínimo para este Módulo (se usa antes de que el logger principal esté listo) ---
_config_module_logger = logging.getLogger("app.core.config_module")
if not _config_module_logger.hasHandlers():
    _stream_handler_config = logging.StreamHandler()
    _formatter_config = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    _stream_handler_config.setFormatter(_formatter_config)
    _config_module_logger.addHandler(_stream_handler_config)
    _config_module_logger.setLevel(os.getenv("CONFIG_MODULE_LOG_LEVEL", "INFO").upper()) 

_config_module_logger.info(f"PROJECT_ROOT_DIR determinado como: {PROJECT_ROOT_DIR}")

class Settings(BaseSettings):
    # --- Información del Proyecto ---
    PROJECT_NAME: str = Field(default="Chatbot App Default Name", validation_alias="PROJECT_NAME")
    PROJECT_VERSION: str = Field(default="1.0.1", validation_alias="PROJECT_VERSION")
    STARTUP_TIMESTAMP: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # --- Configuración de Paths (se calcularán/confirmarán en model_post_init) ---
    BASE_DIR: Path = PROJECT_ROOT_DIR # Se puede asignar directamente
    DATA_DIR: Optional[Path] = None
    LOG_DIR: Optional[Path] = None
    BRANDS_DIR: Optional[Path] = None
    KNOWLEDGE_BASE_DIR: Optional[Path] = None
    LOG_FILE: Optional[Path] = None # Se calculará en model_post_init

    # --- Base de Datos ---
    # El tipo aquí es Optional[str] porque el validador devuelve un str.
    # PostgresDsn se usa DENTRO del validador para construir/validar.
    DATABASE_URL: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    PGHOST: Optional[str] = Field(default=None, validation_alias="PGHOST")
    PGPORT: Optional[str] = Field(default="5432", validation_alias="PGPORT") # Puede ser string, se convierte a int en validador
    PGDATABASE: Optional[str] = Field(default=None, validation_alias="PGDATABASE")
    PGUSER: Optional[str] = Field(default=None, validation_alias="PGUSER")
    PGPASSWORD: Optional[str] = Field(default=None, validation_alias="PGPASSWORD")
    POSTGRES_SSL_MODE: str = Field(default="require", validation_alias="POSTGRES_SSL_MODE")

    # --- Azure Storage para FAISS ---
    STORAGE_ACCOUNT_NAME: Optional[str] = Field(default=None, validation_alias="STORAGE_ACCOUNT_NAME")
    CONTAINER_NAME: Optional[str] = Field(default=None, validation_alias="CONTAINER_NAME")
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    
    # --- RAG y FAISS ---
    FAISS_INDEX_NAME: str = Field(default="index", validation_alias="FAISS_INDEX_NAME")
    FAISS_FOLDER_NAME: str = Field(default="faiss_index_default", validation_alias="FAISS_FOLDER_NAME")
    FAISS_FOLDER_PATH: Optional[Path] = None # Se calculará en model_post_init
    LOCAL_FAISS_CACHE_PATH: Optional[Path] = None # Opcional, para override de dónde se guarda/busca localmente
    EMBEDDING_MODEL_NAME: str = Field(default='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', validation_alias="EMBEDDING_MODEL_NAME")
    RAG_DEFAULT_K: int = Field(default=3, gt=0, validation_alias="RAG_DEFAULT_K")
    RAG_K_FETCH_MULTIPLIER: int = Field(default=2, gt=0, validation_alias="RAG_K_FETCH_MULTIPLIER")
    RAG_MIN_CONTEXT_LENGTH_THRESHOLD: int = Field(default=50, validation_alias="RAG_MIN_CONTEXT_LENGTH_THRESHOLD")

    # --- LLM y OpenRouter ---
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    OPENROUTER_MODEL_CHAT: str = Field(default="meta-llama/llama-3-8b-instruct", validation_alias="OPENROUTER_MODEL_CHAT")
    OPENROUTER_CHAT_ENDPOINT: HttpUrl = Field(default=HttpUrl("https://openrouter.ai/api/v1"), validation_alias="OPENROUTER_CHAT_ENDPOINT")
    LLM_TEMPERATURE: float = Field(default=0.5, ge=0.0, le=2.0, validation_alias="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=150, gt=0, validation_alias="LLM_MAX_TOKENS")
    LLM_HTTP_TIMEOUT: float = Field(default=45.0, gt=0, validation_alias="LLM_HTTP_TIMEOUT")

    # --- Meta (WhatsApp/Messenger) ---
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = Field(default=None, validation_alias="WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_ACCESS_TOKEN: Optional[str] = Field(default=None, validation_alias="WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_VERIFY_TOKEN: Optional[str] = Field(default=None, validation_alias="VERIFY_TOKEN")
    META_API_VERSION: str = Field(default="v19.0", validation_alias="META_API_VERSION")
    MESSENGER_PAGE_ACCESS_TOKEN: Optional[str] = Field(default=None, validation_alias="MESSENGER_PAGE_ACCESS_TOKEN")

    # --- Palabras Clave para Salida de Conversación ---
    EXIT_CONVERSATION_KEYWORDS: Set[str] = Field(
        default_factory=lambda: {
            "gracias", "muchas gracias", "gracias por tu ayuda", "eso es todo",
            "eso sería todo", "ya terminé", "listo gracias", "ok gracias",
            "no necesito más ayuda", "suficiente por ahora", "ha sido de ayuda"
        },
        description="Palabras clave que indican que el usuario desea finalizar la conversación actual de forma amigable."
    )

    # --- Calendly ---
    CALENDLY_API_KEY: Optional[str] = Field(default=None, validation_alias="CALENDLY_API_KEY")
    CALENDLY_EVENT_TYPE_URI: Optional[HttpUrl] = Field(default=None, validation_alias="CALENDLY_EVENT_TYPE_URI")
    CALENDLY_TIMEZONE: str = Field(default="America/Mexico_City", validation_alias="CALENDLY_TIMEZONE")
    CALENDLY_USER_SLUG: Optional[str] = Field(default=None, validation_alias="CALENDLY_USER_SLUG")
    CALENDLY_DAYS_TO_CHECK: int = Field(default=7, gt=0, validation_alias="CALENDLY_DAYS_TO_CHECK")
    CALENDLY_GENERAL_SCHEDULING_LINK: Optional[HttpUrl] = Field(default=None, validation_alias="CALENDLY_GENERAL_SCHEDULING_LINK")

    # --- Aplicación General ---
    ENVIRONMENT: str = Field(default="development", validation_alias="ENVIRONMENT")
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")
    # Campo para leer del .env, se normalizará a self.LOG_LEVEL (en mayúsculas)
    LOG_LEVEL_FROM_ENV: str = Field(default="INFO", validation_alias="LOG_LEVEL") 
    LOG_LEVEL: str = "INFO" # Atributo final, se establecerá correctamente en model_post_init
    LOG_FORMAT: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s', validation_alias="LOG_FORMAT")
    LOG_MAX_SIZE_BYTES: int = Field(default=10 * 1024 * 1024, validation_alias="LOG_MAX_SIZE_BYTES")
    LOG_BACKUP_COUNT: int = Field(default=5, validation_alias="LOG_BACKUP_COUNT")
    
    SERVER_HOST: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    SERVER_PORT: int = Field(default=8000, validation_alias="SERVER_PORT")
    PROJECT_SITE_URL: HttpUrl = Field(default=HttpUrl("http://localhost:8000"), validation_alias="PROJECT_SITE_URL")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    @validator("DATABASE_URL", pre=True, always=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]: # Devuelve Optional[str]
        # 'values' aquí es un ModelValidator. Reemplazado con values.data para acceder a los campos.
        # O mejor, usar values.get("nombre_campo")
        
        # Si DATABASE_URL se proporciona explícitamente en .env o var de entorno, usarla.
        if isinstance(v, str) and v.strip():
            _config_module_logger.info(f"DATABASE_URL provista directamente: ...{v[v.find('@'):] if '@' in v else v}")
            return v # Devuelve el string provisto
        
        _config_module_logger.info("DATABASE_URL no provista directamente. Intentando construir desde componentes PG*...")
        # Acceder a los valores de forma segura
        pg_user = values.data.get("PGUSER")
        pg_password = values.data.get("PGPASSWORD")
        pg_host = values.data.get("PGHOST")
        pg_port_str = values.data.get("PGPORT", "5432") # Default como string
        pg_database = values.data.get("PGDATABASE")
        pg_ssl_mode = values.data.get("POSTGRES_SSL_MODE", "require")

        if not all([pg_user, pg_host, pg_database]):
            _config_module_logger.warning("Componentes PGUSER, PGHOST o PGDATABASE faltantes. No se puede construir DATABASE_URL.")
            return None

        try:
            pg_port_int = int(pg_port_str) # Convertir a int para PostgresDsn.build
        except (ValueError, TypeError):
            _config_module_logger.warning(f"PGPORT '{pg_port_str}' no es un entero válido. Usando 5432 por defecto.")
            pg_port_int = 5432
        
        try:
            dsn_object = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=pg_user,
                password=pg_password, # Puede ser None
                host=pg_host,
                port=pg_port_int,
                path=f"/{pg_database}" # path debe empezar con /
            )
            # Convertir el objeto DSN a string para poder añadir parámetros query
            final_dsn_str = str(dsn_object)

            # Añadir ?ssl=pg_ssl_mode si no está deshabilitado y no está ya en la DSN
            if pg_ssl_mode and pg_ssl_mode.lower() != "disable":
                param_to_add = f"ssl={pg_ssl_mode}"
                if "?" in final_dsn_str: # Ya hay otros parámetros query
                    if param_to_add not in final_dsn_str: # Evitar duplicar
                        final_dsn_str += f"&{param_to_add}"
                else: # No hay parámetros query
                    final_dsn_str += f"?{param_to_add}"
            
            _config_module_logger.info(f"DATABASE_URL construida internamente: ...@{pg_host}:{pg_port_int}/{pg_database} (con SSL: {pg_ssl_mode})")
            return final_dsn_str
        except Exception as e_dsn_build:
            _config_module_logger.error(f"Error construyendo PostgresDsn desde componentes: {e_dsn_build}", exc_info=True)
            return None # Falló la construcción
        
    def model_post_init(self, __context: Any) -> None:
        _config_module_logger.info("Ejecutando model_post_init para Settings (cálculo de paths y normalizaciones finales)...")
        
        # Normalizar y asignar LOG_LEVEL (el atributo final que usará la app)
        # self.LOG_LEVEL_FROM_ENV es el valor leído del .env o el default "INFO"
        env_log_val = self.LOG_LEVEL_FROM_ENV 
        normalized_log_level = env_log_val.upper()
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        final_log_level_to_set = "INFO" # Default si la normalización falla
        if normalized_log_level in valid_log_levels:
            final_log_level_to_set = normalized_log_level
        else:
            _config_module_logger.warning(f"  Valor de LOG_LEVEL_FROM_ENV ('{env_log_val}') es inválido. Usando INFO para el atributo LOG_LEVEL.")
        
        # Usar object.__setattr__ para modificar el campo después de la inicialización de Pydantic
        object.__setattr__(self, 'LOG_LEVEL', final_log_level_to_set) 
        _config_module_logger.info(f"  model_post_init: Atributo self.LOG_LEVEL (final) establecido a: {self.LOG_LEVEL}")

        # Calcular Paths (BASE_DIR ya está asignado)
        # Asegurar que self.BASE_DIR sea Path
        base_dir_path = Path(self.BASE_DIR)
        data_dir_val = base_dir_path / "data"
        log_dir_val = base_dir_path / "logs"
        
        object.__setattr__(self, 'DATA_DIR', data_dir_val)
        object.__setattr__(self, 'LOG_DIR', log_dir_val)
        
        sanitized_project_name = self.PROJECT_NAME.lower().replace(' ', '_').replace(':', '_')
        object.__setattr__(self, 'LOG_FILE', log_dir_val / f"{sanitized_project_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log")
        
        object.__setattr__(self, 'BRANDS_DIR', data_dir_val / "brands")
        object.__setattr__(self, 'KNOWLEDGE_BASE_DIR', base_dir_path / "knowledge_base")
        
        # FAISS_FOLDER_NAME es el nombre del subdirectorio específico del índice dentro de DATA_DIR
        object.__setattr__(self, 'FAISS_FOLDER_PATH', data_dir_val / self.FAISS_FOLDER_NAME)

        # Crear directorios necesarios
        dirs_to_create: List[Path] = []
        # Añadir solo si los paths no son None y son Path
        if self.LOG_DIR and isinstance(self.LOG_DIR, Path): dirs_to_create.append(self.LOG_DIR)
        if self.DATA_DIR and isinstance(self.DATA_DIR, Path): dirs_to_create.append(self.DATA_DIR)
        if self.BRANDS_DIR and isinstance(self.BRANDS_DIR, Path): dirs_to_create.append(self.BRANDS_DIR)
        if self.KNOWLEDGE_BASE_DIR and isinstance(self.KNOWLEDGE_BASE_DIR, Path): dirs_to_create.append(self.KNOWLEDGE_BASE_DIR)
        if self.FAISS_FOLDER_PATH and isinstance(self.FAISS_FOLDER_PATH, Path): dirs_to_create.append(self.FAISS_FOLDER_PATH)
        if self.LOCAL_FAISS_CACHE_PATH and isinstance(self.LOCAL_FAISS_CACHE_PATH, Path): dirs_to_create.append(self.LOCAL_FAISS_CACHE_PATH)

        for dir_path_obj in dirs_to_create:
            try:
                dir_path_obj.mkdir(parents=True, exist_ok=True)
                _config_module_logger.debug(f"  Directorio asegurado/creado: {dir_path_obj}")
            except Exception as e_mkdir_paths:
                _config_module_logger.error(f"  No se pudo crear directorio {dir_path_obj}: {e_mkdir_paths}")
        
        _config_module_logger.info("model_post_init finalizado.")

# --- Singleton para la instancia de Settings ---
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _config_module_logger.debug("get_settings(): Creando NUEVA instancia de Settings...")
        try:
            _settings_instance = Settings() # __init__ y model_post_init se ejecutan aquí
            # Loguear después de que la instancia esté completamente formada
            _log_essential_settings_info(_settings_instance)
        except Exception as e_settings_creation: 
            _config_module_logger.critical(f"ERROR FATAL creando instancia de Settings en get_settings(): {e_settings_creation}", exc_info=True)
            raise RuntimeError(f"La carga de configuración (Settings) falló críticamente: {e_settings_creation}")
    return _settings_instance

def _log_essential_settings_info(s: Settings):
    """Loguea un resumen de la configuración cargada DESPUÉS de model_post_init."""
    _config_module_logger.info("--- Resumen Configuración (después de model_post_init) ---")
    _config_module_logger.info(f"  PROJECT_NAME: {s.PROJECT_NAME}, VERSION: {s.PROJECT_VERSION}")
    _config_module_logger.info(f"  LOG_LEVEL (final para la app): {s.LOG_LEVEL}") # Usar el atributo LOG_LEVEL final
    if s.LOG_FILE: _config_module_logger.info(f"  LOG_FILE: {s.LOG_FILE}")
    if s.FAISS_FOLDER_PATH: _config_module_logger.info(f"  FAISS_FOLDER_PATH (contendrá '{s.FAISS_INDEX_NAME}.faiss/.pkl'): {s.FAISS_FOLDER_PATH}")
    
    db_url_display = "NO CONFIGURADA O ERROR EN CONSTRUCCIÓN"
    if s.DATABASE_URL and isinstance(s.DATABASE_URL, str): # s.DATABASE_URL ahora debería ser string
        try:
            # Parsear el string DATABASE_URL para acceder a sus componentes de forma segura para logging
            parsed_dsn_for_log = PostgresDsn(s.DATABASE_URL) 
            
            scheme_log = parsed_dsn_for_log.scheme or "N/A"
            username_log = parsed_dsn_for_log.username or "N/A" 
            host_log = parsed_dsn_for_log.host or "N/A"
            port_log = str(parsed_dsn_for_log.port) if parsed_dsn_for_log.port is not None else "N/A"
            path_log = parsed_dsn_for_log.path or "/N/A"
            query_log = parsed_dsn_for_log.query or ""
            
            db_url_display = f"{scheme_log}://{username_log}:***@{host_log}:{port_log}{path_log}"
            if query_log: 
                db_url_display += f"?{query_log}"

        except Exception as e_parse_log_display_final:
            db_url_display = (f"Formato DSN inválido al intentar loguear ({e_parse_log_display_final}). "
                              f"Valor (preview): {s.DATABASE_URL[:s.DATABASE_URL.find('@') if '@' in s.DATABASE_URL else 30]}...")
    
    _config_module_logger.info(f"  DATABASE_URL (final): {db_url_display}")
    
    # Verificación de variables críticas (usa los nombres de atributos de la clase Settings)
    critical_vars = {
        "DATABASE_URL": s.DATABASE_URL, 
        "WHATSAPP_ACCESS_TOKEN": s.WHATSAPP_ACCESS_TOKEN,
        "WHATSAPP_PHONE_NUMBER_ID": s.WHATSAPP_PHONE_NUMBER_ID, 
        "WHATSAPP_VERIFY_TOKEN": s.WHATSAPP_VERIFY_TOKEN, # Atributo de la clase Settings
        "OPENROUTER_API_KEY": s.OPENROUTER_API_KEY, 
        "STORAGE_ACCOUNT_NAME": s.STORAGE_ACCOUNT_NAME,
        "CONTAINER_NAME": s.CONTAINER_NAME, 
        "FAISS_INDEX_NAME": s.FAISS_INDEX_NAME
    }
    missing = [k_attr for k_attr, v_val in critical_vars.items() if not v_val]
    if missing: 
        _config_module_logger.critical(f"  ¡¡ADVERTENCIA CRÍTICA!! Faltan/vacías variables (nombres de atributo en Settings): {', '.join(missing)}")
    else: 
        _config_module_logger.info("  Verificación de variables críticas básicas: OK.")
    _config_module_logger.info("-" * 60)

async def get_brand_context(brand_name_original: str) -> Optional[str]:
    current_app_settings = get_settings() 
    if not current_app_settings:
        _config_module_logger.error("get_brand_context: No se pudo obtener 'settings'.")
        return None
    
    # Asegurarse de que BRANDS_DIR sea un Path y exista
    brands_dir_path = getattr(current_app_settings, 'BRANDS_DIR', None)
    if not brands_dir_path or not isinstance(brands_dir_path, Path) or not brands_dir_path.is_dir():
        _config_module_logger.error(f"get_brand_context: BRANDS_DIR ('{brands_dir_path}') no es un directorio válido o no está configurado.")
        return None

    def _internal_normalize_brand_name(name: str) -> str: # Función de normalización interna
        import re
        from unidecode import unidecode as unidecode_function # Renombrar para evitar conflicto
        if not isinstance(name, str) or not name.strip(): return "invalid_brand_name_file_target"
        
        s = unidecode_function(name).lower()
        s = re.sub(r'[^\w\s-]', '', s)  # Permitir alfanuméricos, espacios, guiones
        s = re.sub(r'\s+', '_', s)      # Reemplazar espacios con guiones bajos
        # Quitar cualquier cosa que no sea letra, número, guion bajo o guion.
        s = re.sub(r'[^a-z0-9_-]', '', s) 
        s = s.strip('_')
        return s if s else "normalized_to_empty_target" # Devolver un string si queda vacío

    normalized_filename_part = _internal_normalize_brand_name(brand_name_original)
    
    if "invalid" in normalized_filename_part or "empty" in normalized_filename_part:
        _config_module_logger.warning(f"get_brand_context: Nombre de marca '{brand_name_original}' resultó en nombre de archivo inválido/vacío tras normalizar: '{normalized_filename_part}'")
        return None

    file_path_to_try = brands_dir_path / f"{normalized_filename_part}.txt"

    if not file_path_to_try.is_file():
        _config_module_logger.warning(f"get_brand_context: Archivo de contexto de marca no encontrado para '{brand_name_original}' en la ruta esperada '{file_path_to_try}'.")
        # Podrías añadir una lógica de fallback para probar con el nombre original si es necesario, pero la normalización es preferible.
        return None
    try:
        with open(file_path_to_try, mode='r', encoding='utf-8') as f: 
            content = f.read().strip()
        
        if not content: 
            _config_module_logger.warning(f"get_brand_context: Archivo de contexto '{file_path_to_try.name}' para '{brand_name_original}' está vacío.")
            return None # O devolver "" si un string vacío es un contexto válido para ti
            
        _config_module_logger.info(f"Contexto cargado exitosamente para la marca '{brand_name_original}' desde el archivo '{file_path_to_try.name}'. Longitud: {len(content)}.")
        return content
        
    except Exception as e_file_read:
        _config_module_logger.error(f"get_brand_context: Error al leer el archivo de contexto de marca '{file_path_to_try.name}' para '{brand_name_original}': {e_file_read}", exc_info=True)
        return None

# --- Instancia Global de Settings ---
# Se crea una vez cuando este módulo es importado por primera vez.
settings: Settings = get_settings() # Llama a la función que maneja el singleton

# --- Verificación final al cargar el módulo ---
if settings is None: # No debería pasar si get_settings() lanza RuntimeError
    _config_module_logger.critical("CRÍTICO [config.py - Nivel Módulo]: La instancia 'settings' es None después de llamar a get_settings(). La aplicación probablemente no funcionará.")
else:
    _config_module_logger.info(f"Módulo de config.py cargado y la instancia 'settings' está disponible. PROJECT_NAME: {settings.PROJECT_NAME}. LOG_LEVEL final de app: {settings.LOG_LEVEL}.")