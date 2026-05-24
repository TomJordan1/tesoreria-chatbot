import os
import re
import requests
import traceback
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar nuestros módulos
from servicios import extraer_datos_recibo_llm, guardar_en_sheets
from generador_pdf import generar_comprobante_pdf

app = FastAPI()

# TOKENS
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("🚨 ERROR: Falta TELEGRAM_TOKEN en el archivo .env")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Hora de Perú (UTC-5)
ZONA_HORARIA_PERU = timezone(timedelta(hours=-5))

# Estados de la conversación por usuario
user_states = {}

@app.get("/")
def home():
    return {"status": "Servidor funcionando correctamente"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"status": "ok"}

    message = data["message"]
    chat_id = str(message["chat"]["id"])

    # --- SI EL USUARIO ENVÍA UNA FOTO ---
    if "photo" in message:
        user_states.pop(chat_id, None)

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": "📸 Imagen recibida. La IA está procesando el comprobante..."}
        )

        try:
            # 1. Obtener imagen de Telegram
            file_id = message["photo"][-1]["file_id"]
            file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]

            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
            image_bytes = requests.get(image_url).content

            # 2. Extraer Comprador y Proyecto desde Telegram
            comprador = message.get("from", {}).get("first_name", "Desconocido")
            proyecto = message.get("caption", "General") # La leyenda de la foto representará el Proyecto/Actividad

            # 3. Mandar a Groq (LLM)
            datos_ia = extraer_datos_recibo_llm(image_bytes)

            if datos_ia["monto"] != "Error":
                # 4. Consolidar datos en el estado temporal
                user_states[chat_id] = {
                    "step": "confirmar",
                    "datos": {
                        "fecha_registro": datetime.now(ZONA_HORARIA_PERU).strftime("%d/%m/%Y %H:%M:%S"),
                        "comprador": comprador,
                        "ruc": datos_ia.get("ruc", "No detectado"),
                        "proveedor": datos_ia.get("proveedor", "No detectado"),
                        "proyecto": proyecto,
                        "categoria_gasto": datos_ia.get("categoria_gasto", "Otros"),
                        "monto": datos_ia.get("monto", "No detectado"),
                        "fecha": datos_ia.get("fecha", "No detectado"),
                        "estado_reembolso": "Pendiente"
                    }
                }

                d = user_states[chat_id]["datos"]
                respuesta = (
                    f"🧾 **Comprobante Analizado:**\n\n"
                    f"👤 **Comprador:** {d['comprador']}\n"
                    f"🆔 **RUC:** {d['ruc']}\n"
                    f"🏢 **Proveedor:** {d['proveedor']}\n"
                    f"📂 **Proyecto/Actividad:** {d['proyecto']}\n"
                    f"🏷️ **Categoría Gasto:** {d['categoria_gasto']}\n"
                    f"💰 **Monto:** S/ {d['monto']}\n"
                    f"📅 **Fecha Emisión:** {d['fecha']}\n\n"
                    f"¿Los datos son correctos?\n"
                    f"1) Solo guardar en Sheets\n"
                    f"2) Guardar en Sheets y generar PDF\n"
                    f"3) Editar datos"
                )
            else:
                respuesta = "❌ Ocurrió un error al analizar la imagen con el modelo de visión."

        except Exception as e:
            traceback.print_exc()
            respuesta = "⚠️ Ocurrió un error interno al procesar la imagen."

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": respuesta, "parse_mode": "Markdown"}
        )
        return {"status": "ok"}

    # --- MANEJO DE MENSAJES DE TEXTO ---
    state = user_states.get(chat_id)

    if not state:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": chat_id, 
                "text": "👋 ¡Hola! Envíame la foto de un recibo o factura.\n\n*💡 Consejo:* Escribe el nombre del proyecto en la leyenda (caption) de la foto para asignarlo automáticamente.",
                "parse_mode": "Markdown"
            }
        )
        return {"status": "ok"}

    # Estado: Confirmar
    if state["step"] == "confirmar":
        text = message.get("text", "").strip().lower()

        # Opción 1: Solo guardar en Sheets
        if text in ["1", "solo guardar", "guardar", "sí", "si"]:
            try:
                id_asignado = guardar_en_sheets(state["datos"])
                d = state["datos"]
                respuesta = (
                    f"✅ ¡Gasto registrado en Sheets con el ID #{id_asignado}!\n"
                    f"*(No se generó PDF por elección del usuario)*\n\n"
                    f"📥 Envía otra foto para continuar."
                )
            except Exception as e:
                traceback.print_exc()
                respuesta = "⚠️ Error de conexión con Google Sheets."
            finally:
                user_states.pop(chat_id, None)

            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage", 
                json={"chat_id": chat_id, "text": respuesta, "parse_mode": "Markdown"}
            )
            return {"status": "ok"}

        # Opción 2: Guardar en Sheets y generar PDF
        elif text in ["2", "pdf", "guardar y pdf"]:
            try:
                id_asignado = guardar_en_sheets(state["datos"])
                d = state["datos"]
                
                requests.post(
                    f"{TELEGRAM_API_URL}/sendMessage",
                    json={"chat_id": chat_id, "text": f"✅ Gasto registrado (ID #{id_asignado}). Generando PDF..."}
                )

                # Compilación del PDF usando el módulo independiente generador_pdf.py
                nombre_pdf_local = f"comprobante_{id_asignado}.pdf"
                try:
                    generar_comprobante_pdf(d, nombre_pdf_local)
                    
                    with open(nombre_pdf_local, 'rb') as archivo_adjunto:
                        requests.post(
                            f"{TELEGRAM_API_URL}/sendDocument",
                            data={"chat_id": chat_id, "caption": f"📄 Comprobante de Gasto Interno - ID #{id_asignado}\n📥 Envía otra foto para continuar."},
                            files={"document": archivo_adjunto}
                        )
                except Exception as pdf_error:
                    print(f"Error generando o enviando PDF: {pdf_error}")
                    requests.post(
                        f"{TELEGRAM_API_URL}/sendMessage",
                        json={"chat_id": chat_id, "text": "⚠️ El gasto se guardó, pero ocurrió un problema al compilar el PDF."}
                    )
                finally:
                    if os.path.exists(nombre_pdf_local):
                        os.remove(nombre_pdf_local)

            except Exception as e:
                traceback.print_exc()
                requests.post(
                    f"{TELEGRAM_API_URL}/sendMessage", 
                    json={"chat_id": chat_id, "text": "⚠️ Error de conexión con Google Sheets."}
                )
            finally:
                user_states.pop(chat_id, None)

            return {"status": "ok"}

        # Opción 3: Entrar al modo edición
        elif text in ["3", "editar"]:
            state["step"] = "editar"
            respuesta = (
                "✏️ **Modo edición:**\n"
                "Modifica los valores manteniendo las 5 barras verticales (`|`):\n\n"
                "`Proveedor | RUC | Monto | Fecha | Categoría Gasto | Proyecto`\n\n"
                "Ejemplo:\n"
                "`Librería UNI | 20123456789 | 35.50 | 24/05/2026 | Materiales | Talleres Cono Norte`\n\n"
                "O envía /cancelar para anular."
            )
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": respuesta, "parse_mode": "Markdown"}
            )
            return {"status": "ok"}

        else:
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Por favor responde:\n1) Solo guardar\n2) Guardar y crear PDF\n3) Editar"}
            )
            return {"status": "ok"}


    # --- ESTADO: EDITAR ---
    if state["step"] == "editar":
        text = message.get("text", "").strip()
        if text.lower() == "/cancelar":
            user_states.pop(chat_id, None)
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "❌ Registro cancelado. Puedes enviar otra foto."}
            )
            return {"status": "ok"}

        partes = [p.strip() for p in text.split("|")]
        if len(partes) != 6 or not all(partes):
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "⚠️ Estructura incorrecta. Asegúrate de proveer los 6 campos separados por '|'."}
            )
            return {"status": "ok"}

        proveedor, ruc, monto_str, fecha_str, categoria_gasto, proyecto = partes

        if not re.match(r'^\d+(\.\d{2})?$', monto_str):
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Formato de monto inválido (ejemplo correcto: 120.00). Intenta de nuevo."}
            )
            return {"status": "ok"}

        # Aplicar correcciones manuales hechas por el usuario al estado temporal
        d = state["datos"]
        d["proveedor"] = proveedor
        d["ruc"] = ruc
        d["monto"] = monto_str
        d["fecha"] = fecha_str
        d["categoria_gasto"] = categoria_gasto
        d["proyecto"] = proyecto

        # Devolver al estado confirmar para que el usuario elija si quiere PDF o no con los nuevos cambios
        state["step"] = "confirmar"

        respuesta = (
            f"📝 **Datos corregidos exitosamente.**\n"
            f"¿Qué deseas hacer ahora con este registro?\n\n"
            f"👤 **Comprador:** {d['comprador']}\n"
            f"🆔 **RUC:** {d['ruc']}\n"
            f"🏢 **Proveedor:** {d['proveedor']}\n"
            f"📂 **Proyecto:** {d['proyecto']}\n"
            f"🏷️ **Categoría:** {d['categoria_gasto']}\n"
            f"💰 **Monto:** S/ {d['monto']}\n"
            f"📅 **Fecha:** {d['fecha']}\n\n"
            f"1) Solo guardar en Sheets\n"
            f"2) Guardar en Sheets y generar PDF\n"
            f"3) Volver a editar"
        )

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": respuesta, "parse_mode": "Markdown"}
        )
        return {"status": "ok"}