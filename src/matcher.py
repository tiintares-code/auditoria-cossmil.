"""
Módulo de Conciliación - Sistema de Cotejamiento 2026.
Cruza las extracciones de los PDFs contra el Maestro Oficial detectando Sobrantes, Errores y Faltantes.
"""

import logging
import pandas as pd
from rapidfuzz import process, fuzz
from src.database import get_connection
from src.config import UMBRAL_FUZZY_MATCH

logger = logging.getLogger("SistemaActivos")

def ejecutar_conciliacion() -> bool:
    """Ejecuta el cruce de datos y guarda los resultados en la base de datos."""
    logger.info("Iniciando motor de conciliación integral...")
    
    try:
        with get_connection() as conn:
            # 1. Cargar el maestro oficial
            df_maestro = pd.read_sql_query("SELECT codigo_activo FROM maestro_activos", conn)
            set_maestro = set(df_maestro['codigo_activo'].tolist())
            
            # 2. Cargar los códigos extraídos de los PDFs
            df_extraidos = pd.read_sql_query("SELECT DISTINCT codigo_normalizado FROM extracciones_pdf", conn)
            lista_extraidos = df_extraidos['codigo_normalizado'].tolist()
            
            resultados = []
            
            # NUEVO: Control para rastrear qué activos del maestro sí aparecieron
            codigos_maestro_detectados = set()

            if not lista_extraidos:
                logger.warning("No hay códigos extraídos. Todos los activos del maestro serán marcados como Faltantes.")
            else:
                # 3. Lógica de Cotejamiento de lo Extraído (Matches, OCR Errors, Sobrantes)
                for codigo_pdf in lista_extraidos:
                    if codigo_pdf in set_maestro:
                        resultados.append((codigo_pdf, 'MATCH_PERFECTO', codigo_pdf, 100.0, "Validado correctamente en acta."))
                        codigos_maestro_detectados.add(codigo_pdf)
                    else:
                        match = process.extractOne(codigo_pdf, set_maestro, scorer=fuzz.ratio)
                        if match:
                            mejor_coincidencia, puntaje, _ = match
                            if puntaje >= UMBRAL_FUZZY_MATCH:
                                observacion = f"Posible error de lectura OCR. ¿Quiso decir {mejor_coincidencia}?"
                                resultados.append((codigo_pdf, 'POSIBLE_ERROR_OCR', mejor_coincidencia, float(puntaje), observacion))
                                codigos_maestro_detectados.add(mejor_coincidencia)
                            else:
                                resultados.append((codigo_pdf, 'SOBRANTE_EN_ACTA', None, 0.0, "Activo físico en acta sin respaldo en el maestro."))
                        else:
                            resultados.append((codigo_pdf, 'SOBRANTE_EN_ACTA', None, 0.0, "Activo físico en acta sin respaldo en el maestro."))

            # 4. LÓGICA DE FALTANTES: Maestro original MENOS los detectados
            activos_faltantes = set_maestro - codigos_maestro_detectados
            for codigo_faltante in activos_faltantes:
                # OJO: Aquí registramos el código que debió estar, pero no se encontró.
                resultados.append((codigo_faltante, 'FALTANTE_EN_ACTA', None, 0.0, "Registrado en Maestro oficial, pero NO se encontró en ninguna acta."))

            # 5. Guardar todo en la Base de Datos
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conciliacion_resultados;")
            
            cursor.executemany("""
                INSERT INTO conciliacion_resultados 
                (codigo_activo, estado_conciliacion, codigo_sugerido_maestro, score_coincidencia, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, resultados)
            conn.commit()
            
            # Estadísticas de auditoría
            logger.info(f"Conciliación finalizada. Resumen de Auditoría:")
            logger.info(f"-> Matches Perfectos: {len(codigos_maestro_detectados)}")
            logger.info(f"-> Activos No Encontrados (Faltantes): {len(activos_faltantes)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error crítico en el cruce de datos: {str(e)}", exc_info=True)
        return False