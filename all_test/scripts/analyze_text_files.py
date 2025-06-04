#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para analizar archivos de texto que serán vectorizados.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
BRANDS_DIR = DATA_DIR / 'brands'
KNOWLEDGE_DIR = DATA_DIR / 'knowledge'
OUTPUT_DIR = BASE_DIR / 'analysis_output'

# Crear directorio de salida si no existe
OUTPUT_DIR.mkdir(exist_ok=True)

def get_file_stats(file_path: Path) -> dict:
    """Obtiene estadísticas de un archivo de texto."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Calcular estadísticas
        stats = {
            'file_name': file_path.name,
            'file_path': str(file_path.relative_to(BASE_DIR)),
            'file_size_kb': os.path.getsize(file_path) / 1024,
            'num_lines': len(content.splitlines()),
            'num_words': len(re.findall(r'\w+', content)),
            'num_chars': len(content),
            'avg_line_length': sum(len(line) for line in content.splitlines()) / max(1, len(content.splitlines())),
            'empty_lines': sum(1 for line in content.splitlines() if not line.strip()),
        }
        return stats
    except Exception as e:
        print(f"Error procesando {file_path}: {str(e)}")
        return None

def analyze_text_files() -> pd.DataFrame:
    """Analiza todos los archivos de texto en los directorios de marcas y conocimiento."""
    all_files = []
    
    # Buscar archivos .txt en los directorios
    for dir_path in [BRANDS_DIR, KNOWLEDGE_DIR]:
        if not dir_path.exists():
            print(f"Advertencia: El directorio {dir_path} no existe.")
            continue
            
        for file_path in dir_path.glob('**/*.txt'):
            stats = get_file_stats(file_path)
            if stats:
                stats['source'] = 'brands' if 'brands' in str(file_path) else 'knowledge'
                all_files.append(stats)
    
    # Crear DataFrame con los resultados
    if not all_files:
        print("No se encontraron archivos .txt para analizar.")
        return None
        
    df = pd.DataFrame(all_files)
    return df

def generate_report(df: pd.DataFrame) -> None:
    """Genera un informe con estadísticas de los archivos."""
    if df is None or df.empty:
        print("No hay datos para generar el informe.")
        return
    
    # Generar estadísticas generales
    report = []
    
    # Estadísticas generales
    total_files = len(df)
    total_size_mb = df['file_size_kb'].sum() / 1024
    avg_file_size_kb = df['file_size_kb'].mean()
    
    report.append("# Análisis de Archivos de Texto")
    report.append(f"- Total de archivos analizados: {total_files}")
    report.append(f"- Tamaño total: {total_size_mb:.2f} MB")
    report.append(f"- Tamaño promedio por archivo: {avg_file_size_kb:.2f} KB")
    
    # Estadísticas por fuente (brands/knowledge)
    if 'source' in df.columns:
        source_stats = df.groupby('source').agg({
            'file_name': 'count',
            'file_size_kb': 'sum',
            'num_words': 'sum',
            'num_chars': 'sum'
        }).reset_index()
        
        report.append("\n## Estadísticas por Fuente")
        report.append(source_stats.to_markdown(index=False, tablefmt="pipe"))
    
    # Top 10 archivos más grandes
    top_large = df.nlargest(10, 'file_size_kb')
    report.append("\n## Top 10 Archivos más Grandes")
    report.append(top_large[['file_name', 'file_size_kb', 'num_words', 'source']].to_markdown(index=False, tablefmt="pipe"))
    
    # Guardar informe
    report_path = OUTPUT_DIR / 'file_analysis_report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\nInforme generado en: {report_path}")
    
    # Generar gráficos
    generate_plots(df)

def generate_plots(df: pd.DataFrame) -> None:
    """Genera gráficos de análisis."""
    plt.figure(figsize=(12, 6))
    
    # Gráfico de distribución de tamaños
    plt.subplot(1, 2, 1)
    sns.histplot(df['file_size_kb'], bins=20, kde=True)
    plt.title('Distribución de Tamaños de Archivo (KB)')
    plt.xlabel('Tamaño (KB)')
    plt.ylabel('Cantidad de Archivos')
    
    # Gráfico de palabras por archivo
    plt.subplot(1, 2, 2)
    sns.scatterplot(data=df, x='file_size_kb', y='num_words', hue='source' if 'source' in df.columns else None)
    plt.title('Tamaño vs. Número de Palabras')
    plt.xlabel('Tamaño (KB)')
    plt.ylabel('Número de Palabras')
    
    plt.tight_layout()
    plot_path = OUTPUT_DIR / 'file_analysis_plots.png'
    plt.savefig(plot_path)
    plt.close()
    
    print(f"Gráficos guardados en: {plot_path}")

if __name__ == "__main__":
    print("Analizando archivos de texto...")
    df = analyze_text_files()
    
    if df is not None and not df.empty:
        print("\nResumen de archivos analizados:")
        print(f"- Total de archivos: {len(df)}")
        print(f"- Tamaño total: {df['file_size_kb'].sum() / 1024:.2f} MB")
        print(f"- Palabras totales: {df['num_words'].sum():,}")
        
        generate_report(df)
        
        # Mostrar los primeros registros
        print("\nMuestra de datos:")
        print(df[['file_name', 'file_size_kb', 'num_words', 'source']].head().to_markdown(index=False, tablefmt="pipe"))
    else:
        print("No se encontraron archivos para analizar.")
