#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar la calidad de los datos antes de crear el índice FAISS.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_quality_check.log')
    ]
)
logger = logging.getLogger(__name__)

# Constantes
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
BRANDS_DIR = DATA_DIR / 'brands'
KNOWLEDGE_DIR = DATA_DIR / 'knowledge'

# Configuración de chunks
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 2000

def normalize_brand_name(name: str) -> str:
    """Normaliza el nombre de una marca para consistencia."""
    if not name:
        return ""
    
    # Convertir a minúsculas y normalizar espacios
    normalized = name.lower().strip()
    
    # Reemplazar caracteres especiales
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u', ' ': '_', '.': '_', '-': '_'
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Eliminar caracteres no alfanuméricos
    normalized = re.sub(r'[^a-z0-9_]', '', normalized)
    
    # Eliminar múltiples guiones bajos
    normalized = re.sub(r'_+', '_', normalized)
    
    # Eliminar guiones al inicio/final
    normalized = normalized.strip('_')
    
    return normalized

def check_file_quality(file_path: Path) -> Dict:
    """Verifica la calidad de un archivo individual."""
    try:
        # Leer contenido
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding='latin-1')
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Error de codificación: {str(e)}',
                    'size': file_path.stat().st_size
                }
        
        # Verificar tamaño
        size = len(content)
        if size == 0:
            return {'valid': False, 'error': 'Archivo vacío', 'size': 0}
        
        # Contar líneas y palabras
        lines = content.splitlines()
        word_count = sum(len(line.split()) for line in lines if line.strip())
        
        # Verificar formato
        has_multiple_newlines = '\n\n\n' in content
        has_tabs = '\t' in content
        
        return {
            'valid': True,
            'size': size,
            'lines': len(lines),
            'word_count': word_count,
            'has_multiple_newlines': has_multiple_newlines,
            'has_tabs': has_tabs
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'size': file_path.stat().st_size if file_path.exists() else 0
        }

def check_chunk_quality(text: str) -> Dict:
    """Verifica la calidad de un chunk de texto."""
    size = len(text)
    
    # Verificar tamaño
    if size < MIN_CHUNK_SIZE:
        return {'valid': False, 'issue': f'Chunk demasiado pequeño ({size} caracteres)'}
    
    if size > MAX_CHUNK_SIZE:
        return {'valid': False, 'issue': f'Chunk demasiado grande ({size} caracteres)'}
    
    # Verificar estructura
    sentences = re.split(r'[.!?]', text)
    if len(sentences) > 0 and len(sentences[-1]) > 100:
        return {'valid': False, 'issue': 'Posible oración cortada al final'}
    
    return {'valid': True}

def analyze_files(directory: Path) -> Tuple[Dict, Dict]:
    """Analiza todos los archivos en un directorio."""
    if not directory.exists():
        logger.warning(f"El directorio no existe: {directory}")
        return {}, {}
    
    file_stats = {}
    brand_stats = defaultdict(list)
    
    # Buscar archivos .txt y .md
    for ext in ('*.txt', '*.md'):
        for file_path in directory.glob(f'**/{ext}'):
            # Obtener información básica
            rel_path = file_path.relative_to(directory)
            brand_name = file_path.stem
            
            # Verificar calidad del archivo
            file_quality = check_file_quality(file_path)
            
            # Si el archivo es válido, verificar chunks
            chunk_issues = []
            if file_quality['valid']:
                # Simular división en chunks
                content = file_path.read_text(encoding='utf-8')
                words = content.split()
                
                # Crear chunks simulados
                for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
                    chunk = ' '.join(words[i:i + CHUNK_SIZE])
                    chunk_quality = check_chunk_quality(chunk)
                    if not chunk_quality['valid']:
                        chunk_issues.append(f"Chunk {i//CHUNK_SIZE + 1}: {chunk_quality['issue']}")
            
            # Guardar estadísticas
            file_stats[str(rel_path)] = {
                'brand': brand_name,
                'normalized_brand': normalize_brand_name(brand_name),
                'valid': file_quality['valid'],
                'error': file_quality.get('error'),
                'size': file_quality.get('size', 0),
                'lines': file_quality.get('lines', 0),
                'word_count': file_quality.get('word_count', 0),
                'chunk_issues': chunk_issues
            }
            
            # Estadísticas por marca
            if file_quality['valid']:
                brand_stats[normalize_brand_name(brand_name)].append({
                    'file': str(rel_path),
                    'word_count': file_quality.get('word_count', 0),
                    'chunk_issues': len(chunk_issues)
                })
    
    return file_stats, dict(brand_stats)

def generate_report(file_stats: Dict, brand_stats: Dict) -> None:
    """Genera un informe de verificación."""
    # Estadísticas generales
    total_files = len(file_stats)
    valid_files = sum(1 for s in file_stats.values() if s['valid'])
    invalid_files = total_files - valid_files
    
    print("\n" + "="*80)
    print("INFORME DE CALIDAD DE DATOS")
    print("="*80)
    
    print(f"\n📊 ESTADÍSTICAS GENERALES")
    print(f"• Archivos analizados: {total_files}")
    print(f"• Archivos válidos: {valid_files} ({valid_files/max(total_files,1)*100:.1f}%)")
    print(f"• Archivos con problemas: {invalid_files} ({invalid_files/max(total_files,1)*100:.1f}%)")
    
    # Problemas comunes
    if invalid_files > 0:
        print("\n🚫 PROBLEMAS DETECTADOS")
        errors = defaultdict(int)
        for stats in file_stats.values():
            if not stats['valid']:
                errors[stats['error']] += 1
        
        for error, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            print(f"• {error}: {count} archivos")
    
    # Estadísticas por marca
    if brand_stats:
        print("\n🏷️  ESTADÍSTICAS POR MARCA")
        print("-"*50)
        
        for brand, files in sorted(brand_stats.items(), key=lambda x: len(x[1]), reverse=True):
            total_words = sum(f['word_count'] for f in files)
            total_issues = sum(f['chunk_issues'] for f in files)
            
            print(f"\n🔹 {brand.upper()}")
            print(f"   • Archivos: {len(files)}")
            print(f"   • Palabras totales: {total_words:,}")
            print(f"   • Problemas de chunks: {total_issues}")
    
    # Recomendaciones
    print("\n💡 RECOMENDACIONES")
    if invalid_files > 0:
        print("• Corrige los archivos con errores antes de continuar")
    else:
        print("• ¡Todos los archivos son válidos! Puedes proceder a crear el índice.")
    
    print("• Verifica los problemas de chunks en archivos grandes")
    print("• Considera dividir archivos muy grandes en documentos más pequeños\n")

def main():
    """Función principal."""
    print("🔍 INICIANDO VERIFICACIÓN DE CALIDAD DE DATOS\n")
    
    # Verificar directorios
    for dir_path in [BRANDS_DIR, KNOWLEDGE_DIR]:
        if not dir_path.exists():
            print(f"⚠️  Advertencia: El directorio no existe: {dir_path}")
    
    # Analizar archivos
    print("\nAnalizando archivos de marcas...")
    brand_files, brand_stats = analyze_files(BRANDS_DIR)
    
    print("\nAnalizando archivos de conocimiento general...")
    knowledge_files, knowledge_stats = analyze_files(KNOWLEDGE_DIR)
    
    # Combinar resultados
    all_files = {**brand_files, **knowledge_files}
    all_brands = {**brand_stats, **knowledge_stats}
    
    # Generar informe
    generate_report(all_files, all_brands)
    
    # Guardar resultados detallados
    output_file = PROJECT_ROOT / 'data_quality_report.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        import sys
        sys.stdout = f
        generate_report(all_files, all_brands)
        sys.stdout = sys.__stdout__
    
    print(f"\n✔️  Informe detallado guardado en: {output_file}")

if __name__ == "__main__":
    main()
