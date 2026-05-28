"""
Módulo de Persistencia y Base de Datos - SQLite.
Garantiza almacenamiento transaccional y trazabilidad de los hallazgos de auditoría.
"""

import sqlite3
from pathlib import Path
from src.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    """Establece una conexión transaccional con la base de datos local."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")  # Forzar integridad referencial
    return conn

def inicializar_base_datos() -> None:
    """Crea la estructura de tablas si no existen en el sistema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla 1: Reporte Maestro Oficial (Fuente de Verdad)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maestro_activos (
                codigo_activo TEXT PRIMARY KEY,
                descripcion TEXT,
                fecha_compra TEXT,
                estado_bien TEXT,
                metadata_adicional TEXT
            );
        """)
        
        # Tabla 2: Trazabilidad de Lecturas de PDFs (Actas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracciones_pdf (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_archivo TEXT NOT NULL,
                pagina_pdf INTEGER NOT NULL,
                codigo_extraido_crudo TEXT NOT NULL,
                codigo_normalizado TEXT NOT NULL,
                metodo_extraccion TEXT CHECK(metodo_extraccion IN ('DIGITAL', 'OCR')),
                fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Tabla 3: Resultados finales del Cotejamiento (Resultados de Auditoría)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conciliacion_resultados (
                codigo_activo TEXT PRIMARY KEY,
                estado_conciliacion TEXT CHECK(
                    estado_conciliacion IN ('MATCH_PERFECTO', 'FALTANTE_EN_ACTA', 'SOBRANTE_EN_ACTA', 'POSIBLE_ERROR_OCR')
                ),
                codigo_sugerido_maestro TEXT,
                score_coincidencia REAL,
                observaciones TEXT
            );
        """)
        conn.commit()

def limpiar_tablas_operativas() -> None:
    """Limpia los datos de ejecuciones anteriores para evitar solapamientos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM extracciones_pdf;")
        cursor.execute("DELETE FROM conciliacion_resultados;")
        conn.commit()