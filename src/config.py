"""
Módulo de Configuración Global - Sistema de Cotejamiento de Activos Fijos 2026.
Centraliza rutas, expresiones regulares y parámetros de tolerancia.
"""

import os
import re
from pathlib import Path

# --- RUTAS DEL SISTEMA ---
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
INPUT_MAESTRO_DIR = DATA_DIR / "01_input_maestro"
INPUT_PDF_DIR = DATA_DIR / "02_input_actas_pdf"
OUTPUT_DIR = DATA_DIR / "04_output_reportes"
LOG_DIR = BASE_DIR / "logs"

# Asegurar la existencia de directorios operativos
for directory in [INPUT_MAESTRO_DIR, INPUT_PDF_DIR, OUTPUT_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# --- BASE DE DATOS ---
DB_PATH = BASE_DIR / "activos_inventario.db"

# --- CONFIGURACIÓN DE EXTRACTOR Y REGEX ---
# Regex estricta para validación final
REGEX_ESTRICTO = re.compile(r"^COS-10-\d{5,}$", re.IGNORECASE)

# Regex tolerante a errores comunes de OCR en fases de escaneo inicial
REGEX_TOLERANTE_OCR = re.compile(r"\b[C0][O0][S5]-[1I][0O]-\d{5,}\b", re.IGNORECASE)

# --- PARÁMETROS DE CALIDAD Y RENDIMIENTO ---
DPI_RASTERIZACION = 300  # Resolución óptima para PaddleOCR en tablas
UMBRAL_FUZZY_MATCH = 85.0  # Límite de aceptación para RapidFuzz (0-100)

# --- LOGGING CONFIG ---
LOG_FILE = LOG_DIR / "system.log"