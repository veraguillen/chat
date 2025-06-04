#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para limpiar y estandarizar archivos de marcas.
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuración
BASE_DIR = Path(__file__).parent.parent
BRANDS_DIR = BASE_DIR / 'data' / 'brands'
BACKUP_DIR = BASE_DIR / 'data' / 'brands_backup'

# Crear directorio de respaldo con marca de tiempo
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP = BACKUP_DIR / f"backup_{timestamp}"

# Expresiones regulares para limpieza
MULTIPLE_SPACES = re.compile(r'\s+')
MULTIPLE_NEWLINES = re.compile(r'\n{3,}')
NON_ALPHANUM = re.compile(r'[^\w\sáéíóúÁÉÍÓÚñÑ.,;:!?¿¡()\-]')

def create_backup() -> None:
    """Crea una copia de seguridad de los archivos originales."""
    try:
        if not BRANDS_DIR.exists():
            print(f"Error: El directorio {BRANDS_DIR} no existe.")
            return False
            
        CURRENT_BACKUP.mkdir(parents=True, exist_ok=True)
        
        for file_path in BRANDS_DIR.glob('*'):
            if file_path.is_file():
                shutil.copy2(file_path, CURRENT_BACKUP / file_path.name)
        
        print(f"✓ Copia de seguridad creada en: {CURRENT_BACKUP}")
        return True
    except Exception as e:
        print(f"✗ Error al crear copia de seguridad: {str(e)}")
        return False

def clean_filename(filename: str) -> str:
    """Limpia y estandariza nombres de archivo."""
    # Quitar la extensión si existe
    name = filename
    if filename.lower().endswith('.txt'):
        name = filename[:-4]
    
    # Convertir a minúsculas
    clean = name.lower()
    
    # Reemplazar caracteres especiales
    clean = clean.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    clean = clean.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    
    # Reemplazar espacios y guiones por guiones bajos
    clean = clean.replace(' ', '_').replace('-', '_')
    
    # Eliminar caracteres no alfanuméricos excepto guión bajo y punto
    clean = re.sub(r'[^a-z0-9_.]', '', clean)
    
    # Eliminar múltiples guiones bajos
    clean = re.sub(r'_+', '_', clean)
    
    # Eliminar guiones bajos al final
    clean = clean.rstrip('_')
    
    # Mantener nombres limpios para archivos conocidos
    if 'ehecatl' in clean and 'clean' not in clean:
        clean = 'corporativo_ehecatl'
    
    # Añadir .txt
    clean += '.txt'
    
    return clean

def clean_file_content(content: str) -> str:
    """Limpia el contenido del archivo."""
    # Eliminar múltiples espacios
    content = MULTIPLE_SPACES.sub(' ', content)
    
    # Eliminar múltiples saltos de línea
    content = MULTIPLE_NEWLINES.sub('\n\n', content)
    
    # Eliminar caracteres no deseados
    content = NON_ALPHANUM.sub(' ', content)
    
    # Eliminar espacios al inicio/fin de cada línea
    lines = [line.strip() for line in content.splitlines()]
    
    # Unir líneas eliminando las vacías al inicio/fin
    content = '\n'.join(filter(None, lines))
    
    return content.strip()

def process_brand_files() -> None:
    """Procesa todos los archivos de marcas."""
    if not create_backup():
        print("No se pudo crear la copia de seguridad. Abortando...")
        return
    
    processed_files = {}
    duplicates = []
    
    # Primera pasada: identificar duplicados
    for file_path in BRANDS_DIR.glob('*.txt'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            # Limpiar contenido para comparación
            clean_content = clean_file_content(content)
            
            if clean_content in processed_files.values():
                # Es un duplicado
                original = [k for k, v in processed_files.items() if v == clean_content][0]
                duplicates.append((file_path.name, original))
            else:
                # Es un archivo único
                processed_files[file_path.name] = clean_content
                
        except Exception as e:
            print(f"✗ Error procesando {file_path.name}: {str(e)}")
    
    # Segunda pasada: renombrar y limpiar archivos únicos
    for filename, content in processed_files.items():
        try:
            # Generar nuevo nombre
            new_name = clean_filename(filename)
            new_path = BRANDS_DIR / new_name
            
            # Si es necesario renombrar
            if new_name != filename:
                old_path = BRANDS_DIR / filename
                print(f"→ Renombrando: {filename} -> {new_name}")
                old_path.rename(new_path)
            
            # Limpiar y guardar contenido
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"✓ Procesado: {new_name}")
            
        except Exception as e:
            print(f"✗ Error al procesar {filename}: {str(e)}")
    
    # Eliminar duplicados
    for dup, original in duplicates:
        try:
            dup_path = BRANDS_DIR / dup
            dup_path.unlink()
            print(f"✗ Eliminado duplicado: {dup} (original: {original})")
        except Exception as e:
            print(f"✗ Error al eliminar duplicado {dup}: {str(e)}")
    
    print("\n¡Proceso completado!")
    print(f"- Archivos procesados: {len(processed_files)}")
    print(f"- Archivos duplicados eliminados: {len(duplicates)}")
    print(f"- Copia de seguridad en: {CURRENT_BACKUP}")

if __name__ == "__main__":
    print("=== LIMPIEZA DE ARCHIVOS DE MARCAS ===\n")
    
    if not BRANDS_DIR.exists():
        print(f"Error: El directorio {BRANDS_DIR} no existe.")
    else:
        print(f"Directorio a procesar: {BRANDS_DIR}")
        print(f"Se creará una copia de seguridad en: {CURRENT_BACKUP}\n")
        
        confirm = input("¿Desea continuar? (s/n): ").strip().lower()
        if confirm == 's':
            process_brand_files()
        else:
            print("\nOperación cancelada por el usuario.")
