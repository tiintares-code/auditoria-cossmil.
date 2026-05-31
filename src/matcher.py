"""
Módulo de Conciliación - Sistema de Cotejamiento 2026.
Cruza las extracciones de los PDFs contra el Maestro Oficial detectando Sobrantes, Errores y Faltantes.
Incluye trazabilidad de documentos de origen.
"""

import logging
import pandas as pd
from rapidfuzz import process, fuzz
from src.database import get_connection
from src.config import UMBRAL_FUZZY_MATCH

logger = logging.getLogger("SistemaActivos")

def ejecutar_conciliacion() -> bool:
    """Ejecuta el cruce de datos y guarda los resultados en la base de datos."""
    logger.info("Iniciando motor de conciliación integral con trazabilidad...")
    
    try:
        with get_connection() as conn:
            # 1. Cargar el maestro oficial
            df_maestro = pd.read_sql_query("SELECT codigo_activo FROM maestro_activos", conn)
            set_maestro = set(df_maestro['codigo_activo'].tolist())
            
            # 2. Cargar los códigos extraídos CON SU ORIGEN EXACTO (Archivo y Página)
            query_extraidos = """
                SELECT 
                    codigo_normalizado, 
                    GROUP_CONCAT(nombre_archivo || ' (Pág ' || CAST(pagina_pdf AS TEXT) || ')', ' + ') as origen
                FROM extracciones_pdf
                GROUP BY codigo_normalizado
            """
            df_extraidos = pd.read_sql_query(query_extraidos, conn)
            
            resultados = []
            codigos_maestro_detectados = set()

            if df_extraidos.empty:
                logger.warning("No hay códigos extraídos. Todos los activos del maestro serán marcados como Faltantes.")
            else:
                # 3. Lógica de Cotejamiento con Inyección de Trazabilidad
                for _, row in df_extraidos.iterrows():
                    codigo_pdf = row['codigo_normalizado']
                    origen = row['origen'] # Aquí viene: "ACTA_AF_00389.pdf (Pág 1)"
                    
                    if codigo_pdf in set_maestro:
                        resultados.append((codigo_pdf, 'MATCH_PERFECTO', codigo_pdf, 100.0, f"Validado en: {origen}"))
                        codigos_maestro_detectados.add(codigo_pdf)
                    else:
                        match = process.extractOne(codigo_pdf, set_maestro, scorer=fuzz.ratio)
                        if match:
                            mejor_coincidencia, puntaje, _ = match
                            if puntaje >= UMBRAL_FUZZY_MATCH:
                                # Inyectamos el origen en la observación para los errores OCR
                                observacion = f"Posible error OCR. Sugerencia: {mejor_coincidencia}. | Hallado en: {origen}"
                                resultados.append((codigo_pdf, 'POSIBLE_ERROR_OCR', mejor_coincidencia, float(puntaje), observacion))
                                codigos_maestro_detectados.add(mejor_coincidencia)
                            else:
                                resultados.append((codigo_pdf, 'SOBRANTE_EN_ACTA', None, 0.0, f"Activo sin respaldo en el maestro. | Hallado en: {origen}"))
                        else:
                            resultados.append((codigo_pdf, 'SOBRANTE_EN_ACTA', None, 0.0, f"Activo sin respaldo en el maestro. | Hallado en: {origen}"))

            # 4. LÓGICA DE FALTANTES
            activos_faltantes = set_maestro - codigos_maestro_detectados
            for codigo_faltante in activos_faltantes:
                resultados.append((codigo_faltante, 'FALTANTE_EN_ACTA', None, 0.0, "Registrado en Maestro oficial, pero NO se encontró en ninguna acta física."))

            # 5. Guardar todo en la Base de Datos
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conciliacion_resultados;")
            
            cursor.executemany("""
                INSERT INTO conciliacion_resultados 
                (codigo_activo, estado_conciliacion, codigo_sugerido_maestro, score_coincidencia, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, resultados)
            conn.commit()
            
            logger.info(f"Conciliación finalizada. Resumen de Auditoría:")
            logger.info(f"-> Matches Perfectos: {len(codigos_maestro_detectados)}")
            logger.info(f"-> Activos No Encontrados (Faltantes): {len(activos_faltantes)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error crítico en el cruce de datos: {str(e)}", exc_info=True)
        return False