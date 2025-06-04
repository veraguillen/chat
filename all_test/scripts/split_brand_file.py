#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para dividir archivos de marca en chunks lógicos.
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tamaño máximo de cada chunk (en caracteres aprox.)
MAX_CHUNK_SIZE = 1500
# Tamaño de superposición entre chunks (en caracteres)
CHUNK_OVERLAP = 200
# Nivel de encabezado para dividir secciones
SECTION_HEADER_LEVEL = re.compile(r'^([A-Z][A-ZÁÉÍÓÚ\s]+):')


def clean_text(text: str) -> str:
    """Limpia el texto de espacios en blanco innecesarios."""
    # Reemplazar múltiples espacios por uno solo
    text = re.sub(r'\s+', ' ', text)
    # Eliminar espacios al inicio y final
    text = text.strip()
    return text


def split_into_sections(content: str) -> List[Tuple[str, str]]:
    """
    Divide el contenido en secciones basadas en encabezados.
    
    Retorna una lista de tuplas (título, contenido).
    """
    sections = []
    current_section = None
    current_content = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Verificar si es un encabezado de sección
        header_match = SECTION_HEADER_LEVEL.match(line)
        if header_match:
            if current_section is not None and current_content:
                sections.append((current_section, '\n'.join(current_content)))
            current_section = line
            current_content = []
        else:
            if current_section is None:
                current_section = "INICIO"
            current_content.append(line)
    
    # Asegurarse de agregar la última sección
    if current_section is not None and current_content:
        sections.append((current_section, '\n'.join(current_content)))
    
    return sections


def create_chunks_from_sections(sections: List[Tuple[str, str]]) -> List[str]:
    """Crea chunks a partir de las secciones, respetando los límites de tamaño."""
    chunks = []
    current_chunk = []
    current_size = 0
    
    for section_title, section_content in sections:
        section_text = f"{section_title}\n{section_content}"
        section_size = len(section_text)
        
        # Si la sección es muy grande, dividirla
        if section_size > MAX_CHUNK_SIZE:
            # Si hay contenido en el chunk actual, guardarlo
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Dividir la sección grande en chunks más pequeños
            words = section_text.split()
            temp_chunk = []
            temp_size = 0
            
            for word in words:
                word_size = len(word) + 1  # +1 por el espacio
                if temp_size + word_size > MAX_CHUNK_SIZE:
                    chunks.append(' '.join(temp_chunk))
                    temp_chunk = []
                    temp_size = 0
                temp_chunk.append(word)
                temp_size += word_size
            
            if temp_chunk:
                chunks.append(' '.join(temp_chunk))
        else:
            # Si la sección cabe en el chunk actual, agregarla
            if current_size + section_size > MAX_CHUNK_SIZE and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(section_text)
            current_size += section_size + 2  # +2 por los saltos de línea
    
    # Agregar el último chunk si hay contenido
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def process_brand_file(input_file: str, output_dir: str) -> None:
    """Procesa un archivo de marca y lo divide en chunks."""
    # Crear directorio de salida si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    # Leer el archivo de entrada
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error al leer el archivo {input_file}: {str(e)}")
        return
    
    # Limpiar el contenido
    content = clean_text(content)
    
    # Dividir en secciones
    sections = split_into_sections(content)
    logger.info(f"Se identificaron {len(sections)} secciones en el archivo.")
    
    # Crear chunks
    chunks = create_chunks_from_sections(sections)
    logger.info(f"Se crearon {len(chunks)} chunks del archivo.")
    
    # Guardar cada chunk en un archivo separado
    base_name = Path(input_file).stem
    for i, chunk in enumerate(chunks, 1):
        output_file = os.path.join(output_dir, f"{base_name}_chunk_{i:02d}.txt")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(chunk)
            logger.info(f"Chunk {i} guardado en {output_file} (tamaño: {len(chunk)} caracteres)")
        except Exception as e:
            logger.error(f"Error al guardar el chunk {i}: {str(e)}")
    
    logger.info("Proceso de división completado.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Divide archivos de marca en chunks lógicos.')
    parser.add_argument('input_file', help='Ruta al archivo de entrada')
    parser.add_argument('-o', '--output-dir', default='output_chunks',
                      help='Directorio de salida para los chunks (por defecto: output_chunks)')
    
    args = parser.parse_args()
    
    process_brand_file(args.input_file, args.output_dir)
