import os
import logging
from pathlib import Path
from typing import Optional, List, Union, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, HttpUrl
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- 1. Calcular PROJECT_ROOT_DIR (La Raíz de Tu Proyecto) ---
# Esto asume que config.py está en app/core/config.py
try:
    PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
except NameError:
    PROJECT_ROOT_DIR = Path(".").resolve() # Fallback al directorio de trabajo actual

# --- 2. Cargar Archivo .env (principalmente para desarrollo local) ---
ENV_FILE_PATH = PROJECT_ROOT_DIR / '.env'
if ENV_FILE_PATH.is_file():
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    # print(f"INFO [config.py]: Archivo .env cargado desde {ENV_FILE_PATH}") # Para depuración
else:
    # print(f"INFO [config.py]: Archivo .env NO encontrado en {ENV_FILE_PATH}")
    pass # Es normal que no exista en producción (Azure)

# --- 3. Configuración de Logging Mínima para este Módulo ---
_LOG_FORMAT_DEFAULT_CONFIG = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
_config_module_logger = logging.getLogger("app.core.config_loader_module")
if not _config_module_logger.hasHandlers():
    _stream_handler_config = logging.StreamHandler()
    _formatter_config = logging.Formatter(_LOG_FORMAT_DEFAULT_CONFIG, datefmt='%Y-%m-%d %H:%M:%S')
    _stream_handler_config.setFormatter(_formatter_config)
    _config_module_logger.addHandler(_stream_handler_config)
    _config_module_logger.setLevel(os.getenv("INIT_LOG_LEVEL", "INFO").upper())

_config_module_logger.info(f"PROJECT_ROOT_DIR: {PROJECT_ROOT_DIR}")
_config_module_logger.info(f"Pydantic intentará cargar variables desde: '{ENV_FILE_PATH}' (si existe) y el entorno del sistema.")


class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Chatbot_App_Default_Name"
    PROJECT_VERSION: str = "1.0.0"  # Added this line
    VERSION: str = "1.0.0"  # Keep this for backward compatibility
    STARTUP_TIMESTAMP: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
        # Add these inside the Settings class
    azure_storage_connection_string: Optional[str] = Field(default=None, validation_alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_webapp_name: Optional[str] = Field(default=None, validation_alias="AZURE_WEBAPP_NAME")
    azure_resource_group: Optional[str] = Field(default=None, validation_alias="AZURE_RESOURCE_GROUP")
    azure_location: str = Field(default="eastus", validation_alias="AZURE_LOCATION")
    LLM_TEMPERATURE: float = Field(default=0.5, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=1000, gt=0)

    whatsapp_phone_number_id: Optional[str] = Field(default=None, validation_alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_access_token: Optional[str] = Field(default=None, validation_alias="WHATSAPP_ACCESS_TOKEN")
    meta_api_version: str = Field(default="v19.0", validation_alias="META_API_VERSION")
    messenger_page_access_token: Optional[str] = Field(default=None, validation_alias="MESSENGER_PAGE_ACCESS_TOKEN")
    verify_token: Optional[str] = Field(default=None, validation_alias="VERIFY_TOKEN")

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL_CHAT: str = Field(default="mistralai/mistral-7b-instruct-v0.2")
    OPENROUTER_CHAT_ENDPOINT: HttpUrl = Field(default="https://openrouter.ai/api/v1")

    HTTP_CLIENT_TIMEOUT: float = Field(default=30.0, gt=0)

    pguser: Optional[str] = Field(default=None, validation_alias="PGUSER")
    pgpassword: Optional[str] = Field(default=None, validation_alias="PGPASSWORD")
    pghost: Optional[str] = Field(default=None, validation_alias="PGHOST")
    pgdatabase: Optional[str] = Field(default=None, validation_alias="PGDATABASE")
    pgport: int = Field(default=5432, validation_alias="PGPORT")
    # database_url se calculará en __init__ si no se provee directamente
    database_url_env: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")


    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default=_LOG_FORMAT_DEFAULT_CONFIG, validation_alias="LOG_FORMAT")
    log_max_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0, validation_alias="LOG_MAX_SIZE_BYTES")
    log_backup_count: int = Field(default=5, ge=0, validation_alias="LOG_BACKUP_COUNT")

    storage_account_name: Optional[str] = Field(default=None, validation_alias="STORAGE_ACCOUNT_NAME")
    container_name: Optional[str] = Field(default=None, validation_alias="CONTAINER_NAME")

    embedding_model_name: str = Field(default='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', validation_alias="EMBEDDING_MODEL_NAME")
    faiss_index_name: str = Field(default="index", validation_alias="FAISS_INDEX_NAME")
    faiss_folder_name: str = Field(default="faiss_index_kb_spanish_v1", validation_alias="FAISS_FOLDER_NAME")
    vector_db_type: str = Field(default="FAISS", validation_alias="VECTOR_DB_TYPE")
    rag_default_k: int = Field(default=3, ge=1, le=10, validation_alias="RAG_DEFAULT_K")
    rag_k_fetch_multiplier: int = Field(default=2, validation_alias="RAG_K_FETCH_MULTIPLIER")
    
    calendly_api_key: Optional[str] = Field(default=None, validation_alias="CALENDLY_API_KEY")
    calendly_event_type_uri: Optional[HttpUrl] = Field(default=None, validation_alias="CALENDLY_EVENT_TYPE_URI")
    calendly_timezone: str = Field(default="America/Mexico_City", validation_alias="CALENDLY_TIMEZONE")
    calendly_user_slug: Optional[str] = Field(default=None, validation_alias="CALENDLY_USER_SLUG")
    calendly_days_to_check: int = Field(default=7, gt=0, le=60, validation_alias="CALENDLY_DAYS_TO_CHECK")

    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    server_port: int = Field(default=8000, gt=1023, lt=65536, validation_alias="SERVER_PORT")

    # --- Campos que serán calculados y asignados en __init__ ---
    # Se declaran como Optional o con un valor inicial que no cause error de "missing"
    # O simplemente se declaran con su tipo y se asignan en __init__ usando object.__setattr__
    BASE_DIR: Path = PROJECT_ROOT_DIR # Se asigna un valor por defecto válido
    DATA_DIR: Optional[Path] = None
    BRANDS_DIR: Optional[Path] = None
    LOG_DIR: Optional[Path] = None
    KNOWLEDGE_BASE_DIR: Optional[Path] = None
    log_file: Optional[Path] = None
    faiss_folder_path: Optional[Path] = None
    database_url: Optional[str] = None # Valor final de database_url

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    def __init__(self, **kwargs: Any):
        # Paso 1: Pydantic carga valores desde .env, entorno, o kwargs en `self`
        super().__init__(**kwargs)

        # Paso 2: Asignar/Calcular paths dinámicos.
        # BASE_DIR ya está asignado a PROJECT_ROOT_DIR por su default.
        # Para los demás, usamos object.__setattr__ para asegurar la asignación
        # después de la inicialización de Pydantic.

        # DATA_DIR
        data_dir_val = self.BASE_DIR / "data"
        object.__setattr__(self, 'DATA_DIR', data_dir_val)

        # LOG_DIR y log_file
        log_dir_val = self.BASE_DIR / "logs"
        object.__setattr__(self, 'LOG_DIR', log_dir_val)
        log_file_val = log_dir_val / f"chatbot_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        object.__setattr__(self, 'log_file', log_file_val)
        
        # BRANDS_DIR
        brands_dir_val = data_dir_val / "brands"
        object.__setattr__(self, 'BRANDS_DIR', brands_dir_val)

        # KNOWLEDGE_BASE_DIR
        knowledge_base_dir_val = self.BASE_DIR / "knowledge_base"
        object.__setattr__(self, 'KNOWLEDGE_BASE_DIR', knowledge_base_dir_val)
        
        # faiss_folder_path (usa self.faiss_folder_name que fue cargado por super())
        faiss_folder_path_val = data_dir_val / self.faiss_folder_name
        object.__setattr__(self, 'faiss_folder_path', faiss_folder_path_val)
        
        # Paso 3: Crear directorios necesarios
        dirs_to_create: List[Path] = [
            self.LOG_DIR, self.DATA_DIR, self.BRANDS_DIR, 
            self.KNOWLEDGE_BASE_DIR, self.faiss_folder_path
        ]
        for dir_path in dirs_to_create:
            if dir_path:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    _config_module_logger.debug(f"  Directorio asegurado/creado: {dir_path}")
                except Exception as e_mkdir:
                    _config_module_logger.error(f"  No se pudo crear directorio {dir_path}: {e_mkdir}")

        # Paso 4: Lógica adicional
        # Normalizar log_level
        current_log_level = self.log_level.upper()
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if current_log_level not in valid_log_levels:
            _config_module_logger.warning(f"  LOG_LEVEL '{current_log_level}' inválido. Usando INFO por defecto.")
            object.__setattr__(self, 'log_level', "INFO")
        else:
            # Si ya es válido, no necesitamos reasignarlo a menos que queramos forzar el upper case
             object.__setattr__(self, 'log_level', current_log_level)


        # Construir database_url si no se proveyó explícitamente via DATABASE_URL y los componentes están disponibles
        # Usamos self.database_url_env para el valor leído del entorno y self.database_url para el final
        if self.database_url_env: # Si DATABASE_URL fue provista en .env o var de entorno
            object.__setattr__(self, 'database_url', self.database_url_env)
            _config_module_logger.info(f"  DATABASE_URL provista directamente y usada.")
        elif all([self.pguser, self.pgpassword, self.pghost, self.pgdatabase, self.pgport]):
            constructed_db_url = f"postgresql+asyncpg://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}?ssl=require"
            object.__setattr__(self, 'database_url', constructed_db_url)
            _config_module_logger.info(f"  DATABASE_URL construida internamente: postgresql+asyncpg://{self.pguser}:***@{self.pghost}:{self.pgport}/{self.pgdatabase}?ssl=require")
        else:
             _config_module_logger.critical("  DATABASE_URL no se proveyó ni se pudo construir. La conexión a la base de datos fallará.")
        
        _config_module_logger.info("Finalizada inicialización personalizada de Settings y cálculo de paths.")

    def get_version(self) -> str:
        """Returns the project version consistently"""
        return self.PROJECT_VERSION or self.VERSION

# --- Singleton para la instancia de Settings ---
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _config_module_logger.debug("get_settings(): Creando nueva instancia de Settings...")
        try:
            _settings_instance = Settings() # Llama a __init__ de arriba
            _config_module_logger.info("Instancia de Settings creada y validada exitosamente por Pydantic.")
            _log_essential_settings_info(_settings_instance)
        except Exception as e_load: 
            _config_module_logger.critical(f"ERROR FATAL creando instancia de Settings en get_settings(): {e_load}", exc_info=True)
            if hasattr(e_load, 'errors') and callable(getattr(e_load, 'errors', None)): 
                try:
                    validation_errors = e_load.errors()
                    _config_module_logger.critical(f"Detalles de validación de Pydantic: {validation_errors}")
                except Exception as e_val_detail:
                    _config_module_logger.critical(f"No se pudieron obtener detalles de validación de Pydantic: {e_val_detail}")
            raise RuntimeError(f"La carga de configuración de la aplicación falló críticamente: {e_load}")
    return _settings_instance

def _log_essential_settings_info(s: Settings):
    _config_module_logger.info("--- Resumen de Configuración Cargada (desde get_settings) ---")
    _config_module_logger.info(f"  PROJECT_NAME: {s.PROJECT_NAME}, VERSION: {s.VERSION}")
    _config_module_logger.info(f"  LOG_LEVEL (app): {s.log_level}")
    if s.log_file: _config_module_logger.info(f"  LOG_FILE (app): {s.log_file}")
    if s.BASE_DIR: _config_module_logger.info(f"  BASE_DIR: {s.BASE_DIR}")
    if s.DATA_DIR: _config_module_logger.info(f"  DATA_DIR: {s.DATA_DIR}")
    if s.faiss_folder_path: 
        _config_module_logger.info(f"  FAISS Folder Path: {s.faiss_folder_path}")
        if not s.faiss_folder_path.is_dir():
             _config_module_logger.warning(f"  ¡ADVERTENCIA! La carpeta FAISS calculada NO EXISTE: {s.faiss_folder_path}")
    
    db_url_display = 'AUSENTE O NO CONSTRUIDA'
    if s.database_url: # Usar el campo final self.database_url
        parts = s.database_url.split('@')
        db_url_display = f"...@{parts[-1]}" if len(parts) > 1 else "Formato no estándar o incompleta"
    _config_module_logger.info(f"  DATABASE_URL (final para conexión): {db_url_display}")

    critical_vars_check = {
        "DATABASE_URL": s.database_url,
        "WHATSAPP_ACCESS_TOKEN": s.whatsapp_access_token,
        "WHATSAPP_PHONE_NUMBER_ID": s.whatsapp_phone_number_id,
        "VERIFY_TOKEN": s.verify_token,
    }
    missing_critical = [k_env for k_env, attr_val in critical_vars_check.items() if not attr_val]
    if missing_critical:
        _config_module_logger.critical(f"  ¡¡VARIABLES CRÍTICAS FALTANTES!!: {', '.join(missing_critical)}")
    else:
        _config_module_logger.info("  Verificación básica de variables críticas: OK.")
    _config_module_logger.info("---------------------------------------------------")

# --- Instancia Global de Settings (se crea al importar este módulo) ---
try:
    settings = get_settings()
except RuntimeError:
    settings = None 
    # El error ya fue logueado extensamente por get_settings()
    # Tu app/__init__.py debería verificar si settings es None y salir si es necesario.

# --- Funciones de utilidad que usan 'settings' (como get_brand_context) ---
# Deben estar después de la inicialización de 'settings' o tomar 'settings' como argumento.
# Ejemplo de cómo get_brand_context podría acceder a settings de forma segura:

async def get_brand_context(brand_name_original: str) -> Optional[str]:
    # Acceder a la instancia global 'settings'
    # Es crucial que 'settings' se haya inicializado correctamente antes de llamar a esta función.
    if not settings:
        _config_module_logger.error("get_brand_context: La instancia 'settings' global no está inicializada.")
        return None
    if not settings.BRANDS_DIR or not settings.BRANDS_DIR.is_dir(): # BRANDS_DIR ya es Path
        _config_module_logger.error(f"get_brand_context: Directorio BRANDS_DIR ('{settings.BRANDS_DIR}') no configurado o no existe.")
        return None

    try:
        # Asumimos que normalize_brand_name está disponible en algún lugar o se importa aquí
        from app.main.webhook_handler import normalize_brand_name 
    except ImportError:
        _config_module_logger.error("get_brand_context: No se pudo importar normalize_brand_name.")
        # Fallback simple si la importación falla (ajusta según tu lógica de normalización)
        normalize_brand_name = lambda name: name.lower().replace(" ", "_").replace(".", "")

    normalized_brand_for_filename = normalize_brand_name(brand_name_original)
    normalized_filepath = settings.BRANDS_DIR / f"{normalized_brand_for_filename}.txt"
    original_filepath = settings.BRANDS_DIR / f"{brand_name_original}.txt"

    file_to_read: Optional[Path] = None
    if normalized_filepath.is_file():
        file_to_read = normalized_filepath
    elif original_filepath.is_file():
        _config_module_logger.debug(f"Archivo de marca normalizado no encontrado, usando nombre original: {original_filepath.name}")
        file_to_read = original_filepath
    else:
        _config_module_logger.warning(f"Archivo de contexto de marca no encontrado para '{brand_name_original}'. Probados: '{normalized_filepath.name}', '{original_filepath.name}'.")
        return None

    try:
        async with open(file_to_read, mode='r', encoding='utf-8') as f: # aiofiles no es necesario para abrir un archivo síncronamente
            content = f.read() # Lectura síncrona
        content = content.strip()
        if not content:
            _config_module_logger.warning(f"Archivo de contexto de marca para '{brand_name_original}' ('{file_to_read.name}') está vacío.")
            return None
        _config_module_logger.debug(f"Contexto cargado para '{brand_name_original}' desde '{file_to_read.name}'.")
        return content
    except Exception as file_err:
        _config_module_logger.error(f"Error leyendo archivo de contexto de marca '{brand_name_original}' en '{file_to_read.name}': {file_err}", exc_info=True)
        return None