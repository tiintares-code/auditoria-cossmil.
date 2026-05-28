"""
Módulo de Reportes - Sistema de Cotejamiento 2026.
Exporta los resultados de la conciliación desde SQLite a un archivo Excel profesional.
"""

import logging
import pandas as pd
from datetime import datetime
from src.database import get_connection
from src.config import OUTPUT_DIR

logger = logging.getLogger("SistemaActivos")

def generar_reporte_excel() -> bool:
    """Genera un reporte Excel final con múltiples hojas según el estado de conciliación."""
    logger.info("Iniciando generación de reporte final en Excel...")
    
    fecha_actual = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"Auditoria_Activos_{fecha_actual}.xlsx"
    ruta_salida = OUTPUT_DIR / nombre_archivo
    
    try:
        with get_connection() as conn:
            query = """
                SELECT 
                    c.codigo_activo AS 'Código Evaluado',
                    c.estado_conciliacion AS 'Estado de Auditoría',
                    c.observaciones AS 'Observaciones',
                    m.descripcion AS 'Descripción en Maestro',
                    m.estado_bien AS 'Estado Físico (Maestro)',
                    m.metadata_adicional AS 'Ubicación / Regional'
                FROM conciliacion_resultados c
                LEFT JOIN maestro_activos m ON c.codigo_activo = m.codigo_activo
                ORDER BY c.estado_conciliacion ASC
            """
            df_resultados = pd.read_sql_query(query, conn)
            
            if df_resultados.empty:
                logger.warning("No hay resultados de conciliación para exportar.")
                return False

            # Separar los DataFrames para las pestañas
            df_perfectos = df_resultados[df_resultados['Estado de Auditoría'] == 'MATCH_PERFECTO']
            df_faltantes = df_resultados[df_resultados['Estado de Auditoría'] == 'FALTANTE_EN_ACTA']
            df_errores_ocr = df_resultados[df_resultados['Estado de Auditoría'] == 'POSIBLE_ERROR_OCR']
            df_sobrantes = df_resultados[df_resultados['Estado de Auditoría'] == 'SOBRANTE_EN_ACTA']
            
            with pd.ExcelWriter(ruta_salida, engine='openpyxl') as writer:
                # Hoja 1: Todo mezclado
                df_resultados.to_excel(writer, sheet_name='Consolidado General', index=False)
                
                # Hoja 2: Los que hicieron Match
                if not df_perfectos.empty:
                    df_perfectos.to_excel(writer, sheet_name='✔ Encontrados', index=False)
                    
                # Hoja 3: LA MÁS IMPORTANTE PARA AUDITORÍA (Los que faltan)
                if not df_faltantes.empty:
                    # Ordenamos para mejor lectura
                    df_faltantes.to_excel(writer, sheet_name='❓ Faltantes', index=False)
                    
                # Hoja 4 y 5: Irregularidades
                if not df_errores_ocr.empty:
                    df_errores_ocr.to_excel(writer, sheet_name='⚠️ Errores OCR', index=False)
                if not df_sobrantes.empty:
                    df_sobrantes.to_excel(writer, sheet_name='❌ Sobrantes', index=False)
                    
        logger.info(f"Reporte generado exitosamente en: {ruta_salida}")
        return True
        
    except Exception as e:
        logger.error(f"Error crítico al generar el reporte Excel: {str(e)}", exc_info=True)
        return False