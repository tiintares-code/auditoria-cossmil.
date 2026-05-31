"""
Módulo de Reportes - Sistema de Cotejamiento 2026.
Exporta los resultados a un Excel Corporativo con diseño, filtros y formato condicional.
"""

import logging
import pandas as pd
from datetime import datetime
from src.database import get_connection
from src.config import OUTPUT_DIR

logger = logging.getLogger("SistemaActivos")

def generar_reporte_excel() -> bool:
    """Genera un reporte Excel final profesional con formato y colores."""
    logger.info("Iniciando generación de reporte final en Excel (Estilo Corporativo)...")
    
    fecha_actual = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"Auditoria_COSSMIL_{fecha_actual}.xlsx"
    ruta_salida = OUTPUT_DIR / nombre_archivo
    
    try:
        with get_connection() as conn:
            # Consulta SQL para extraer los datos
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
                ORDER BY 
                    CASE c.estado_conciliacion 
                        WHEN 'FALTANTE_EN_ACTA' THEN 1
                        WHEN 'POSIBLE_ERROR_OCR' THEN 2
                        WHEN 'SOBRANTE_EN_ACTA' THEN 3
                        WHEN 'MATCH_PERFECTO' THEN 4
                        ELSE 5
                    END ASC
            """
            df_resultados = pd.read_sql_query(query, conn)
            
            if df_resultados.empty:
                logger.warning("No hay resultados para exportar.")
                return False

            # Separar DataFrames para cada pestaña
            df_perfectos = df_resultados[df_resultados['Estado de Auditoría'] == 'MATCH_PERFECTO']
            df_faltantes = df_resultados[df_resultados['Estado de Auditoría'] == 'FALTANTE_EN_ACTA']
            df_errores_ocr = df_resultados[df_resultados['Estado de Auditoría'] == 'POSIBLE_ERROR_OCR']
            df_sobrantes = df_resultados[df_resultados['Estado de Auditoría'] == 'SOBRANTE_EN_ACTA']
            
            # Crear el archivo Excel utilizando el motor avanzado xlsxwriter
            with pd.ExcelWriter(ruta_salida, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # --- 1. DEFINICIÓN DE FORMATOS Y COLORES ---
                formato_encabezado = workbook.add_format({
                    'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center',
                    'bg_color': '#002060', 'font_color': 'white', 'border': 1
                })
                
                # Colores para el formato condicional
                formato_verde = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                formato_rojo = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                formato_amarillo = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
                formato_azul = workbook.add_format({'bg_color': '#B4C6E7', 'font_color': '#003366'})
                
                hojas = {
                    'Consolidado General': df_resultados,
                    '❓ Faltantes': df_faltantes,
                    '⚠️ Errores OCR': df_errores_ocr,
                    '❌ Sobrantes': df_sobrantes,
                    '✔ Encontrados': df_perfectos
                }
                
                # --- 2. APLICACIÓN DE DISEÑO A CADA HOJA ---
                for nombre_hoja, df in hojas.items():
                    if df.empty and nombre_hoja != 'Consolidado General':
                        continue
                        
                    df.to_excel(writer, sheet_name=nombre_hoja, index=False)
                    worksheet = writer.sheets[nombre_hoja]
                    
                    # Dar formato a los encabezados y habilitar Auto-Filtros
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, formato_encabezado)
                    worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
                    
                    # Ajustar el ancho de las columnas para una lectura cómoda
                    worksheet.set_column('A:A', 18)  # Código
                    worksheet.set_column('B:B', 22)  # Estado
                    worksheet.set_column('C:C', 55)  # Observaciones (Origen)
                    worksheet.set_column('D:D', 45)  # Descripción
                    worksheet.set_column('E:E', 20)  # Estado físico
                    worksheet.set_column('F:F', 25)  # Ubicación
                    
                    # Aplicar Formato Condicional Automático a la columna de "Estado"
                    rango_estados = f'B2:B{len(df)+1}'
                    worksheet.conditional_format(rango_estados, {'type': 'cell', 'criteria': '==', 'value': '"MATCH_PERFECTO"', 'format': formato_verde})
                    worksheet.conditional_format(rango_estados, {'type': 'cell', 'criteria': '==', 'value': '"FALTANTE_EN_ACTA"', 'format': formato_rojo})
                    worksheet.conditional_format(rango_estados, {'type': 'cell', 'criteria': '==', 'value': '"POSIBLE_ERROR_OCR"', 'format': formato_amarillo})
                    worksheet.conditional_format(rango_estados, {'type': 'cell', 'criteria': '==', 'value': '"SOBRANTE_EN_ACTA"', 'format': formato_azul})
                    
        logger.info(f"Reporte corporativo generado exitosamente en: {ruta_salida}")
        return True
        
    except Exception as e:
        logger.error(f"Error crítico al generar el Excel corporativo: {str(e)}", exc_info=True)
        return False