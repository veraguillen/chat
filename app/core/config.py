from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from pathlib import Path
from typing import Optional, Any, Dict
import os
import logging
import aiofiles
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- Initial .env Load ---
_ENV_FILE_PATH_TO_CHECK_FOR_DOTENV = Path(__file__).resolve().parent.parent.parent / '.env'
if _ENV_FILE_PATH_TO_CHECK_FOR_DOTENV.is_file():
    load_dotenv(dotenv_path=_ENV_FILE_PATH_TO_CHECK_FOR_DOTENV, override=True)

# --- Logging Setup ---
_LOG_FORMAT_TEMP = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT_TEMP,
    datefmt='%Y-%m-%d %H:%M:%S'
)
_temp_logger = logging.getLogger("app.core.config_loader")

# --- Base Path Calculations ---
try:
    CORE_DIR = Path(__file__).resolve().parent
    APP_DIR = CORE_DIR.parent
    BASE_DIR = APP_DIR.parent
    DATA_DIR = BASE_DIR / "data"
    BRANDS_DIR = DATA_DIR / "brands"
    LOG_DIR = BASE_DIR / "logs"
    KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
    _temp_logger.info(f"Rutas base calculadas: BASE_DIR={BASE_DIR}, KNOWLEDGE_BASE_DIR={KNOWLEDGE_BASE_DIR}")
except Exception as e:
    _temp_logger.error(f"Error crítico calculando rutas base: {e}. Usando fallbacks relativos.", exc_info=True)
    BASE_DIR = Path(".").resolve()
    DATA_DIR = BASE_DIR / "data"
    BRANDS_DIR = DATA_DIR / "brands"
    LOG_DIR = BASE_DIR / "logs"
    KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

_ENV_FILE_PATH_TO_CHECK = BASE_DIR / '.env'

# --- .env Debug ---
_temp_logger.info(f"Pydantic intentará usar el archivo .env desde: '{_ENV_FILE_PATH_TO_CHECK}' (según model_config)")
if _ENV_FILE_PATH_TO_CHECK.is_file():
    _temp_logger.info(f"El archivo .env '{_ENV_FILE_PATH_TO_CHECK}' EXISTE (verificado por Pydantic).")
    try:
        with open(_ENV_FILE_PATH_TO_CHECK, 'r', encoding='utf-8') as f_env_debug:
            env_content_sample = f_env_debug.read(1000)
    except Exception as e_read_env:
        _temp_logger.error(f"Error al intentar leer el archivo .env para depuración: {e_read_env}")
else:
    _temp_logger.warning(f"El archivo .env '{_ENV_FILE_PATH_TO_CHECK}' NO EXISTE (según Pydantic).")

class Settings(BaseSettings):
    PROJECT_NAME: str = "ChatbotMultimarca_Citas_RAG_v2.3_OpenRouter"
    VERSION: str = "2.3.0"
    STARTUP_TIMESTAMP: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    BASE_DIR: Path = Field(default=BASE_DIR)
    DATA_DIR: Path = Field(default=DATA_DIR)
    BRANDS_DIR: Path = Field(default=BRANDS_DIR)
    LOG_DIR: Path = Field(default=LOG_DIR)
    KNOWLEDGE_BASE_DIR: Optional[Path] = Field(default=KNOWLEDGE_BASE_DIR)

    LLM_TEMPERATURE: float = Field(default=0.5, ge=0.0, le=2.0, validation_alias="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=1000, gt=0, validation_alias="LLM_MAX_TOKENS")

    whatsapp_phone_number_id: Optional[str] = Field(default=None, validation_alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_access_token: Optional[str] = Field(default=None, validation_alias="WHATSAPP_ACCESS_TOKEN")
    meta_api_version: str = Field(default="v19.0", validation_alias="META_API_VERSION")
    messenger_page_access_token: Optional[str] = Field(default=None, validation_alias="MESSENGER_PAGE_ACCESS_TOKEN")
    webhook_verify_token: Optional[str] = Field(default=None, validation_alias="VERIFY_TOKEN")

    OPENROUTER_API_KEY: Optional[str] = Field(default=None)
    OPENROUTER_MODEL_CHAT: str = Field(default="mistralai/mistral-7b-instruct-v0.2")
    OPENROUTER_CHAT_ENDPOINT: str = Field(default="https://openrouter.ai/api/v1")

    http_client_timeout: float = Field(default=30.0, gt=0, validation_alias="HTTP_CLIENT_TIMEOUT")
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default=_LOG_FORMAT_TEMP, validation_alias="LOG_FORMAT")
    log_file: Optional[Path] = None
    log_max_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0, validation_alias="LOG_MAX_SIZE_BYTES")
    log_backup_count: int = Field(default=5, ge=0, validation_alias="LOG_BACKUP_COUNT")

    embedding_model_name: str = Field(
        default='sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
        validation_alias="EMBEDDING_MODEL_NAME"
    )
    faiss_index_name: str = Field(default="index", validation_alias="FAISS_INDEX_NAME")
    faiss_folder_name: str = Field(default="faiss_index_multilingual_v1", validation_alias="FAISS_FOLDER_NAME")
    faiss_folder_path: Optional[Path] = None
    vector_db_type: str = Field(default="FAISS", validation_alias="VECTOR_DB_TYPE")
    rag_default_k: int = Field(default=3, ge=1, le=10, validation_alias="RAG_DEFAULT_K")
    rag_chunk_size: int = Field(default=1000, gt=0, validation_alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=150, ge=0, validation_alias="RAG_CHUNK_OVERLAP")

    calendly_api_key: Optional[str] = Field(default=None, validation_alias="CALENDLY_API_KEY")
    calendly_event_type_uri: Optional[str] = Field(default=None, validation_alias="CALENDLY_EVENT_TYPE_URI")
    calendly_timezone: str = Field(default="America/Mexico_City", validation_alias="CALENDLY_TIMEZONE")
    calendly_user_slug: Optional[str] = Field(default=None, validation_alias="CALENDLY_USER_SLUG")
    calendly_days_to_check: int = Field(default=7, gt=0, le=60, validation_alias="CALENDLY_DAYS_TO_CHECK")

    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    server_port: int = Field(default=8000, gt=1023, lt=65536, validation_alias="SERVER_PORT")

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH_TO_CHECK,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode='after')
    def _calculate_and_create_paths(self) -> 'Settings':
        if not self.BASE_DIR.is_absolute():
            try:
                core_dir_val = Path(__file__).resolve().parent
                app_dir_val = core_dir_val.parent
                self.BASE_DIR = app_dir_val.parent
            except Exception:
                self.BASE_DIR = Path(".").resolve()

        if not self.LOG_DIR or not self.LOG_DIR.is_absolute():
            self.LOG_DIR = self.BASE_DIR / "logs"
        self.log_file = self.LOG_DIR / f"chatbot_{datetime.now().strftime('%Y%m%d')}.log"

        if not self.DATA_DIR or not self.DATA_DIR.is_absolute():
            self.DATA_DIR = self.BASE_DIR / "data"

        if self.faiss_folder_name:
            self.faiss_folder_path = self.DATA_DIR / self.faiss_folder_name

        if not self.BRANDS_DIR or not self.BRANDS_DIR.is_absolute():
            self.BRANDS_DIR = self.DATA_DIR / "brands"

        if self.KNOWLEDGE_BASE_DIR and not self.KNOWLEDGE_BASE_DIR.is_absolute():
            self.KNOWLEDGE_BASE_DIR = self.BASE_DIR / "knowledge_base"
        elif not self.KNOWLEDGE_BASE_DIR:
            self.KNOWLEDGE_BASE_DIR = self.BASE_DIR / "knowledge_base"

        dirs_to_create = [self.LOG_DIR, self.DATA_DIR, self.BRANDS_DIR]
        if self.KNOWLEDGE_BASE_DIR:
            dirs_to_create.append(self.KNOWLEDGE_BASE_DIR)
        if self.faiss_folder_path:
            dirs_to_create.append(self.faiss_folder_path)

        for dir_path in dirs_to_create:
            if dir_path and isinstance(dir_path, Path):
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e_mkdir:
                    _temp_logger.error(f"No se pudo crear directorio {dir_path}: {e_mkdir}")
            elif dir_path:
                _temp_logger.warning(f"Path esperado para dir, se obtuvo: {dir_path} (tipo: {type(dir_path)})")
        return self

_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        try:
            _temp_logger.debug("Primera llamada a get_settings(), inicializando Settings...")
            current_settings = Settings()
            _settings_instance = current_settings
            _temp_logger.info("Instancia de Settings creada y validada.")
            _log_essential_settings_info(_settings_instance)
        except Exception as e_load:
            _temp_logger.critical(f"ERROR FATAL en get_settings(): {e_load}", exc_info=True)
            if hasattr(e_load, 'errors'):
                _temp_logger.critical(f"Detalles de validación: {e_load.errors()}")
            raise RuntimeError(f"Configuración falló al cargar: {e_load}")
    return _settings_instance

def _log_essential_settings_info(s: Settings):
    _temp_logger.info("--- Configuración Esencial Cargada ---")
    _temp_logger.info(f"  PROJECT_NAME: {s.PROJECT_NAME}, VERSION: {s.VERSION}")
    _temp_logger.info(f"  LOG_LEVEL: {s.log_level}, LOG_FILE: {s.log_file}")
    _temp_logger.info(f"  LLM_TEMPERATURE: {s.LLM_TEMPERATURE}")
    _temp_logger.info(f"  LLM_MAX_TOKENS: {s.LLM_MAX_TOKENS}")
    _temp_logger.info(f"  EMBEDDING_MODEL: {s.embedding_model_name}")
    _temp_logger.info(f"  FAISS_INDEX_PATH: {s.faiss_folder_path}")
    _temp_logger.info(f"  OPENROUTER_MODEL: {s.OPENROUTER_MODEL_CHAT}")
    _temp_logger.info(f"  OPENROUTER_API_KEY: {'Presente' if s.OPENROUTER_API_KEY else 'AUSENTE'}")
    _temp_logger.info(f"  CALENDLY_EVENT_URI: {s.calendly_event_type_uri if s.calendly_event_type_uri else 'AUSENTE'}")
    _temp_logger.info(f"  CALENDLY_API_KEY: {'Presente' if s.calendly_api_key else 'AUSENTE'}")
    
    missing = [k for k, v in {
        "OPENROUTER_API_KEY": s.OPENROUTER_API_KEY,
        "WHATSAPP_ACCESS_TOKEN": s.whatsapp_access_token,
        "WHATSAPP_PHONE_NUMBER_ID": s.whatsapp_phone_number_id,
        "WEBHOOK_VERIFY_TOKEN": s.webhook_verify_token,
        "CALENDLY_API_KEY": s.calendly_api_key,
        "CALENDLY_EVENT_TYPE_URI": s.calendly_event_type_uri,
        "DATABASE_URL": s.database_url
    }.items() if not v]
    
    if missing:
        _temp_logger.warning(f"ADVERTENCIA: Faltan configuraciones opcionales/requeridas: {', '.join(missing)}")
    else:
        _temp_logger.info("  Todas las configuraciones esenciales verificadas parecen estar presentes.")
    _temp_logger.info("-------------------------------------")

async def get_brand_context(brand_name_original: str) -> Optional[str]:
    from app.main.webhook_handler import normalize_brand_name
    s = get_settings()
    if not s.BRANDS_DIR or not s.BRANDS_DIR.is_dir():
        _temp_logger.error(f"Directorio BRANDS_DIR ('{s.BRANDS_DIR}') no configurado o no existe.")
        return None

    normalized_brand_for_filename = normalize_brand_name(brand_name_original)
    normalized_filepath = s.BRANDS_DIR / f"{normalized_brand_for_filename}.txt"
    original_filepath = s.BRANDS_DIR / f"{brand_name_original}.txt"

    file_to_read = None
    if normalized_filepath.is_file():
        file_to_read = normalized_filepath
    elif original_filepath.is_file():
        _temp_logger.debug(f"Archivo normalizado no encontrado, usando nombre original: {original_filepath.name}")
        file_to_read = original_filepath
    else:
        _temp_logger.warning(f"Archivo contexto no encontrado para '{brand_name_original}'. Probados: '{normalized_filepath.name}', '{original_filepath.name}'.")
        return None

    try:
        async with aiofiles.open(file_to_read, mode='r', encoding='utf-8') as f:
            content = await f.read()
        content = content.strip()
        if not content:
            _temp_logger.warning(f"Archivo contexto para '{brand_name_original}' ('{file_to_read.name}') vacío.")
            return None
        _temp_logger.debug(f"Contexto cargado para '{brand_name_original}' desde '{file_to_read.name}'.")
        return content
    except Exception as file_err:
        _temp_logger.error(f"Error leyendo archivo contexto '{brand_name_original}' en '{file_to_read.name}': {file_err}", exc_info=True)
        return None

try:
    settings = get_settings()
except RuntimeError as e_init:
    _temp_logger.critical(f"FALLO CRÍTICO AL INICIALIZAR 'settings' en config.py (nivel de módulo): {e_init}")
    settings = None