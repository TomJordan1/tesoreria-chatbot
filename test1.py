import os
import re
import requests
import traceback
from datetime import datetime
from fastapi import FastAPI, Request
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI()

# TOKENS
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("🚨 ERROR: Falta TELEGRAM_TOKEN en el archivo .env")
if not OCR_API_KEY:
    raise ValueError("🚨 ERROR: Falta OCR_API_KEY en el archivo .env")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Google Sheets
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "cred.json"
SHEET_NAME = "Gastos"

# Estados de la conversación por usuario
user_states = {}


def get_sheets_client():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    return gspread.authorize(creds)


def extraer_fecha(texto: str) -> str:
    """Busca una fecha en texto con formato español dd/mm/aaaa, dd-mm-aaaa, dd de mes de aaaa, etc."""
    patrones = [
        r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b',                         # 01/01/2023 o 01-01-2023
        r'\b(\d{1,2})\s+de\s+([a-zA-ZñÑ]+)\s+de\s+(\d{4})\b',                # 01 de enero de 2023
        r'\b(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})\b',                         # 2023/01/01 (menos común)
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            # Normalizar a formato dd/mm/aaaa
            if patron == patrones[0]:
                return f"{match.group(1).zfill(2)}/{match.group(2).zfill(2)}/{match.group(3)}"
            elif patron == patrones[1]:
                dia, mes_texto, anio = match.groups()
                # Convertir nombre de mes a número
                meses = {
                    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
                    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
                    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
                }
                mes_num = meses.get(mes_texto.lower(), "01")
                return f"{dia.zfill(2)}/{mes_num}/{anio}"
            elif patron == patrones[2]:
                return f"{match.group(3).zfill(2)}/{match.group(2).zfill(2)}/{match.group(1)}"
    return "No detectado"


@app.get("/")
def home():
    return {"status": "Servidor funcionando correctamente"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"status": "ok"}

    message = data["message"]
    chat_id = str(message["chat"]["id"])  # usamos str como clave en user_states

    # Si el usuario envía una foto (nuevo recibo) ignoramos cualquier estado previo
    if "photo" in message:
        # Resetear estado anterior para empezar limpio
        user_states.pop(chat_id, None)

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": "📸 Imagen recibida. Procesando datos..."}
        )

        try:
            # 1. Obtener imagen de Telegram
            file_id = message["photo"][-1]["file_id"]
            file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]

            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
            image_bytes = requests.get(image_url).content

            # 2. OCR.space
            ocr_url = "https://api.ocr.space/parse/image"
            ocr_payload = {
                'apikey': OCR_API_KEY,
                'language': 'spa',
            }

            ocr_response_raw = requests.post(
                ocr_url,
                data=ocr_payload,
                files={'file': ('recibo.jpg', image_bytes, 'image/jpeg')}
            )
            ocr_response = ocr_response_raw.json()

            # 3. Validar y extraer datos
            if not ocr_response.get("IsErroredOnProcessing") and ocr_response.get("ParsedResults"):
                texto_completo = ocr_response["ParsedResults"][0]["ParsedText"]

                monto_match = re.search(r'\d+\.\d{2}', texto_completo)
                monto = monto_match.group(0) if monto_match else "No detectado"

                fecha = extraer_fecha(texto_completo)

                lineas_texto = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
                proveedor = lineas_texto[0] if lineas_texto else "Desconocido"

                # Guardar datos en estado del usuario
                user_states[chat_id] = {
                    "step": "confirmar",
                    "datos": {
                        "proveedor": proveedor,
                        "monto": monto,
                        "fecha": fecha,
                        "fecha_registro": datetime.utcnow().isoformat(),  # se usará al guardar
                        "tipo": "Recibo escaneado"
                    }
                }

                # Mostrar datos y pedir confirmación
                respuesta = (
                    f"🧾 Datos detectados:\n"
                    f"Proveedor: {proveedor}\n"
                    f"Monto: S/ {monto}\n"
                    f"Fecha: {fecha}\n\n"
                    f"¿Es correcto?\n"
                    f"1) Sí\n"
                    f"2) Editar"
                )
            else:
                error_msg = ocr_response.get("ErrorMessage", ["Error desconocido en OCR"])[0]
                respuesta = f"❌ No pude detectar texto. Detalle: {error_msg}"

        except Exception as e:
            error_trace = traceback.format_exc()
            print("\n--- ERROR DETECTADO ---")
            print(error_trace)
            print("-----------------------\n")
            respuesta = "⚠️ Ocurrió un error. Revisa la terminal de Uvicorn en tu computadora para ver el detalle exacto."

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": respuesta}
        )
        return {"status": "ok"}

    # --- Manejo de mensajes de texto según el estado ---
    state = user_states.get(chat_id)

    # Si no hay estado, mensaje de bienvenida
    if not state:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": "👋 ¡Hola! Por favor, envíame una foto de un recibo o factura para registrar el gasto."}
        )
        return {"status": "ok"}

    # Estado: confirmar
    if state["step"] == "confirmar":
        text = message.get("text", "").strip().lower()
        if text in ["1", "sí", "si", "yes"]:
            # Guardar en Google Sheets
            try:
                sheets_client = get_sheets_client()
                sheet = sheets_client.open(SHEET_NAME).sheet1
                d = state["datos"]
                # Columnas: Fecha_registro | Proveedor | Monto | Fecha_comprobante | Tipo
                sheet.append_row([
                    d["fecha_registro"],
                    d["proveedor"],
                    d["monto"],
                    d["fecha"],
                    d["tipo"]
                ])
                respuesta = (
                    f"✅ ¡Gasto registrado exitosamente!\n"
                    f"🏢 Proveedor: {d['proveedor']}\n"
                    f"💰 Monto: S/ {d['monto']}\n"
                    f"📅 Fecha comprobante: {d['fecha']}\n"
                    f"📥 Envía otra foto para continuar."
                )
            except Exception as e:
                error_trace = traceback.format_exc()
                print("\n--- ERROR AL GUARDAR EN SHEETS ---")
                print(error_trace)
                print("-----------------------------------\n")
                respuesta = "⚠️ Error al guardar en Sheets. Revisa la terminal."
            finally:
                # Limpiar estado
                user_states.pop(chat_id, None)

            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": respuesta}
            )
            return {"status": "ok"}

        elif text in ["2", "editar"]:
            # Cambiar a modo edición
            state["step"] = "editar"
            respuesta = (
                "✏️ Modo edición:\n"
                "Envía los datos corregidos en el siguiente formato:\n\n"
                "`Proveedor | Monto | Fecha`\n\n"
                "Ejemplo: `Supermercado XYZ | 45.90 | 12/05/2023`\n\n"
                "O envía /cancelar para descartar este recibo."
            )
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": respuesta, "parse_mode": "Markdown"}
            )
            return {"status": "ok"}

        else:
            # Respuesta no reconocida
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Por favor responde:\n1) Sí\n2) Editar"}
            )
            return {"status": "ok"}

    # Estado: editar
    if state["step"] == "editar":
        text = message.get("text", "").strip()
        if text.lower() == "/cancelar":
            user_states.pop(chat_id, None)
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "❌ Registro cancelado. Envía otra foto cuando quieras."}
            )
            return {"status": "ok"}

        # Parsear formato Proveedor | Monto | Fecha
        partes = [p.strip() for p in text.split("|")]
        if len(partes) != 3 or not all(partes):
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Formato incorrecto. Usa: Proveedor | Monto | Fecha\nEjemplo: Supermercado XYZ | 45.90 | 12/05/2023"}
            )
            return {"status": "ok"}

        proveedor, monto_str, fecha_str = partes

        # Validación mínima del monto: que sea un número con decimales
        if not re.match(r'^\d+(\.\d{2})?$', monto_str):
            requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "El monto debe ser un número con dos decimales (ej. 45.90). Intenta de nuevo."}
            )
            return {"status": "ok"}

        # Actualizar los datos originales con los editados
        d = state["datos"]
        d["proveedor"] = proveedor
        d["monto"] = monto_str
        d["fecha"] = fecha_str if fecha_str.lower() != "no detectado" else "No detectado"

        # Guardar directamente después de la edición
        try:
            sheets_client = get_sheets_client()
            sheet = sheets_client.open(SHEET_NAME).sheet1
            sheet.append_row([
                d["fecha_registro"],
                d["proveedor"],
                d["monto"],
                d["fecha"],
                d["tipo"]
            ])
            respuesta = (
                f"✅ ¡Gasto registrado exitosamente (editado)!\n"
                f"🏢 Proveedor: {d['proveedor']}\n"
                f"💰 Monto: S/ {d['monto']}\n"
                f"📅 Fecha comprobante: {d['fecha']}\n"
                f"📥 Envía otra foto para continuar."
            )
        except Exception as e:
            error_trace = traceback.format_exc()
            print("\n--- ERROR AL GUARDAR EN SHEETS ---")
            print(error_trace)
            print("-----------------------------------\n")
            respuesta = "⚠️ Error al guardar en Sheets. Revisa la terminal."
        finally:
            user_states.pop(chat_id, None)

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": respuesta}
        )
        return {"status": "ok"}

    # Por si acaso, cualquier otro estado no contemplado
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": "Estado no reconocido. Envía una nueva foto para empezar."}
    )
    return {"status": "ok"}