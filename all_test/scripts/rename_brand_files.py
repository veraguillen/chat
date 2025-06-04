#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para renombrar archivos de marcas a un formato limpio.
"""

import os
import re
from pathlib import Path

# Configuración
BASE_DIR = Path(__file__).parent.parent
BRANDS_DIR = BASE_DIR / 'data' / 'brands'

def get_clean_name(filename: str) -> str:
    """Obtiene un nombre limpio para el archivo."""
    # Mapeo de nombres especiales
    name_mapping = {
        'ehecatl': 'corporativo_ehecatl',
        'fundacion': 'fundacion_desarrollemos_mexico',
        'javier': 'consultor_javier_bazan',
        'estudiantil': 'frente_estudiantil_social',
        'universidad': 'universidad_desarrollo_digital'
    }
    
    # Buscar coincidencias con nombres especiales
    for key, clean_name in name_mapping.items():
        if key in filename.lower():
            return clean_name + '.txt'
    
    # Para otros archivos, usar el nombre base
    name = re.sub(r'\.txt$', '', filename, flags=re.IGNORECASE)
    name = re.sub(r'[^a-z0-9]', '_', name.lower())
    name = re.sub(r'_+', '_', name).strip('_')
    return name + '.txt'

def rename_brand_files():
    """Renombra los archivos de marcas a un formato limpio."""
    if not BRANDS_DIR.exists():
        print(f"Error: El directorio {BRANDS_DIR} no existe.")
        return
    
    print("=== RENOMBRANDO ARCHIVOS DE MARCAS ===\n")
    print(f"Directorio: {BRANDS_DIR}\n")
    
    # Primero mostramos los cambios propuestos
    files = list(BRANDS_DIR.glob('*.txt'))
    if not files:
        print("No se encontraron archivos .txt en el directorio.")
        return
    
    print("Cambios propuestos:")
    print("-" * 60)
    
    changes = []
    for file_path in files:
        old_name = file_path.name
        new_name = get_clean_name(old_name)
        if old_name != new_name:
            changes.append((old_name, new_name))
            print(f"{old_name} -> {new_name}")
    
    if not changes:
        print("\nNo se requieren cambios. Los archivos ya están con nombres limpios.")
        return
    
    # Pedir confirmación
    confirm = input("\n¿Desea aplicar estos cambios? (s/n): ").strip().lower()
    if confirm != 's':
        print("\nOperación cancelada por el usuario.")
        return
    
    # Aplicar cambios
    print("\nAplicando cambios...")
    for old_name, new_name in changes:
        try:
            old_path = BRANDS_DIR / old_name
            new_path = BRANDS_DIR / new_name
            
            # Si el archivo de destino ya existe, agregar un número
            counter = 1
            while new_path.exists() and new_path != old_path:
                base_name = new_name[:-4]  # Quitar .txt
                new_name = f"{base_name}_{counter}.txt"
                new_path = BRANDS_DIR / new_name
                counter += 1
            
            if old_path != new_path:
                old_path.rename(new_path)
                print(f"✓ Renombrado: {old_name} -> {new_name}")
        except Exception as e:
            print(f"✗ Error al renombrar {old_name}: {str(e)}")
    
    print("\n¡Proceso completado!")

if __name__ == "__main__":
    rename_brand_files()
