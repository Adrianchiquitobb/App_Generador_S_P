import streamlit as st
import google.generativeai as genai
import io
import pandas as pd
import json
import math
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Creador de Sinonimos y Pistas", page_icon="🧩", layout="centered")

# --- SEGURIDAD DE LA API ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("⚠️ Configura la clave API de Gemini en los Secrets de esta aplicación.")
    st.stop()

model = genai.GenerativeModel('gemini-2.5-flash')

# --- INICIALIZAR MEMORIA BLINDADA ---
if "archivo_final_excel" not in st.session_state:
    st.session_state.archivo_final_excel = None
if "proceso_terminado" not in st.session_state:
    st.session_state.proceso_terminado = False

# --- INTERFAZ VISUAL ---
st.title("🧩 Generador de Sinónimos, Pistas y Autodefinidos")
st.markdown("""
Carga tu archivo Excel con el listado de palabras. 
La IA generará sinónimos, pistas estándar y pistas cortas para autodefinidos.
""")
st.info("💡 **Consejo:** Una vez que inicies el proceso, mantén esta pestaña abierta y no refresques la página.")
st.divider()

# Se admiten múltiples extensiones de Excel
archivo_excel = st.file_uploader(
    "Carga el listado base (Excel)", 
    type=["xlsx", "xls", "xlsm", "xlsb"], 
    accept_multiple_files=False,
    help="Sube tu archivo. Formatos compatibles: .xlsx, .xls, .xlsm, .xlsb"
)

if st.button("Generar Pistas y Sinónimos", type="primary", use_container_width=True):
    if not archivo_excel:
        st.warning("⚠️ Por favor, carga el archivo Excel.")
    else:
        st.session_state.archivo_final_excel = None
        st.session_state.proceso_terminado = False
        
        try:
            df_entrada = pd.read_excel(archivo_excel)
            
            columna_palabras = df_entrada.columns[0]
            lista_palabras = df_entrada[columna_palabras].astype(str).tolist()
            
            st.write(f"📊 Palabras a procesar: **{len(lista_palabras)}**")
            barra_progreso = st.progress(0)
            texto_estado = st.empty()
            
            tamaño_lote = 20  
            total_lotes = math.ceil(len(lista_palabras) / tamaño_lote)
            resultados_acumulados = []

            for i in range(total_lotes):
                lote_actual = lista_palabras[i * tamaño_lote : (i + 1) * tamaño_lote]
                porcentaje = int(((i + 1) / total_lotes) * 100)
                
                texto_estado.text(f"🧠 Creando contenido: Lote {i+1} de {total_lotes} ({porcentaje}%)...")
                
                # ACTUALIZACIÓN: Petición de 4ta columna (Autodefinidos)
                prompt = f"""
                Actúa como un experto en crucigramas y lingüista.
                Para cada palabra de la siguiente lista, genera:
                1. Un SINÓNIMO común EN MAYÚSCULAS (si no existe, usa "").
                2. Una PISTA creativa estándar (MÁXIMO 60 CARACTERES).
                3. Una PISTA PARA AUTODEFINIDO: Debe ser muy corta, idealmente entre 17 y 20 caracteres. No puede exceder los 20 caracteres.

                Devuelve ÚNICAMENTE un objeto JSON donde cada clave sea la palabra original y el valor sea otro objeto con 'sinonimo', 'pista' y 'autodefinido'.
                Ejemplo: {{"CIELO": {{"sinonimo": "FIRMAMENTO", "pista": "Espacio azul donde flotan las nubes", "autodefinido": "Bóveda azulada"}}}}
                No incluyas explicaciones ni formato markdown.

                Lista:
                {lote_actual}
                """
                
                try:
                    respuesta = model.generate_content(prompt)
                    texto_json = respuesta.text.strip()
                    
                    if "```" in texto_json:
                        texto_json = texto_json.replace("```json", "").replace("```", "").strip()
                    
                    datos_lote = json.loads(texto_json)
                    
                    for palabra in lote_actual:
                        info = datos_lote.get(palabra, {})
                        # ACTUALIZACIÓN: Agregamos el 4to elemento a la lista
                        resultados_acumulados.append([
                            palabra,
                            str(info.get("sinonimo", "")).upper(),
                            info.get("pista", ""),
                            info.get("autodefinido", "") # Cuarta columna: Autodefinidos
                        ])
                        
                except Exception as e_lote:
                    st.toast(f"⚠️ Error en lote {i+1}. ({e_lote})")
                    for palabra in lote_actual:
                        resultados_acumulados.append([palabra, "", "", ""])

                barra_progreso.progress(porcentaje)
                
                if i < total_lotes - 1:
                    time.sleep(3)

            texto_estado.text("Construyendo archivo final...")
            df_final = pd.DataFrame(resultados_acumulados)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, header=False, sheet_name='Crucigrama Final')
            
            # ACTUALIZACIÓN: Nombre de archivo con prefijo "P " y sin guiones bajos
            nombre_base = archivo_excel.name.replace('_', ' ')
            nombre_descarga = f"P {nombre_base}"

            st.session_state.archivo_final_excel = {
                "nombre": nombre_descarga,
                "datos": buffer.getvalue()
            }
            st.session_state.proceso_terminado = True
            
            texto_estado.text("✅ ¡Archivo procesado con éxito!")
            st.balloons()

        except Exception as e:
            st.error(f"Error crítico: {e}")

# --- CONTENEDOR DE DESCARGA ---
if st.session_state.get("proceso_terminado") and st.session_state.archivo_final_excel:
    st.divider()
    st.success("🎉 ¡Tu base de datos con pistas de autodefinidos está lista!")
    
    with st.container(border=True):
        st.markdown(f"### 📥 Archivo: {st.session_state.archivo_final_excel['nombre']}")
        st.download_button(
            label="Descargar Excel Final (4 Columnas)",
            data=st.session_state.archivo_final_excel["datos"],
            file_name=st.session_state.archivo_final_excel["nombre"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
