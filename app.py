"""
Interfaz Web (Frontend) - Sistema de Cotejamiento COSSMIL 2026.
Construido con Streamlit.
"""

import streamlit as st
import os
import shutil
from pathlib import Path

# Importamos nuestro motor ya construido
from src.config import INPUT_MAESTRO_DIR, INPUT_PDF_DIR, OUTPUT_DIR
from src.database import inicializar_base_datos, limpiar_tablas_operativas
from src.maestro_loader import cargar_maestro_excel
from src.extractor_pdf import procesar_directorio_pdfs
from src.matcher import ejecutar_conciliacion
from src.reporter import generar_reporte_excel

# Configuración de la página web
st.set_page_config(page_title="Auditoría COSSMIL", page_icon="📊", layout="centered")

def limpiar_directorios():
    """Limpia las carpetas de datos de ejecuciones anteriores."""
    for directorio in [INPUT_MAESTRO_DIR, INPUT_PDF_DIR]:
        for archivo in directorio.glob("*"):
            if archivo.is_file():
                archivo.unlink()

# --- DISEÑO DE LA INTERFAZ WEB ---
st.title("📊 Sistema de Auditoría de Activos - COSSMIL")
st.markdown("Cargue el reporte maestro y las actas digitalizadas para cruzar la información automáticamente.")

# Sección 1: Subida de Archivos
st.header("1. Carga de Datos")
archivo_maestro = st.file_uploader("Subir Reporte Maestro Oficial (Excel .xlsx)", type=["xlsx"])
archivos_pdfs = st.file_uploader("Subir Actas Físicas (PDFs)", type=["pdf"], accept_multiple_files=True)

# Sección 2: Ejecución
st.header("2. Procesamiento Automático")
if st.button("🚀 Ejecutar Auditoría Integral", type="primary"):
    
    if not archivo_maestro:
        st.error("⚠️ Falta el Reporte Maestro. Por favor, súbelo antes de continuar.")
    elif not archivos_pdfs:
        st.error("⚠️ Faltan las Actas en PDF. Por favor, sube al menos una.")
    else:
        # Iniciamos el proceso visual
        barra_progreso = st.progress(0, text="Iniciando sistema y limpiando datos anteriores...")
        
        # 1. Preparar el entorno físico
        limpiar_directorios()
        inicializar_base_datos()
        limpiar_tablas_operativas()
        
        # Guardar el Excel subido en nuestra carpeta 'data/01_input_maestro'
        ruta_maestro_local = INPUT_MAESTRO_DIR / archivo_maestro.name
        with open(ruta_maestro_local, "wb") as f:
            f.write(archivo_maestro.getbuffer())
            
        # Guardar los PDFs subidos en nuestra carpeta 'data/02_input_actas_pdf'
        for pdf in archivos_pdfs:
            ruta_pdf_local = INPUT_PDF_DIR / pdf.name
            with open(ruta_pdf_local, "wb") as f:
                f.write(pdf.getbuffer())

        # 2. Ejecutar el Pipeline (Nuestro Backend)
        try:
            barra_progreso.progress(25, text="1/4: Cargando Reporte Maestro en Base de Datos...")
            if not cargar_maestro_excel(ruta_maestro_local):
                st.error("Error al leer el archivo maestro. Verifica el formato.")
                st.stop()
                
            barra_progreso.progress(50, text="2/4: Extrayendo códigos de los PDFs (Procesamiento Digital)...")
            procesar_directorio_pdfs(INPUT_PDF_DIR)
            
            barra_progreso.progress(75, text="3/4: Cruzando datos e identificando faltantes...")
            if not ejecutar_conciliacion():
                st.error("Error en el cruce de datos.")
                st.stop()
                
            barra_progreso.progress(90, text="4/4: Generando reporte Excel final...")
            if generar_reporte_excel():
                barra_progreso.progress(100, text="¡Auditoría Completada con Éxito!")
                st.success("✅ El cruce de datos ha finalizado correctamente.")
                
                # Buscar el archivo generado para ofrecer la descarga
                reportes_generados = list(OUTPUT_DIR.glob("*.xlsx"))
                if reportes_generados:
                    reporte_final = max(reportes_generados, key=os.path.getctime) # Toma el más reciente
                    
                    with open(reporte_final, "rb") as file:
                        st.download_button(
                            label="📥 Descargar Reporte de Auditoría",
                            data=file,
                            file_name=reporte_final.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            else:
                st.error("Hubo un problema al generar el archivo Excel.")
                
        except Exception as e:
            st.error(f"❌ Ocurrió un error crítico: {str(e)}")