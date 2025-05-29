import os
import logging
from pathlib import Path
from typing import Optional, List, Union, Any # Añadido Any para __init__
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator, HttpUrl
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- Cálculo de Rutas Base (antes de cualquier otra cosa) ---
try:
    # Asumimos que este archivo (config.py) está en app/core/config.py
    # Subimos tres niveles para llegar a la raíz del proyecto
    PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent 
except NameError: 
    # Fallback si __file__ no está definido (ej. en algunos contextos de ejecución interactiva)
    PROJECT_ROOT_DIR = Path(".").resolve() # Raíz del directorio de trabajo actual

ENV_FILE_PATH = PROJECT_ROOT_DIR / '.env'

# --- Carga Inicial de .env (principalmente para desarrollo local) ---
if ENV_FILE_PATH.is_file():
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    # No es necesario loguear aquí, Pydantic lo hará o podemos loguearlo después en Settings
else:
    # En producción (Azure), es normal que .env no exista, las variables vienen del entorno
    pass

# --- Configuración de Logging Básico para ESTE MÓDULO ---
# Este logger se usa ANTES de que la configuración completa de Settings esté disponible
# y antes de que el logger principal de la aplicación se configure.
_LOG_FORMAT_DEFAULT_CONFIG = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
_config_module_logger = logging.getLogger("app.core.config_loader_module") # Nombre único
if not _config_module_logger.hasHandlers(): # Evitar añadir handlers múltiples veces
    _stream_handler_config = logging.StreamHandler()
    _formatter_config = logging.Formatter(_LOG_FORMAT_DEFAULT_CONFIG, datefmt='%Y-%m-%d %H:%M:%S')
    _stream_handler_config.setFormatter(_formatter_config)
    _config_module_logger.addHandler(_stream_handler_config)
    _config_module_logger.setLevel(os.getenv("INIT_LOG_LEVEL", "INFO").upper()) # Nivel de log inicial

_config_module_logger.info(f"PROJECT_ROOT_DIR calculado como: {PROJECT_ROOT_DIR}")
_config_module_logger.info(f"Pydantic intentará cargar .env desde: '{ENV_FILE_PATH}' (si existe)")


class Settings(BaseSettings):
    PROJECT_NAME: str = "Chatbot_App_Default_Name"
    VERSION: str = "1.0.0"
    STARTUP_TIMESTAMP: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # --- Paths Base (calculados en el validador o __init__) ---
    BASE_DIR: Path # Se establecerá en el validador usando PROJECT_ROOT_DIR
    DATA_DIR: Path
    BRANDS_DIR: Path
    LOG_DIR: Path
    KNOWLEDGE_BASE_DIR: Path
    
    # --- Configuración de LLM ---
    LLM_TEMPERATURE: float = Field(default=0.5, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=1000, gt=0)

    # --- Configuración de Meta (WhatsApp, Messenger) ---
    whatsapp_phone_number_id: Optional[str] = Field(default=None, validation_alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_access_token: Optional[str] = Field(default=None, validation_alias="WHATSAPP_ACCESS_TOKEN")
    meta_api_version: str = Field(default="v19.0", validation_alias="META_API_VERSION")
    messenger_page_access_token: Optional[str] = Field(default=None, validation_alias="MESSENGER_PAGE_ACCESS_TOKEN")
    verify_token: Optional[str] = Field(default=None, validation_alias="VERIFY_TOKEN") # Para webhook verification

    # --- Configuración de OpenRouter ---
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL_CHAT: str = Field(default="mistralai/mistral-7b-instruct-v0.2")
    OPENROUTER_CHAT_ENDPOINT: HttpUrl = Field(default="https://openrouter.ai/api/v1")

    # --- Configuración de Cliente HTTP ---
    HTTP_CLIENT_TIMEOUT: float = Field(default=30.0, gt=0)

    # --- Configuración de Base de Datos PostgreSQL ---
    pguser: Optional[str] = Field(default=None, validation_alias="PGUSER")
    pgpassword: Optional[str] = Field(default=None, validation_alias="PGPASSWORD")
    pghost: Optional[str] = Field(default=None, validation_alias="PGHOST")
    pgdatabase: Optional[str] = Field(default=None, validation_alias="PGDATABASE")
    pgport: int = Field(default=5432, validation_alias="PGPORT") # Añadido pgport para la URL
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL") # Puede ser provista directamente

    # --- Configuración de Logging de la Aplicación ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default=_LOG_FORMAT_DEFAULT_CONFIG, validation_alias="LOG_FORMAT") # Usar el mismo formato
    log_file: Path # Se calculará en el validador
    log_max_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0, validation_alias="LOG_MAX_SIZE_BYTES")
    log_backup_count: int = Field(default=5, ge=0, validation_alias="LOG_BACKUP_COUNT")

    # --- Configuración de Azure Storage ---
    storage_account_name: Optional[str] = Field(default=None, validation_alias="STORAGE_ACCOUNT_NAME")
    container_name: Optional[str] = Field(default=None, validation_alias="CONTAINER_NAME")

    # --- Configuración RAG ---
    embedding_model_name: str = Field(default='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', validation_alias="EMBEDDING_MODEL_NAME")
    faiss_index_name: str = Field(default="index", validation_alias="FAISS_INDEX_NAME") # Nombre base de los archivos .faiss y .pkl
    faiss_folder_name: str = Field(default="faiss_index_kb_spanish_v1", validation_alias="FAISS_FOLDER_NAME") # Subcarpeta dentro de DATA_DIR
    faiss_folder_path: Path # Se calculará en el validador
    vector_db_type: str = Field(default="FAISS", validation_alias="VECTOR_DB_TYPE")
    rag_default_k: int = Field(default=3, ge=1, le=10, validation_alias="RAG_DEFAULT_K")
    rag_k_fetch_multiplier: int = Field(default=2, validation_alias="RAG_K_FETCH_MULTIPLIER")
    
    # --- Configuración de Calendly ---
    calendly_api_key: Optional[str] = Field(default=None, validation_alias="CALENDLY_API_KEY")
    calendly_event_type_uri: Optional[HttpUrl] = Field(default=None, validation_alias="CALENDLY_EVENT_TYPE_URI")
    calendly_timezone: str = Field(default="America/Mexico_City", validation_alias="CALENDLY_TIMEZONE")
    calendly_user_slug: Optional[str] = Field(default=None, validation_alias="CALENDLY_USER_SLUG")
    calendly_days_to_check: int = Field(default=7, gt=0, le=60, validation_alias="CALENDLY_DAYS_TO_CHECK")

    # --- Configuración del Servidor Uvicorn/Gunicorn ---
    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST") # Para Uvicorn si se usa run.py
    server_port: int = Field(default=8000, gt=1023, lt=65536, validation_alias="SERVER_PORT") # Para Uvicorn si se usa run.py

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None, # Solo carga si existe
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False # Variables de entorno no son case-sensitive
    )

    @model_validator(mode='after')
    def _process_and_validate_settings(self) -> 'Settings':
        _config_module_logger.info("Ejecutando _process_and_validate_settings Pydantic model_validator...")
        
        # Establecer BASE_DIR usando la variable global calculada al inicio del módulo
        self.BASE_DIR = PROJECT_ROOT_DIR
        _config_module_logger.info(f"  BASE_DIR establecido a: {self.BASE_DIR}")

        # Calcular y crear LOG_DIR y self.log_file
        self.LOG_DIR = self.BASE_DIR / "logs"
        self.log_file = self.LOG_DIR / f"chatbot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_utc')}.log"
        _config_module_logger.info(f"  LOG_DIR calculado: {self.LOG_DIR}")
        _config_module_logger.info(f"  log_file calculado: {self.log_file}")
        
        # Calcular otros directorios basados en BASE_DIR y DATA_DIR
        self.DATA_DIR = self.BASE_DIR / "data"
        self.BRANDS_DIR = self.DATA_DIR / "brands"
        self.KNOWLEDGE_BASE_DIR = self.BASE_DIR / "knowledge_base" # Si usas esta carpeta separada
        
        # Calcular el path completo a la carpeta del índice FAISS
        if self.faiss_folder_name: # faiss_folder_name es el nombre de la subcarpeta dentro de DATA_DIR
            self.faiss_folder_path = self.DATA_DIR / self.faiss_folder_name
            _config_module_logger.info(f"  faiss_folder_path calculado: {self.faiss_folder_path}")
        else:
            _config_module_logger.error("  faiss_folder_name no está definido, faiss_folder_path no se puede calcular.")
            # Considera lanzar un error aquí si es crítico
            # raise ValueError("faiss_folder_name debe estar definido en la configuración.")
            self.faiss_folder_path = self.DATA_DIR / "default_faiss_index" # Fallback o error

        # Crear directorios necesarios
        dirs_to_create: List[Path] = [self.LOG_DIR, self.DATA_DIR, self.BRANDS_DIR, self.KNOWLEDGE_BASE_DIR]
        if hasattr(self, 'faiss_folder_path') and self.faiss_folder_path: # Asegurarse que faiss_folder_path exista
            dirs_to_create.append(self.faiss_folder_path)

        for dir_path in dirs_to_create:
            if dir_path: # Asegurarse que el path no sea None
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    _config_module_logger.info(f"  Directorio asegurado/creado: {dir_path}")
                except Exception as e_mkdir:
                    _config_module_logger.error(f"  No se pudo crear directorio {dir_path}: {e_mkdir}")
        
        # Validar y normalizar LOG_LEVEL
        self.log_level = self.log_level.upper()
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            _config_module_logger.warning(f"  LOG_LEVEL '{self.log_level}' inválido. Usando INFO por defecto.")
            self.log_level = "INFO"
            
        # Construir DATABASE_URL si no se proveyó explícitamente y los componentes están disponibles
        if not self.database_url and all([self.pguser, self.pgpassword, self.pghost, self.pgdatabase, self.pgport]):
            self.database_url = f"postgresql+asyncpg://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}?ssl=require"
            _config_module_logger.info(f"  DATABASE_URL construida internamente: postgresql+asyncpg://{self.pguser}:***@{self.pghost}:{self.pgport}/{self.pgdatabase}?ssl=require")
        elif self.database_url:
            # Validaciones opcionales para una DATABASE_URL provista
            if "asyncpg" not in self.database_url:
                 _config_module_logger.warning(f"  DATABASE_URL provista puede no ser para 'asyncpg'.")
            if "?ssl=require" not in self.database_url and "localhost" not in self.database_url and "127.0.0.1" not in self.database_url :
                 _config_module_logger.warning(f"  DATABASE_URL provista no especifica '?ssl=require' y no parece ser local.")
        else:
            _config_module_logger.critical("  DATABASE_URL no se proveyó ni se pudo construir. La conexión a la base de datos fallará.")
            
        _config_module_logger.info("Finalizada validación y procesamiento de settings en _process_and_validate_settings.")
        return self

# --- Singleton para la instancia de Settings ---
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _config_module_logger.debug("get_settings(): Creando nueva instancia de Settings...")
        try:
            _settings_instance = Settings()
            _config_module_logger.info("Instancia de Settings creada y validada exitosamente por Pydantic.")
            # Loguear un resumen de la configuración esencial (cuidado con datos sensibles en producción)
            # _log_essential_settings_info(_settings_instance) # Descomentar para depuración detallada
        except Exception as e_load:
            _config_module_logger.critical(f"ERROR FATAL creando instancia de Settings en get_settings(): {e_load}", exc_info=True)
            if hasattr(e_load, 'errors'): # Específico para pydantic.ValidationError
                _config_module_logger.critical(f"Detalles de validación de Pydantic: {e_load.errors()}")
            raise RuntimeError(f"La carga de configuración de la aplicación falló críticamente: {e_load}")
    return _settings_instance

# Función de ayuda para loguear un resumen (opcional, para depuración)
def _log_essential_settings_info(s: Settings):
    _config_module_logger.info("--- Resumen de Configuración Cargada (get_settings) ---")
    _config_module_logger.info(f"  PROJECT_NAME: {s.PROJECT_NAME}, VERSION: {s.VERSION}")
    _config_module_logger.info(f"  LOG_LEVEL (app): {s.log_level}, LOG_FILE (app): {s.log_file}")
    _config_module_logger.info(f"  Calculated FAISS Folder Path: {s.faiss_folder_path}")
    
    db_url_display = 'AUSENTE O NO CONSTRUIDA'
    if s.database_url:
        parts = s.database_url.split('@')
        db_url_display = f"...@{parts[-1]}" if len(parts) > 1 else "Formato no estándar o incompleta"
    _config_module_logger.info(f"  DATABASE_URL (final para conexión): {db_url_display}")

    # Lista de variables consideradas críticas para el funcionamiento
    critical_vars_check = {
        "DATABASE_URL": s.database_url, # Verificar la URL final
        "WHATSAPP_ACCESS_TOKEN": s.whatsapp_access_token,
        "WHATSAPP_PHONE_NUMBER_ID": s.whatsapp_phone_number_id,
        "VERIFY_TOKEN": s.verify_token,
        # "OPENROUTER_API_KEY": s.OPENROUTER_API_KEY, # Depende si es crítico para el arranque
        # "CALENDLY_API_KEY": s.calendly_api_key, # Depende si es crítico
    }
    if hasattr(s, 'faiss_folder_path') and not s.faiss_folder_path.is_dir():
         _config_module_logger.critical(f"  ¡¡RUTA FAISS CRÍTICA NO ES UN DIRECTORIO!!: {s.faiss_folder_path}")
    
    missing_critical = [k_env for k_env, attr_val in critical_vars_check.items() if not attr_val]
    if missing_critical:
        _config_module_logger.critical(f"  ¡¡VARIABLES CRÍTICAS FALTANTES!!: {', '.join(missing_critical)}")
    else:
        _config_module_logger.info("  Verificación básica de variables críticas: OK.")
    _config_module_logger.info("---------------------------------------------------")

# --- Instancia Global de Settings ---
# Se crea una vez cuando este módulo es importado por primera vez.
# Si falla aquí, la aplicación no debería arrancar.
try:
    settings = get_settings()
except RuntimeError as e_init_module_level:
    _config_module_logger.critical(f"FALLO CRÍTICO AL INICIALIZAR 'settings' a nivel de módulo en config.py: {e_init_module_level}")
    # En un escenario real, podrías querer que la app falle completamente aquí.
    # Para permitir que otros módulos importen 'settings' aunque sea None:
    settings = None 