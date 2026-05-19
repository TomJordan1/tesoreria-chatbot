import os
import re
import requests
import traceback
from datetime import datetime
from fastapi import FastAPI, Request
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI()

# TOKENS a usar
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("🚨 ERROR: Falta TELEGRAM_TOKEN en el archivo .env")
if not OCR_API_KEY:
    raise ValueError("🚨 ERROR: Falta OCR_API_KEY en el archivo .env")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Usamos los Scopes modernos de Google Auth
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "cred.json" 
SHEET_NAME = "Gastos" 

# SISTEMA DE ESTADOS (Memoria temporal para el MVP)
# Estructura: { chat_id: {"step": "confirmar" | "editar", "datos": {...}} }
user_states = {}

def get_sheets_client():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    return gspread.authorize(creds)

def enviar_mensaje_telegram(chat_id: int, texto: str):
    """Función auxiliar para no repetir código de envío de mensajes."""
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": texto}
    )

def guardar_en_sheets(proveedor: str, monto: str, fecha_comprobante: str):
    """Guarda los datos finales en Google Sheets con la estructura solicitada."""
    sheets_client = get_sheets_client()
    sheet = sheets_client.open(SHEET_NAME).sheet1
    
    fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Columnas: Fecha_registro | Proveedor | Monto | Fecha_comprobante | Tipo
    sheet.append_row([fecha_registro, proveedor, monto, fecha_comprobante, "Recibo escaneado"])

@app.get("/")
def home():
    return {"status": "Servidor funcionando correctamente"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" not in data:
        return {"status": "ok"}
        
    message = data["message"]
    chat_id = message["chat"]["id"]
    text_message = message.get("text", "").strip()
    
    # 1. SI EL USUARIO ENVÍA UNA FOTO (Inicia o reinicia el flujo)
    if "photo" in message:
        enviar_mensaje_telegram(chat_id, "📸 Imagen recibida. Procesando datos...")

        try:
            # Obtener imagen de Telegram
            file_id = message["photo"][-1]["file_id"]
            file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            
            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
            image_bytes = requests.get(image_url).content
            
            # Enviar a OCR.space
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
            
            # Validar y extraer datos
            if not ocr_response.get("IsErroredOnProcessing") and ocr_response.get("ParsedResults"):
                texto_completo = ocr_response["ParsedResults"][0]["ParsedText"]
                
                # Extracción de Monto
                monto_match = re.search(r'\d+\.\d{2}', texto_completo)
                monto = monto_match.group(0) if monto_match else "No detectado"
                
                # Extracción de Fecha (formatos comunes DD/MM/YYYY, DD-MM-YYYY, etc.)
                fecha_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', texto_completo)
                fecha = fecha_match.group(0) if fecha_match else "No detectado"
                
                # Extracción de Proveedor (Primera línea)
                lineas_texto = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
                proveedor = lineas_texto[0] if lineas_texto else "Desconocido"
                
                # Guardar en el estado del usuario para validación
                user_states[chat_id] = {
                    "step": "confirmar",
                    "datos": {
                        "proveedor": proveedor,
                        "monto": monto,
                        "fecha": fecha
                    }
                }
                
                # Mostrar datos para validación
                respuesta = (
                    "🧾 *Datos detectados:*\n"
                    f"🏢 Proveedor: {proveedor}\n"
                    f"💰 Monto: S/ {monto}\n"
                    f"📅 Fecha: {fecha}\n\n"
                    "¿Es correcto?\n"
                    "1) Sí\n"
                    "2) Editar"
                )
            else:
                error_msg = ocr_response.get("ErrorMessage", ["Error desconocido en OCR"])[0]
                respuesta = f"❌ No pude detectar texto. Detalle: {error_msg}"

        except Exception as e:
            error_trace = traceback.format_exc()
            print("\n--- ERROR DETECTADO ---")
            print(error_trace)
            print("-----------------------\n")
            respuesta = "⚠️ Ocurrió un error procesando la imagen. Revisa la terminal."
            
        enviar_mensaje_telegram(chat_id, respuesta)
        return {"status": "ok"}

    # 2. SI EL USUARIO ENVÍA TEXTO (Validación, Edición o Mensaje Default)
    estado_actual = user_states.get(chat_id, {}).get("step")

    if estado_actual == "confirmar":
        if text_message == "1":
            try:
                datos = user_states[chat_id]["datos"]
                guardar_en_sheets(datos["proveedor"], datos["monto"], datos["fecha"])
                enviar_mensaje_telegram(chat_id, "✅ ¡Gasto registrado exitosamente en Google Sheets!")
                del user_states[chat_id]  # Limpiar estado
            except Exception as e:
                print(traceback.format_exc())
                enviar_mensaje_telegram(chat_id, "⚠️ Error al guardar en Sheets. Revisa la terminal.")
        
        elif text_message == "2":
            user_states[chat_id]["step"] = "editar"
            enviar_mensaje_telegram(
                chat_id, 
                "✍️ Por favor, envía los datos corregidos con este formato exacto:\n\n"
                "Proveedor | Monto | Fecha"
            )
        else:
            enviar_mensaje_telegram(chat_id, "Por favor responde con '1' para confirmar o '2' para editar.")

    elif estado_actual == "editar":
        partes = [p.strip() for p in text_message.split("|")]
        
        if len(partes) == 3:
            proveedor_edit = partes[0] if partes[0] else "No detectado"
            monto_edit = partes[1] if partes[1] else "No detectado"
            fecha_edit = partes[2] if partes[2] else "No detectado"
            
            try:
                guardar_en_sheets(proveedor_edit, monto_edit, fecha_edit)
                enviar_mensaje_telegram(chat_id, "✅ ¡Gasto editado y registrado exitosamente!")
                del user_states[chat_id]  # Limpiar estado
            except Exception as e:
                print(traceback.format_exc())
                enviar_mensaje_telegram(chat_id, "⚠️ Error al guardar en Sheets. Revisa la terminal.")
        else:
            enviar_mensaje_telegram(
                chat_id, 
                "❌ Formato incorrecto. Recuerda usar el formato (separado por barras verticales):\n"
                "Proveedor | Monto | Fecha"
            )

    else:
        # Estado por defecto: Esperando imagen
        enviar_mensaje_telegram(
            chat_id, 
            "👋 ¡Hola! Por favor, envíame una foto de un recibo o factura para registrar el gasto."
        )

    return {"status": "ok"}