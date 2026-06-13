import os
import requests
import traceback
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

from servicios import obtener_saldo_actual, extraer_datos_recibo_llm, guardar_en_sheets
from generador_pdf import generar_comprobante_pdf

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Diccionario complejo de estados para la máquina secuencial
user_states = {}

@app.get("/")
def home():
    return {"status": "Servidor funcionando correctamente"}

def enviar_mensaje(chat_id, texto):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"})

def procesar_imagen_y_confirmar(chat_id):
    """Descarga la imagen, llama a Groq con el contexto y muestra el resumen."""
    state = user_states[chat_id]
    enviar_mensaje(chat_id, "⚙️ Cruzando imagen con tu contexto usando IA. Dame un momento...")
    
    try:
        # Obtener imagen
        file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={state['file_id']}").json()
        file_path = file_info["result"]["file_path"]
        image_bytes = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}").content

        # Consolidar contexto manual si lo hay
        contexto = state.get("contexto_texto", "")
        if not contexto:
            c_man = state.get("contexto_manual", {})
            contexto = f"Tipo: {c_man.get('tipo', '')}, Motivo: {c_man.get('motivo', '')}, Acreedor: {c_man.get('acreedor', '')}, Deudor: {c_man.get('deudor', '')}"

        # Llamar al Super-Prompt
        datos_ia = extraer_datos_recibo_llm(image_bytes, contexto)

        if "error" not in datos_ia:
            state["step"] = "confirmar"
            state["datos_procesados"] = datos_ia
            
            resumen = (
                f"🧾 **Datos Procesados (Listo para guardar):**\n\n"
                f"📅 **Fecha:** {datos_ia.get('fecha')}\n"
                f"🏷️ **Concepto:** {datos_ia.get('concepto')}\n"
                f"🔄 **Tipo:** {datos_ia.get('tipo')} ({datos_ia.get('ing_eg')})\n"
                f"📌 **Motivo:** {datos_ia.get('motivo')}\n"
                f"👤 **Acreedor:** {datos_ia.get('acreedor')}\n"
                f"👤 **Deudor:** {datos_ia.get('deudor')}\n"
                f"💰 **Monto:** S/ {datos_ia.get('monto')}\n"
                f"⚖️ **Saldo Previo en Caja:** S/ {state['saldo_previo']}\n\n"
                f"¿Guardar en la base de datos?\n"
                f"1) Sí, registrar ahora\n"
                f"2) Guardar y generar PDF de respaldo\n"
                f"3) /cancelar"
            )
            enviar_mensaje(chat_id, resumen)
        else:
            enviar_mensaje(chat_id, "❌ Error al analizar la imagen con Groq.")
            user_states.pop(chat_id, None)

    except Exception as e:
        traceback.print_exc()
        enviar_mensaje(chat_id, "⚠️ Error interno durante el procesamiento.")
        user_states.pop(chat_id, None)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data:
        return {"status": "ok"}

    message = data["message"]
    chat_id = str(message["chat"]["id"])

    # --- 1. RECEPCIÓN DE IMAGEN ---
    if "photo" in message:
        user_states[chat_id] = {
            "file_id": message["photo"][-1]["file_id"],
            "caption": message.get("caption", ""),
            "contexto_manual": {}
        }
        
        # Validar Saldo Inicial Bloqueante
        saldo_actual = obtener_saldo_actual()
        if saldo_actual is None:
            user_states[chat_id]["step"] = "pedir_saldo_base"
            enviar_mensaje(chat_id, "⚠️ **Base de datos vacía.**\nEste es el primer registro. Por favor, escribe el **Saldo Base / Inicial** en caja (ej. 1500.50) para poder iniciar las operaciones.")
            return {"status": "ok"}
        
        user_states[chat_id]["saldo_previo"] = saldo_actual

        # Bifurcación automática por leyenda
        if user_states[chat_id]["caption"]:
            user_states[chat_id]["contexto_texto"] = user_states[chat_id]["caption"]
            procesar_imagen_y_confirmar(chat_id)
        else:
            user_states[chat_id]["step"] = "elegir_metodo"
            enviar_mensaje(chat_id, "Tengo la foto. ¿Cómo completamos los datos faltantes?\n\n✍️ Escribe **'manual'** para que te pregunte uno por uno.\n🗣️ O escribe **todo de golpe aquí** (ej. 'Compra para integración, acreedor Proyecta, deudor el museo').")
        
        return {"status": "ok"}

    # --- 2. MANEJO DE TEXTO (MÁQUINA DE ESTADOS) ---
    state = user_states.get(chat_id)
    if not state:
        enviar_mensaje(chat_id, "👋 ¡Hola, Tesorería! Envíame la foto del comprobante o captura para empezar.\n💡 *Tip: Si pones toda la explicación en la leyenda de la foto, salto las preguntas y lo proceso al instante.*")
        return {"status": "ok"}

    text = message.get("text", "").strip()

    if text.lower() == "/cancelar":
        user_states.pop(chat_id, None)
        enviar_mensaje(chat_id, "❌ Operación cancelada. Envíame otra foto cuando desees.")
        return {"status": "ok"}

    # Bloque: Configuración inicial del saldo
    if state.get("step") == "pedir_saldo_base":
        try:
            saldo_ingresado = float(text.replace(",", ""))
            state["saldo_previo"] = saldo_ingresado
            
            if state["caption"]:
                state["contexto_texto"] = state["caption"]
                procesar_imagen_y_confirmar(chat_id)
            else:
                state["step"] = "elegir_metodo"
                enviar_mensaje(chat_id, f"✅ Saldo inicial configurado en S/{saldo_ingresado}.\n\n¿Cómo completamos los datos de esta foto?\n✍️ Escribe **'manual'** o **descríbelo todo aquí**.")
        except ValueError:
            enviar_mensaje(chat_id, "Formato incorrecto. Por favor envía solo números (ej. 1500.00).")
        return {"status": "ok"}

    # Bloque: Bifurcación
    if state.get("step") == "elegir_metodo":
        if text.lower() == "manual":
            state["step"] = "pedir_tipo"
            enviar_mensaje(chat_id, "🔹 **Modo Manual: Paso 1/4**\n¿Qué tipo de operación es? (ej. Compra, DeudaXCobrar, Deuda Cobrada)")
        else:
            state["contexto_texto"] = text
            procesar_imagen_y_confirmar(chat_id)
        return {"status": "ok"}

    # Bloque: Secuencia Manual
    if state.get("step") == "pedir_tipo":
        state["contexto_manual"]["tipo"] = text
        state["step"] = "pedir_motivo"
        enviar_mensaje(chat_id, "🔹 **Paso 2/4**\n¿Cuál es el Motivo? (ej. Página Web, Integración)")
        return {"status": "ok"}

    if state.get("step") == "pedir_motivo":
        state["contexto_manual"]["motivo"] = text
        state["step"] = "pedir_acreedor"
        enviar_mensaje(chat_id, "🔹 **Paso 3/4**\n¿Quién es el Acreedor? (Escribe el nombre o 'No Aplica')")
        return {"status": "ok"}

    if state.get("step") == "pedir_acreedor":
        state["contexto_manual"]["acreedor"] = text
        state["step"] = "pedir_deudor"
        enviar_mensaje(chat_id, "🔹 **Paso 4/4**\n¿Quién es el Deudor? (Escribe el nombre o 'No Aplica')")
        return {"status": "ok"}

    if state.get("step") == "pedir_deudor":
        state["contexto_manual"]["deudor"] = text
        procesar_imagen_y_confirmar(chat_id)
        return {"status": "ok"}

    # Bloque: Guardado Final
    if state.get("step") == "confirmar":
        if text in ["1", "2"]:
            try:
                codigo_asignado = guardar_en_sheets(state["datos_procesados"], state["saldo_previo"])
                
                if text == "1":
                    enviar_mensaje(chat_id, f"✅ ¡Operación registrada exitosamente bajo el código **{codigo_asignado}**!\n📥 Envía otra foto para continuar.")
                
                elif text == "2":
                    enviar_mensaje(chat_id, f"✅ Operación **{codigo_asignado}** registrada. Generando PDF...")
                    
                    nombre_pdf = f"comprobante_{codigo_asignado}.pdf"
                    datos_pdf = state["datos_procesados"]
                    # Asegurar que código esté inyectado para el PDF
                    datos_pdf["codigo"] = codigo_asignado 
                    
                    generar_comprobante_pdf(datos_pdf, nombre_pdf)
                    
                    with open(nombre_pdf, 'rb') as archivo:
                        requests.post(
                            f"{TELEGRAM_API_URL}/sendDocument",
                            data={"chat_id": chat_id, "caption": f"📄 Respaldo de Tesorería - {codigo_asignado}"},
                            files={"document": archivo}
                        )
                    if os.path.exists(nombre_pdf):
                        os.remove(nombre_pdf)

            except Exception as e:
                traceback.print_exc()
                enviar_mensaje(chat_id, "⚠️ Error al guardar en Sheets.")
            finally:
                user_states.pop(chat_id, None)
        else:
            enviar_mensaje(chat_id, "Responde 1 para guardar, 2 para guardar+PDF, o /cancelar.")
        
        return {"status": "ok"}

@app.on_event("shutdown")
def aviso_de_hibernacion():
    # Si nadie estaba a mitad de un trámite, Toribio se duerme en silencio sin molestar a nadie.
    if not user_states:
        return 

    mensaje_toribio = (
        "¡Muuu! 🐮💤\n\n"
        "El prado se quedó muy calladito y me dio sueñito, así que me voy a tomar una siesta. \n\n"
        "Como mi memoria es cortita, acabo de olvidar el recibo que estábamos revisando. 🌿 "
        "Cuando me necesites, vuelve a enviarme la foto, pero dame unos 50 segunditos para "
        "desperezarme bien antes de responderte. ¡Nos vemos lueguito!"
    )
    
    # Toribio le avisa automáticamente a los usuarios que dejó "en espera"
    for chat_id in list(user_states.keys()):
        try:
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": mensaje_toribio}
            )
        except Exception as e:
            print(f"Error al avisar de la siesta al chat {chat_id}: {e}")
