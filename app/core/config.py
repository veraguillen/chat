# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from typing import Optional

# BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "ChatbotMultimarca"

    # WhatsApp
    whatsapp_phone_number_id: Optional[str] = Field(default=None, alias="PHONE_NUMBER_ID")
    whatsapp_access_token: Optional[str] = Field(default=None, alias="ACCESS_TOKEN")
    whatsapp_recipient_waid: Optional[str] = Field(default=None, alias="RECIPIENT_WAID")

    # Messenger
    messenger_page_access_token: Optional[str] = Field(default=None, alias="PAGE_ACCESS_TOKEN")
    messenger_app_id: Optional[str] = Field(default=None, alias="APP_ID")
    messenger_app_secret: Optional[str] = Field(default=None, alias="APP_SECRET")

    # DeepSeek
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")

    # --- CAMBIO AQUÍ ---
    # Webhook - Mantener el nombre de atributo 'verify_token'
    # El alias "VERIFY_TOKEN" le dice que lea esa variable del .env
    verify_token: Optional[str] = Field(default=None, alias="VERIFY_TOKEN")
    # -------------------

    # Database
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    database_name: str = Field(default="chatbot_db", alias="DATABASE_NAME")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Ruta Base de Conocimiento
    KNOWLEDGE_BASE_PATH: str = "knowledge_base"

    class Config:
        env_file = '.env'
        env_file_encoding = "utf-8"
        extra = "ignore"

# Crear la instancia
try:
    settings = Settings()
    # Verificar claves esenciales (ahora usa los nombres de atributo de esta clase)
    essential_keys = ['whatsapp_access_token', 'whatsapp_phone_number_id', 'deepseek_api_key', 'database_url', 'verify_token']
    missing_keys = [k for k in essential_keys if getattr(settings, k, None) is None]
    if missing_keys:
         print(f"ADVERTENCIA: Faltan configuraciones esenciales en .env o no se pudieron cargar: {', '.join(missing_keys)}")

except Exception as e:
    print(f"ERROR FATAL: No se pudo cargar/validar la configuración desde .env: {e}")
    settings = None
