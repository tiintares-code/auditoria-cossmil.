"""
Módulo de Extracción de PDFs (100% Digital) - Sistema de Cotejamiento 2026.
Utiliza exclusivamente PyMuPDF para extraer texto nativo. 
Omitiendo imágenes y fotocopias por reglas de estabilidad y rendimiento.
"""

import logging
import fitz  # PyMuPDF
from pathlib import Path

from src.config import REGEX_TOLERANTE_OCR, REGEX_ESTRICTO
from src.database import get_connection

logger = logging.getLogger("SistemaActivos")

def normalizar_codigo_ocr(codigo_crudo: str) -> str:
    """Normaliza códigos y corrige posibles errores de tipeo o formato."""
    codigo = codigo_crudo.upper().strip()
    
    partes = codigo.split('-')
    if len(partes) != 3:
        codigo = codigo.replace(" ", "-").replace("_", "-")
        partes = codigo.split('-')
        
    if len(partes) >= 3:
        prefijo = partes[0].replace('0', 'O').replace('5', 'S')  
        fijo = partes[1].replace('O', '0').replace('I', '1')      
        secuencia = partes[2].replace('O', '0').replace('I', '1') 
        
        codigo_limpio = f"{prefijo}-{fijo}-{secuencia}"
        
        if REGEX_ESTRICTO.match(codigo_limpio):
            return codigo_limpio
            
    return codigo_crudo 

def procesar_documento(ruta_pdf: Path) -> int:
    """Procesa un PDF leyendo exclusivamente su capa de texto digital."""
    logger.info(f"Procesando documento: {ruta_pdf.name}")
    hallazgos_insertar = []
    
    try:
        doc = fitz.open(ruta_pdf)
        total_paginas = len(doc)
        logger.info(f"   -> Documento abierto. Total de páginas a analizar: {total_paginas}")
        
        for num_pagina, pagina in enumerate(doc, start=1):
            metodo = "DIGITAL"
            
            texto_pagina = pagina.get_text("text")
            
            # REGLA DE NEGOCIO: Si el texto es muy corto, es una imagen o fotocopia. Se omite.
            if len(texto_pagina.strip()) < 50:
                logger.warning(f"      [Pág {num_pagina}] OMITIDA: Imagen o escaneo físico detectado. El sistema solo procesa actas digitales.")
                continue # Saltamos esta página sin que el sistema colapse
            
            coincidencias = REGEX_TOLERANTE_OCR.findall(texto_pagina)
            codigos_unicos = set(coincidencias)
            
            if codigos_unicos:
                logger.info(f"      [Pág {num_pagina}] Se encontraron {len(codigos_unicos)} códigos de activos.")
            
            for codigo_crudo in codigos_unicos:
                codigo_limpio = normalizar_codigo_ocr(codigo_crudo)
                hallazgos_insertar.append((
                    ruta_pdf.name,
                    num_pagina,
                    codigo_crudo,
                    codigo_limpio,
                    metodo
                ))
                
        doc.close()
        
        if hallazgos_insertar:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT INTO extracciones_pdf 
                    (nombre_archivo, pagina_pdf, codigo_extraido_crudo, codigo_normalizado, metodo_extraccion)
                    VALUES (?, ?, ?, ?, ?)
                """, hallazgos_insertar)
                conn.commit()
                
        logger.info(f"Fin {ruta_pdf.name}: {len(hallazgos_insertar)} códigos guardados exitosamente.")
        return len(hallazgos_insertar)
        
    except Exception as e:
        logger.error(f"Error procesando {ruta_pdf.name}: {e}")
        return 0

def procesar_directorio_pdfs(directorio: Path) -> None:
    """Itera sobre todos los PDFs e informa el progreso."""
    archivos_pdf = list(directorio.glob("*.pdf"))
    total_codigos = 0
    
    for i, pdf in enumerate(archivos_pdf, start=1):
        logger.info(f"\n--- Iniciando Extracción Archivo {i}/{len(archivos_pdf)} ---")
        total_codigos += procesar_documento(pdf)
        
    logger.info(f"Extracción global finalizada. Se extrajeron {total_codigos} códigos nativos en total.")