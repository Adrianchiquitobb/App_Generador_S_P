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
    # Recuerda configurar esta clave en los Secrets de Streamlit para esta App 3
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
st.title("🧩 Generador de Pistas y Sinónimos")
st.markdown("""
Carga tu archivo Excel con el listado de palabras. 
La IA analizará cada palabra para encontrar un sinónimo y redactar una pista.
""")
st.info("💡 **Consejo:** Una vez que inicies el proceso, mantén esta pestaña abierta y no refresques la página para evitar perder tu archivo final.")
st.divider()

# ACTUALIZACIÓN: Se admiten múltiples extensiones de Excel
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
        # Reiniciamos la memoria solo al presionar el botón explícitamente
        st.session_state.archivo_final_excel = None
        st.session_state.proceso_terminado = False
        
        try:
            # Leer el Excel (Pandas detecta automáticamente el motor)
            df_entrada = pd.read_excel(archivo_excel)
            
            # Validar que la columna existe
            columna_palabras = df_entrada.columns[0]
            lista_palabras = df_entrada[columna_palabras].astype(str).tolist()
            
            st.write(f"📊 Palabras a procesar: **{len(lista_palabras)}**")
            barra_progreso = st.progress(0)
            texto_estado = st.empty()
            
            # Parámetros de seguridad para la cuota
            tamaño_lote = 20  
            total_lotes = math.ceil(len(lista_palabras) / tamaño_lote)
            resultados_acumulados = []

            for i in range(total_lotes):
                lote_actual = lista_palabras[i * tamaño_lote : (i + 1) * tamaño_lote]
                porcentaje = int(((i + 1) / total_lotes) * 100)
                
                texto_estado.text(f"🧠 Creando contenido: Lote {i+1} de {total_lotes} ({porcentaje}%)...")
                
                prompt = f"""
                Actúa como un experto en crucigramas y lingüista.
                Para cada palabra de la siguiente lista, genera:
                1. Un SINÓNIMO común EN MAYÚSCULAS (si no existe o es muy forzado, usa "").
                2. Una PISTA creativa para un crucigrama (MÁXIMO 60 CARACTERES).

                Devuelve ÚNICAMENTE un objeto JSON donde cada clave sea la palabra original y el valor sea otro objeto con 'sinonimo' y 'pista'.
                Ejemplo: {{"CIELO": {{"sinonimo": "FIRMAMENTO", "pista": "Espacio azul donde flotan las nubes"}}}}
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
                    
                    # Organizar datos y forzar MAYÚSCULAS desde Python
                    for palabra in lote_actual:
                        info = datos_lote.get(palabra, {})
                        resultados_acumulados.append({
                            "Palabra": palabra,
                            "Sinónimo": str(info.get("sinonimo", "")).upper(),
                            "Pista de Crucigrama": info.get("pista", "")
                        })
                        
                except Exception as e_lote:
                    st.toast(f"⚠️ Error en lote {i+1}. Se dejarán vacíos. ({e_lote})")
                    for palabra in lote_actual:
                        resultados_acumulados.append({
                            "Palabra": palabra, "Sinónimo": "", "Pista de Crucigrama": ""
                        })

                barra_progreso.progress(porcentaje)
                
                # Semáforo para respetar la cuota
                if i < total_lotes - 1:
                    texto_estado.text("Pausando 6 segundos para estabilizar la conexión...")
                    time.sleep(6)

            # Generar el Excel final
            texto_estado.text("Construyendo archivo final...")
            df_final = pd.DataFrame(resultados_acumulados)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Crucigrama Final')
            
            # Guardar en memoria blindada
            st.session_state.archivo_final_excel = {
                "nombre": f"Sinonimos_Pistas_{archivo_excel.name}",
                "datos": buffer.getvalue()
            }
            st.session_state.proceso_terminado = True
            
            texto_estado.text("✅ ¡Archivo procesado con éxito!")
            st.balloons() 

        except Exception as e:
            st.error(f"Error crítico: {e}")

# --- CONTENEDOR DE DESCARGA BLINDADO ---
# Se dibuja siempre que exista el archivo en memoria, sin importar si la página se refresca
if st.session_state.get("proceso_terminado") and st.session_state.archivo_final_excel:
    st.divider()
    st.success("🎉 ¡Tu base de datos está lista y asegurada! Puedes descargarla a continuación.")
    
    # El botón de descarga ahora está envuelto en un contenedor destacado
    with st.container(border=True):
        st.markdown("### 📥 Archivo Final Disponible")
        st.download_button(
            label="Descargar Excel Final (3 Columnas)",
            data=st.session_state.archivo_final_excel["datos"],
            file_name=st.session_state.archivo_final_excel["nombre"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
