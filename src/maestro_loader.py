"""
Módulo de Carga del Maestro - Sistema de Cotejamiento 2026.
Lee el archivo XLSX oficial (con o sin encabezados) y lo inserta en SQLite.
"""

import pandas as pd
import logging
from pathlib import Path
from src.database import get_connection

logger = logging.getLogger("SistemaActivos")

def cargar_maestro_excel(ruta_excel: Path) -> bool:
    """
    Lee el archivo XLSX oficial, detecta dinámicamente su estructura,
    normaliza los datos y los carga en la base de datos transaccional.
    """
    logger.info(f"Iniciando lectura del archivo maestro: {ruta_excel.name}")
    
    try:
        # 1. Leemos asumiendo que NO hay encabezados para no perder la fila 1 por accidente
        df = pd.read_excel(ruta_excel, header=None, engine='openpyxl')
        
        # 2. Detección Inteligente de Encabezados (CASO A vs CASO B)
        # Revisamos si la primera fila, en la columna B (índice 1), contiene texto de encabezado
        valor_celda_b1 = str(df.iloc[0, 1]).lower()
        if "cód" in valor_celda_b1 or "cod" in valor_celda_b1 or "activo" in valor_celda_b1:
            logger.info("Encabezados detectados en el archivo. Omitiendo la primera fila.")
            df = df.iloc[1:].reset_index(drop=True)
        else:
            logger.info("Archivo sin encabezados detectado. Procesando todas las filas.")
            
        # 3. Renombrado interno de columnas basado en índices
        df.rename(columns={
            1: 'codigo_activo',
            2: 'descripcion',
            3: 'estado_bien',
            10: 'fecha_compra'
        }, inplace=True)
        
        # 4. Filtrado riguroso (Aislamos solo filas que contengan "COS-")
        # El uso de .copy() previene el error 'SettingWithCopyWarning' de Pandas
        df = df[df['codigo_activo'].astype(str).str.contains(r'COS-', na=False, case=False)].copy()
        
        # 5. Construcción de metadatos (evitando "nan" si las columnas están vacías)
        df['metadata_adicional'] = df[5].fillna("").astype(str) + " | " + \
                                   df[6].fillna("").astype(str) + " | " + \
                                   df[7].fillna("").astype(str)
        
        # 6. Extracción de las columnas finales requeridas por la DB
        df_final = df[['codigo_activo', 'descripcion', 'fecha_compra', 'estado_bien', 'metadata_adicional']].copy()
        
        # 7. Normalización del código: Quitar espacios extra y forzar MAYÚSCULAS
        df_final['codigo_activo'] = df_final['codigo_activo'].astype(str).str.strip().str.upper()
        
        total_registros = len(df_final)
        
        # 8. Inserción segura en SQLite
        with get_connection() as conn:
            # PRIMERO: Limpiamos la tabla del maestro para evitar errores de duplicidad (IntegrityError)
            conn.execute("DELETE FROM maestro_activos;")
            
            # SEGUNDO: Insertamos los datos frescos
            df_final.to_sql('maestro_activos', conn, if_exists='append', index=False)
            
        logger.info(f"Carga exitosa. {total_registros} registros oficiales insertados en la BD.")
        return True
        
    except Exception as e:
        logger.error(f"Error al procesar el archivo maestro: {str(e)}", exc_info=True)
        return False