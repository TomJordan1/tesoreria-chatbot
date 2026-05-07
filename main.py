import os
import re
import requests
import traceback
from fastapi import FastAPI, Request
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8553079256:AAHW_NUJVBMTbyde2UQ7FwzXJiSGOUin-bI")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Usamos los Scopes modernos de Google Auth
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "cred.json" 
SHEET_NAME = "Gastos" 

def get_sheets_client():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    return gspread.authorize(creds)

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
    
    if "photo" in message:
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
            
            # 2. Enviar a OCR.space
            ocr_url = "https://api.ocr.space/parse/image"
            ocr_payload = {
                'apikey': 'K88010627588957',
                'language': 'spa',
            }
            
            ocr_response_raw = requests.post(
                ocr_url, 
                data=ocr_payload, 
                files={'file': ('recibo.jpg', image_bytes, 'image/jpeg')}
            )
            
            # Forzamos la lectura como JSON
            ocr_response = ocr_response_raw.json()
            
            # 3. Validar y extraer datos
            if not ocr_response.get("IsErroredOnProcessing") and ocr_response.get("ParsedResults"):
                texto_completo = ocr_response["ParsedResults"][0]["ParsedText"]
                
                monto_match = re.search(r'\d+\.\d{2}', texto_completo)
                monto = monto_match.group(0) if monto_match else "No detectado"
                
                lineas_texto = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
                proveedor = lineas_texto[0] if lineas_texto else "Desconocido"
                
                # 4. Guardar en Google Sheets
                sheets_client = get_sheets_client()
                sheet = sheets_client.open(SHEET_NAME).sheet1
                
                sheet.append_row([proveedor, monto, "Recibo escaneado"]) 
                
                respuesta = f"✅ ¡Gasto registrado exitosamente!\n\n🏢 Proveedor: {proveedor}\n💰 Monto: S/ {monto}"
            else:
                error_msg = ocr_response.get("ErrorMessage", ["Error desconocido en OCR"])[0]
                respuesta = f"❌ No pude detectar texto. Detalle: {error_msg}"

        except Exception as e:
            # MAGIA DE DEBUGGING: Esto imprime la línea exacta del error en tu terminal
            error_trace = traceback.format_exc()
            print("\n--- ERROR DETECTADO ---")
            print(error_trace)
            print("-----------------------\n")
            respuesta = "⚠️ Ocurrió un error. Revisa la terminal de Uvicorn en tu computadora para ver el detalle exacto."
            
    else:
        respuesta = "👋 ¡Hola! Por favor, envíame una foto de un recibo o factura para registrar el gasto."

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": respuesta}
    )
    
    return {"status": "ok"}