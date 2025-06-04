#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Análisis simple de archivos de texto.
"""

import os
import re
from pathlib import Path
from tabulate import tabulate

# Configuración
BASE_DIR = Path(__file__).parent.parent
BRANDS_DIR = BASE_DIR / 'data' / 'brands'

# Función para obtener estadísticas de un archivo
def get_file_stats(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'file': file_path.name,
            'size_kb': os.path.getsize(file_path) / 1024,
            'lines': len(content.splitlines()),
            'words': len(re.findall(r'\w+', content)),
            'chars': len(content)
        }
    except Exception as e:
        print(f"Error procesando {file_path}: {str(e)}")
        return None

# Analizar archivos
print("Analizando archivos en:", BRANDS_DIR)
files = list(BRANDS_DIR.glob('*.txt'))
stats = []

for file_path in files:
    stat = get_file_stats(file_path)
    if stat:
        stats.append(stat)

# Mostrar resultados
if stats:
    # Ordenar por tamaño (KB)
    stats_sorted = sorted(stats, key=lambda x: x['size_kb'], reverse=True)
    
    # Crear tabla
    headers = ['Archivo', 'Tamaño (KB)', 'Líneas', 'Palabras', 'Caracteres']
    table = []
    
    for stat in stats_sorted:
        table.append([
            stat['file'],
            f"{stat['size_kb']:.2f}",
            stat['lines'],
            stat['words'],
            stat['chars']
        ])
    
    # Totales
    totals = ['TOTALES',
             f"{sum(s['size_kb'] for s in stats):.2f}",
             sum(s['lines'] for s in stats),
             sum(s['words'] for s in stats),
             sum(s['chars'] for s in stats)]
    
    print("\n" + "="*80)
    print("ANÁLISIS DE ARCHIVOS DE TEXTO")
    print("="*80)
    print(tabulate(table, headers=headers, tablefmt='grid'))
    print("-"*80)
    print(tabulate([totals], headers=headers, tablefmt='grid'))
    
    # Estadísticas generales
    print("\nESTADÍSTICAS GENERALES:")
    print(f"- Archivos analizados: {len(stats)}")
    print(f"- Tamaño total: {sum(s['size_kb'] for s in stats):.2f} KB")
    print(f"- Palabras totales: {sum(s['words'] for s in stats):,}")
    print(f"- Tamaño promedio: {sum(s['size_kb'] for s in stats)/len(stats):.2f} KB")
    print("="*80)
else:
    print("No se encontraron archivos para analizar.")
