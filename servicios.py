import os
import json
import base64
import requests
from openai import OpenAI
from datetime import datetime, timezone, timedelta
import msal

# --- CONFIGURACIÓN DE GROQ ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("🚨 ERROR: Falta GROQ_API_KEY en el archivo .env")

llm_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- CONFIGURACIÓN DE MICROSOFT GRAPH ---
MS_TENANT_ID = os.getenv("MS_TENANT_ID")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_SITE_ID = os.getenv("MS_SITE_ID")
MS_DRIVE_ID = os.getenv("MS_DRIVE_ID")
MS_ITEM_ID = os.getenv("MS_ITEM_ID")
MS_TABLE_NAME = os.getenv("MS_TABLE_NAME", "TablaFinanzas")

# Hora de Perú (UTC-5)
ZONA_HORARIA_PERU = timezone(timedelta(hours=-5))

def obtener_token_ms():
    """Obtiene un token OAuth2 para Microsoft Graph API usando Client Credentials."""
    if not all([MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET]):
        print("Faltan credenciales de Microsoft Graph en .env")
        return None
        
    authority = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        MS_CLIENT_ID,
        authority=authority,
        client_credential=MS_CLIENT_SECRET
    )
    result = app.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"Error obteniendo token: {result.get('error')}")
        return None

def obtener_saldo_actual():
    """Consulta la última fila de la tabla en Excel para obtener el último saldo."""
    token = obtener_token_ms()
    if not token:
        return None
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Obtener las filas de la tabla
    url = f"https://graph.microsoft.com/v1.0/sites/{MS_SITE_ID}/drives/{MS_DRIVE_ID}/items/{MS_ITEM_ID}/workbook/tables/{MS_TABLE_NAME}/rows"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error consultando Excel: {response.text}")
            return None
            
        data = response.json()
        filas = data.get("value", [])
        
        if not filas:
            return None # Tabla vacía
            
        # La tabla puede tener filas vacías pre-asignadas al final. 
        # Iteramos hacia atrás hasta encontrar un saldo numérico válido.
        for fila in reversed(filas):
            valores = fila.get("values", [[]])[0]
            if len(valores) > 12:
                saldo_str = str(valores[12]).replace(",", "").strip()
                if saldo_str and saldo_str != "-" and saldo_str != "":
                    try:
                        return float(saldo_str)
                    except ValueError:
                        continue
                        
        return None # Si llegamos aquí, no había ningún saldo válido
    except Exception as e:
        print(f"Excepción obteniendo saldo actual: {e}")
        return None

def _extraer_texto_de_imagen(image_bytes: bytes) -> str:
    """Paso 1: Usa el modelo multimodal solo para transcribir el texto de la imagen."""
    imagen_base64 = base64.b64encode(image_bytes).decode('utf-8')

    response = llm_client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        max_completion_tokens=500,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe todo el texto visible en esta imagen. Solo el texto, sin formato ni explicación."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_base64}"}}
                ]
            }
        ]
    )
    return response.choices[0].message.content.strip()


def extraer_datos_recibo_llm(image_bytes: bytes, contexto_usuario: str) -> dict:
    """Extrae datos del comprobante en dos pasos: OCR multimodal + interpretación con modelo de texto."""
    contexto_seguro = (
        contexto_usuario.replace("{", "(").replace("}", ")").replace("```", "").replace("<", "").replace(">", "").strip()[:200]
        if contexto_usuario else "N/A"
    )

    # Paso 1: Extraer texto de la imagen con el modelo de visión
    try:
        texto_ocr = _extraer_texto_de_imagen(image_bytes)
    except Exception as e:
        print(f"Error en OCR multimodal: {e}")
        return {"error": True}

    if not texto_ocr or len(texto_ocr) < 10:
        print(f"OCR devolvió texto insuficiente: '{texto_ocr}'")
        return {"error": True}

    # Paso 2: Interpretar el texto con modelo de texto (sin imagen)
    prompt = f"""Extrae datos financieros del comprobante.

Texto del comprobante:
{texto_ocr[:800]}

Contexto: {contexto_seguro}

Solo JSON válido:
{{"fecha":"DD/MM/YYYY","concepto":"...","tipo":"Compra|DeudaXCobrar|Deuda Cobrada|Transferencia|Donación|No determinado","ing_eg":"Ingreso|Egreso|No determinado","motivo":"...","acreedor":"...","deudor":"...","estado":"Pagado|Pendiente|Rechazado|No determinado","monto":0.00}}

Reglas: datos solo del texto/contexto. Sin inventar. Dato faltante="No disponible". Monto faltante=null."""

    try:
        response = llm_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            max_completion_tokens=300,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )

        contenido = response.choices[0].message.content
        datos = json.loads(contenido)

        campos_requeridos = {"fecha", "concepto", "tipo", "ing_eg", "motivo", "acreedor", "deudor", "estado", "monto"}
        if set(datos.keys()) != campos_requeridos:
            raise ValueError(f"Campos JSON incorrectos: {list(datos.keys())}")

        return datos

    except Exception as e:
        print(f"Error en LLM interpretación: {e}")
        try:
            print("Respuesta recibida:")
            print(response.choices[0].message.content)
        except:
            pass
        return {"error": True}


def calcular_codigo_y_nro(fecha_str: str) -> tuple:
    """Calcula el autoincremental del día consultando las filas de Excel."""
    meses_letras = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    try:
        dia, mes, anio = fecha_str.split("/")
        letra_mes = meses_letras[int(mes) - 1]
        fecha_ddmmyy = f"{dia}{mes}{anio[-2:]}"
    except:
        ahora = datetime.now(ZONA_HORARIA_PERU)
        letra_mes = meses_letras[ahora.month - 1]
        fecha_ddmmyy = ahora.strftime("%d%m%y")
        fecha_str = ahora.strftime("%d/%m/%Y")

    token = obtener_token_ms()
    nro_operacion_dia = 1
    
    if token:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        url = f"https://graph.microsoft.com/v1.0/sites/{MS_SITE_ID}/drives/{MS_DRIVE_ID}/items/{MS_ITEM_ID}/workbook/tables/{MS_TABLE_NAME}/rows"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                filas = response.json().get("value", [])
                conteo_hoy = 0
                for fila in filas:
                    valores = fila.get("values", [[]])[0]
                    # Indice 1 es fecha, indice 2 es nro_operacion
                    if len(valores) > 2 and valores[1] == fecha_str:
                        try:
                            nro = int(valores[2])
                            if nro > conteo_hoy:
                                conteo_hoy = nro
                        except:
                            pass
                nro_operacion_dia = conteo_hoy + 1
        except Exception as e:
            print(f"Error calculando autoincremental: {e}")

    nro_str = f"{nro_operacion_dia:02d}" 
    codigo = f"{letra_mes}{fecha_ddmmyy}{nro_str}"
    
    return codigo, nro_operacion_dia

def guardar_en_excel(datos: dict, saldo_previo: float) -> dict:
    """Guarda directamente en el Excel de SharePoint usando Graph API."""
    codigo, nro_operacion_dia = calcular_codigo_y_nro(datos["fecha"])
    
    try:
        monto_float = float(datos["monto"])
    except ValueError:
        monto_float = 0.0

    ingreso_val = 0
    egreso_val = 0
    
    if datos["ing_eg"].lower() == "ingreso":
        ingreso_val = monto_float
        nuevo_saldo = saldo_previo + monto_float
    else:
        egreso_val = monto_float
        nuevo_saldo = saldo_previo - monto_float

    datos["codigo"] = codigo
    datos["nro_operacion_dia"] = str(nro_operacion_dia)
    datos["ingreso_final"] = ingreso_val
    datos["egreso_final"] = egreso_val
    datos["saldo"] = f"{nuevo_saldo:.2f}"

    fila_nueva = [
        None,
        datos["fecha"],
        str(nro_operacion_dia),
        datos["concepto"],
        datos["tipo"],
        datos["ing_eg"],
        datos["motivo"],
        datos["acreedor"],
        datos["deudor"],
        datos["estado"],
        ingreso_val,
        egreso_val,
        None
    ]
    
    token = obtener_token_ms()
    if not token:
        raise Exception("Falla de autenticación con SharePoint. Faltan credenciales MS Graph. Habla con el área de TIC.")
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "values": [fila_nueva]
    }
    
    url = f"https://graph.microsoft.com/v1.0/sites/{MS_SITE_ID}/drives/{MS_DRIVE_ID}/items/{MS_ITEM_ID}/workbook/tables/{MS_TABLE_NAME}/rows/add"
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status() 
    
    return datos
