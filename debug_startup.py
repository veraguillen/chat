# debug_startup.py - Script para diagnosticar problemas de arranque
import os
import sys
import json
import logging
from pathlib import Path

# Configurar logging básico
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("startup_diagnosis")

# Punto de entrada para diagnóstico
def diagnose_startup():
    logger.info("=== INICIANDO DIAGNÓSTICO DE ARRANQUE ===")
    
    # 1. Verificar variables de entorno críticas
    critical_vars = [
        "WEBSITES_PORT", "PORT", "ENVIRONMENT", "DEBUG", "LOG_LEVEL",
        "DATABASE_URL", "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD",
        "STORAGE_ACCOUNT_NAME", "CONTAINER_NAME", "AZURE_STORAGE_CONNECTION_STRING",
        "FAISS_INDEX_NAME", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_ACCESS_TOKEN",
        "OPENROUTER_API_KEY", "HUGGINGFACE_TOKEN"
    ]
    
    env_report = {}
    for var in critical_vars:
        value = os.environ.get(var)
        # Ocultar valores sensibles, solo mostrar si están presentes
        if var in ["DATABASE_URL", "PGPASSWORD", "AZURE_STORAGE_CONNECTION_STRING", 
                  "WHATSAPP_ACCESS_TOKEN", "OPENROUTER_API_KEY", "HUGGINGFACE_TOKEN"]:
            env_report[var] = "[PRESENTE]" if value else "[AUSENTE]"
        else:
            env_report[var] = value if value else "[AUSENTE]"
    
    logger.info(f"Variables de entorno críticas: {json.dumps(env_report, indent=2)}")
    
    # 2. Verificar estructura de directorios
    try:
        base_dir = Path(__file__).resolve().parent
        dir_structure = {
            "base_dir": str(base_dir),
            "app_init_exists": (base_dir / "app" / "__init__.py").exists(),
            "app_main_exists": (base_dir / "app" / "main.py").exists(),
            "core_config_exists": (base_dir / "app" / "core" / "config.py").exists(),
            "dockerfile_exists": (base_dir / "Dockerfile").exists(),
        }
        logger.info(f"Estructura de directorios: {json.dumps(dir_structure, indent=2)}")
    except Exception as e:
        logger.error(f"Error verificando estructura de directorios: {e}")
    
    # 3. Intentar importar módulos críticos
    try:
        logger.info("Intentando importar app...")
        import app
        logger.info(f"✓ app importado correctamente. app.__name__: {app.__name__}")
        
        if hasattr(app, 'app') and app.app is not None:
            logger.info(f"✓ app.app existe y no es None. Tipo: {type(app.app).__name__}")
        else:
            logger.error(f"✗ app.app no existe o es None")
            
    except Exception as e:
        logger.error(f"✗ Error importando app: {e}", exc_info=True)
    
    # 4. Intentar importar configuración
    try:
        logger.info("Intentando importar app.core.config...")
        from app.core.config import settings
        logger.info(f"✓ settings importado correctamente.")
        
        # Verificar campos críticos
        critical_settings = [
            "DATABASE_URL", "ENVIRONMENT", "DEBUG", "STORAGE_ACCOUNT_NAME",
            "CONTAINER_NAME", "FAISS_INDEX_NAME", "OPENROUTER_API_KEY"
        ]
        
        settings_report = {}
        for field in critical_settings:
            value = getattr(settings, field, None)
            if field in ["DATABASE_URL", "OPENROUTER_API_KEY"]:
                settings_report[field] = "[PRESENTE]" if value else "[AUSENTE]"
            else:
                settings_report[field] = value
                
        logger.info(f"Valores críticos en settings: {json.dumps(settings_report, indent=2)}")
        
    except Exception as e:
        logger.error(f"✗ Error importando app.core.config: {e}", exc_info=True)
    
    logger.info("=== DIAGNÓSTICO DE ARRANQUE COMPLETADO ===")

if __name__ == "__main__":
    try:
        diagnose_startup()
    except Exception as e:
        logger.critical(f"Error fatal en diagnóstico: {e}", exc_info=True)
