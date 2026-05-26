import os
import json
import base64
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE GROQ ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("🚨 ERROR: Falta GROQ_API_KEY en el archivo .env")

# Cliente de OpenAI apuntando a Groq
llm_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "cred.json"
SHEET_NAME = "Gastos"

def get_sheets_client():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    return gspread.authorize(creds)

def extraer_datos_recibo_llm(image_bytes: bytes) -> dict:
    """Envía la imagen a Groq y devuelve un JSON estructurado con los datos del recibo."""
    imagen_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Prompt optimizado para extraer RUC y clasificar conceptualmente el gasto
    prompt = """
    Analiza este recibo/factura y extrae los siguientes datos en un objeto JSON estricto:
    {
        "proveedor": "Nombre principal de la tienda o establecimiento",
        "ruc": "Número de RUC del proveedor (11 dígitos. Si no se detecta o no aplica, escribe 'No detectado')",
        "monto": "Monto total final a pagar (solo el número con dos decimales, ignora subtotales)",
        "fecha": "Fecha de la compra en formato DD/MM/YYYY",
        "categoria_gasto": "Clasifica la compra en una palabra: Comida, Materiales, Movilidad, Merchandising, Otros"
    }
    Si no encuentras algún dato, escribe "No detectado".
    No agregues texto adicional, solo devuelve el JSON.
    """

    try:
        response = llm_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct", # Modelo de producción oficial y activo en Groq
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_base64}"}}
                    ],
                }
            ],
            response_format={"type": "json_object"}
        )
        
        # Extraemos y convertimos la respuesta a un diccionario de Python
        datos = json.loads(response.choices[0].message.content)
        return datos

    except Exception as e:
        print(f"Error en LLM: {e}")
        return {"proveedor": "Error", "ruc": "Error", "monto": "Error", "fecha": "Error", "categoria_gasto": "Error"}

def guardar_en_sheets(datos: dict):
    """Calcula el ID autoincremental y guarda la fila en Google Sheets en el orden especificado."""
    sheets_client = get_sheets_client()
    sheet = sheets_client.open(SHEET_NAME).sheet1
    
    # 1. Calcular el ID Autoincremental dinámicamente basado en las filas existentes
    todas_las_filas = sheet.get_all_values()
    # Si solo están las cabeceras (1 fila), len() será 1, por lo que el próximo ID será 1.
    id_autoincremental = len(todas_las_filas)
    
    datos["id"] = id_autoincremental
    
    # ID | Fecha Registro | Comprador | RUC | Proveedor | Proyecto/Actividad | Categoría Gasto | Monto | Fecha Comprobante | Estado Reembolso
    fila = [
        id_autoincremental,
        datos["fecha_registro"],
        datos["comprador"],
        datos["ruc"],
        datos["proveedor"],
        datos["proyecto"],
        datos["categoria_gasto"],
        datos["monto"],
        datos["fecha"],
        datos["estado_reembolso"]
    ]
    sheet.append_row(fila)
    return id_autoincremental