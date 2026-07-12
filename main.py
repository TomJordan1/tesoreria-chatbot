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
if not TELEGRAM_TOKEN:
    raise ValueError("🚨 ERROR: Falta TELEGRAM_TOKEN en el archivo .env")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}

@app.get("/")
def home():
    return {"status": "Servidor funcionando correctamente"}

def enviar_mensaje(chat_id, texto):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML"})

def mostrar_resumen_y_opciones(chat_id):
    """Muestra el resumen final con la opción de editar restaurada."""
    state = user_states.get(chat_id)
    if not state: return
    d = state["datos_procesados"]
    resumen = (
        f"🧾 <b>¡Acabé de revisarlo! Aquí tienes el resumen:</b>\n\n"
        f"📅 <b>Fecha:</b> {d.get('fecha')}\n"
        f"🏷️ <b>Concepto:</b> {d.get('concepto')}\n"
        f"🔄 <b>Tipo:</b> {d.get('tipo')} ({d.get('ing_eg')})\n"
        f"📌 <b>Motivo:</b> {d.get('motivo')}\n"
        f"👤 <b>Acreedor:</b> {d.get('acreedor')}\n"
        f"👤 <b>Deudor:</b> {d.get('deudor')}\n"
        f"⚖️ <b>Estado:</b> {d.get('estado')}\n"
        f"💰 <b>Monto:</b> S/ {d.get('monto')}\n\n"
        f"¿Qué te parece? ¿Lo guardamos en mi registro?\n"
        f"1) Sí, guardar en la base de datos\n"
        f"2) Guardar y generarme un PDF\n"
        f"3) Editar algunos datos\n"
        f"O envía /cancelar si nos equivocamos"
    )
    enviar_mensaje(chat_id, resumen)

def procesar_imagen_y_confirmar(chat_id):
    state = user_states.get(chat_id)
    # Seguro por si el usuario canceló mientras la tarea entraba a segundo plano
    if not state: 
        return 
        
    enviar_mensaje(chat_id, "🐂 ¡Muuu! Estoy mirando tu comprobante con mis ojitos de torito y cruzándolo con lo que me contaste. Dame un segundito...")
    
    try:
        file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={state['file_id']}").json()
        file_path = file_info["result"]["file_path"]
        image_bytes = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}").content

        contexto = state.get("contexto_texto", "")
        if not contexto:
            c_man = state.get("contexto_manual", {})
            contexto = f"Tipo: {c_man.get('tipo', '')}, Motivo: {c_man.get('motivo', '')}, Acreedor: {c_man.get('acreedor', '')}, Deudor: {c_man.get('deudor', '')}"

        datos_ia = extraer_datos_recibo_llm(image_bytes, contexto)

        if "error" not in datos_ia:
            state["step"] = "confirmar"
            state["datos_procesados"] = datos_ia
            mostrar_resumen_y_opciones(chat_id)
        else:
            enviar_mensaje(chat_id, "🐂 ¡Uy! Mis pezuñas resbalaron y no pude leer bien la imagen. ¿Podemos intentarlo de nuevo?")
            user_states.pop(chat_id, None)

    except Exception as e:
        traceback.print_exc()
        enviar_mensaje(chat_id, "🐂 ¡Muuu! Me enredé un poco con los cables del prado. Ocurrió un problemita interno.")
        user_states.pop(chat_id, None)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}

    message = data["message"]
    chat_id = str(message["chat"]["id"])

    # --- 1. RECEPCIÓN DE IMAGEN ---
    if "photo" in message:
        user_states[chat_id] = {
            "file_id": message["photo"][-1]["file_id"],
            "caption": message.get("caption", ""),
            "contexto_manual": {}
        }
        
        saldo_actual = obtener_saldo_actual()
        if saldo_actual is None:
            user_states[chat_id]["step"] = "pedir_saldo_base"
            enviar_mensaje(chat_id, "¡Hola! 🤔 Veo que mi pastizal está limpiecito y es el primer registro en la base de datos.\nPara poder calcular bien todo, por favor dime, ¿cuál es el <b>Saldo Base / Inicial</b> en caja? (ej. 1500.50)")
            return {"status": "ok"}
        
        user_states[chat_id]["saldo_previo"] = saldo_actual

        if user_states[chat_id]["caption"]:
            user_states[chat_id]["contexto_texto"] = user_states[chat_id]["caption"]
            user_states[chat_id]["step"] = "esperar_lectura"
            enviar_mensaje(chat_id, "🐂 ¡Muuu! Recibí la foto y tu explicación al mismo tiempo.\n\nPara que no me atragante procesando todo de golpe, escribe <b>'1'</b> (o la palabra que quieras) para empezar a leerlo con mis ojitos y mostrarte el resumen.")
        else:
            user_states[chat_id]["step"] = "elegir_metodo"
            enviar_mensaje(chat_id, "¡Recibido! Tengo la fotito en mis pezuñas. ¿Cómo me cuentas el resto de los detalles?\n\n✍️ Escribe <b>'manual'</b> para que te pregunte paso a paso.\n🗣️ O si prefieres, escríbeme <b>toda la historia junta aquí</b>.")
        return {"status": "ok"}

    # --- 2. MANEJO DE TEXTO ---
    state = user_states.get(chat_id)
    if not state:
        enviar_mensaje(chat_id, "🟢¡Holiii! Soy Toribio, tu torito verde de confianza. Envíame la foto de tu comprobante o captura para empezar a masticar esos números.\n\n💡 <i>Tip: Si me pones toda la explicación en la leyenda de la foto, me ahorro el trabajo de preguntarte y vamos más rápido.</i>")
        return {"status": "ok"}

    text = message.get("text", "").strip()

    if text.lower() == "/cancelar":
        user_states.pop(chat_id, None)
        enviar_mensaje(chat_id, "¡Entendido! Tiramos esto al pasto. Envíame otra foto cuando quieras empezar de nuevo.")
        return {"status": "ok"}

    if state.get("step") == "pedir_saldo_base":
        try:
            state["saldo_previo"] = float(text.replace(",", ""))
            if state["caption"]:
                state["contexto_texto"] = state["caption"]
                state["step"] = "esperar_lectura"
                enviar_mensaje(chat_id, "¡Excelente! He guardado nuestro saldo inicial.\n\n🐂 ¡Muuu! Para que no me atragante procesando todo de golpe, escribe <b>'1'</b> para empezar a leer el recibo con mis ojitos y mostrarte el resumen.")
            else:
                state["step"] = "elegir_metodo"
                enviar_mensaje(chat_id, "¡Excelente! He guardado nuestro saldo inicial en mi libreta.\n\nAhora sí, sobre la foto: ¿cómo completamos los datos que faltan?\n✍️ Escribe <b>'manual'</b> o <b>cuéntamelo todo de golpe aquí</b>.")
        except ValueError:
            enviar_mensaje(chat_id, "¡Muuu! Eso no parece un número de pasto válido. Escríbelo solo con números y punto decimal, por favor (ej. 1500.50).")
        return {"status": "ok"}

    if state.get("step") == "esperar_lectura":
        procesar_imagen_y_confirmar(chat_id)
        return {"status": "ok"}

    if state.get("step") == "elegir_metodo":
        if text.lower() == "manual":
            state["step"] = "pedir_tipo"
            enviar_mensaje(chat_id, "<b>Paso 1 de 4:</b>\n¿Qué tipo de operación es esta? (ej. Compra, DeudaXCobrar, Deuda Cobrada)")
        else:
            state["contexto_texto"] = text
            state["step"] = "esperar_lectura"
            enviar_mensaje(chat_id, "¡Anotado! 🐂\nAhora escribe <b>'1'</b> para que empiece a cruzar esta historia con la foto y te arme el resumen.")
        return {"status": "ok"}

    if state.get("step") in ["pedir_tipo", "pedir_motivo", "pedir_acreedor", "pedir_deudor"]:
        pasos = {"pedir_tipo": ("tipo", "pedir_motivo", "<b>Paso 2 de 4:</b>\n¿Cuál es el Motivo? (ej. Página Web, Integración)"),
                 "pedir_motivo": ("motivo", "pedir_acreedor", "<b>Paso 3 de 4:</b>\n¿Quién es el Acreedor? (Escribe el nombre o pon 'No Aplica')"),
                 "pedir_acreedor": ("acreedor", "pedir_deudor", "<b>Paso 4 de 4:</b>\nY por último, ¿quién es el Deudor? (Escribe el nombre o 'No Aplica')")}
        
        if state["step"] == "pedir_deudor":
            state["contexto_manual"]["deudor"] = text
            state["step"] = "esperar_lectura"
            enviar_mensaje(chat_id, "¡Anotado! 🐂\nAhora escribe <b>'1'</b> para que empiece a cruzar esta historia con la foto y te arme el resumen.")
        else:
            clave, sig_paso, msj = pasos[state["step"]]
            state["contexto_manual"][clave] = text
            state["step"] = sig_paso
            enviar_mensaje(chat_id, msj)
        return {"status": "ok"}

    # Bloque: Restauración del Modo de Edición
    if state.get("step") == "confirmar":
        if text in ["1", "2"]:
            nombre_pdf = None
            nombre_img_temporal = None
            try:
                datos_finales = guardar_en_sheets(state["datos_procesados"], state["saldo_previo"])
                codigo_asignado = datos_finales["codigo"]
                
                if text == "1":
                    enviar_mensaje(chat_id, f"¡Muuucho éxito! Operación guardada en Sheets bajo el código <b>{codigo_asignado}</b>.\n📥 ¡Mándame otra fotito para seguir!")
                elif text == "2":
                    enviar_mensaje(chat_id, f"¡Muuu! Operación <b>{codigo_asignado}</b> bien guardadita. Estoy armando tu PDF con mis cuernos...")
                    nombre_pdf = f"comprobante_{codigo_asignado}.pdf"
                    nombre_img_temporal = f"img_temp_{codigo_asignado}.jpg"
                    
                    file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={state['file_id']}").json()
                    file_path = file_info["result"]["file_path"]
                    image_bytes = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}").content
                    
                    with open(nombre_img_temporal, "wb") as f_img:
                        f_img.write(image_bytes)

                    generar_comprobante_pdf(datos_finales, nombre_pdf, nombre_img_temporal)
                    
                    with open(nombre_pdf, 'rb') as archivo:
                        requests.post(
                            f"{TELEGRAM_API_URL}/sendDocument",
                            data={"chat_id": chat_id, "caption": f"📄 Respaldo de tu tesorería - Código: {codigo_asignado}"},
                            files={"document": archivo}
                        )

            except Exception as e:
                traceback.print_exc()
                enviar_mensaje(chat_id, "¡Ay, qué torito tan despistado soy! Ocurrió un problema tratando de anotar esto en el Excel. Habla con el área de TIC.")
            finally:
                if nombre_pdf and os.path.exists(nombre_pdf):
                    os.remove(nombre_pdf)
                if nombre_img_temporal and os.path.exists(nombre_img_temporal):
                    os.remove(nombre_img_temporal)
                user_states.pop(chat_id, None)
                
        elif text in ["3", "editar"]:
            state["step"] = "editar"
            respuesta = (
                "✏️ <b>Modo edición manual (Mantén las '?' como separador, por favor):</b>\n\n"
                "<code>Fecha ? Concepto ? Tipo ? Ing/Eg ? Motivo ? Acreedor ? Deudor ? Estado ? Monto</code>\n\n"
                "<i>Copia y corrige este ejemplo:</i> \n<code>19/10/2025 ? Pago Hosting ? Compra ? Egreso ? Página Web ? No Aplica ? No Aplica ? Pagado ? 46.00</code>"
            )
            enviar_mensaje(chat_id, respuesta)
        else:
            enviar_mensaje(chat_id, "Por favor responde con un numerito:\n1) Guardar\n2) Guardar y crear PDF\n3) Editar\nO escribe /cancelar si ya no quieres guardarlo.")
        return {"status": "ok"}

    # Procesar datos editados
    if state.get("step") == "editar":
        partes = [p.strip() for p in text.split("?")]
        if len(partes) != 9 or not all(partes):
            enviar_mensaje(chat_id, "¡Ups! Te comiste un poco de pasto. Asegúrate de incluir todos los 9 campos separados por el símbolo '?'.")
            return {"status": "ok"}

        d = state["datos_procesados"]
        d["fecha"], d["concepto"], d["tipo"], d["ing_eg"], d["motivo"], d["acreedor"], d["deudor"], d["estado"], d["monto"] = partes
        
        state["step"] = "confirmar"
        enviar_mensaje(chat_id, "¡Muuu! Datos masticados y corregidos.")
        mostrar_resumen_y_opciones(chat_id)
        return {"status": "ok"}

@app.on_event("shutdown")
def aviso_de_hibernacion():
    if not user_states:
        return 

    mensaje_toribio = (
        "¡Muuu! 💤\n\n"
        "El prado se quedó muy calladito y me dio sueñito, así que me voy a tomar una siesta. \n\n"
        "Como mi memoria es cortita, acabo de olvidar el recibo que estábamos revisando. 🌿 "
        "Cuando me necesites, vuelve a enviarme la foto, pero dame unos 50 segunditos para "
        "desperezarme bien antes de responderte. ¡Nos vemos lueguito!"
    )
    
    for chat_id in list(user_states.keys()):
        try:
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": mensaje_toribio}
            )
        except Exception as e:
            print(f"Error al avisar de la siesta al chat {chat_id}: {e}")
