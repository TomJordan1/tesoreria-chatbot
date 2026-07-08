import os
import json
import base64
import requests
from openai import OpenAI
from datetime import datetime, timezone, timedelta

# --- CONFIGURACIÓN DE GROQ ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("🚨 ERROR: Falta GROQ_API_KEY en el archivo .env")

llm_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- WEBHOOK POWER AUTOMATE (SHAREPOINT) ---
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL")

# Hora de Perú (UTC-5)
ZONA_HORARIA_PERU = timezone(timedelta(hours=-5))
ARCHIVO_MEMORIA = "memoria_toribio.json"

def cargar_memoria():
    """Carga la caché local para no tener que consultar el Excel de SharePoint cada vez."""
    if os.path.exists(ARCHIVO_MEMORIA):
        with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"fecha_actual": "", "conteo_dia": 0, "ultimo_saldo": None}

def guardar_memoria(memoria):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, indent=4)

def obtener_saldo_actual():
    """Retorna el último saldo registrado en la memoria local."""
    memoria = cargar_memoria()
    return memoria.get("ultimo_saldo")

def extraer_datos_recibo_llm(image_bytes: bytes, contexto_usuario: str) -> dict:
    imagen_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = f"""
    Eres un auditor financiero. Analiza este comprobante (o captura) y cruza la información con este contexto del usuario:
    CONTEXTO DEL USUARIO: "{contexto_usuario}"
    
    Extrae los siguientes datos en un JSON estricto:
    {{
        "fecha": "Fecha de la operación en formato DD/MM/YYYY",
        "concepto": "Descripción de la compra/transferencia",
        "tipo": "Clasifica como: Compra, DeudaXCobrar, Deuda Cobrada, etc.",
        "ing_eg": "Debe ser estrictamente 'Ingreso' o 'Egreso'",
        "motivo": "Motivo específico (ej. Página Web, Integración)",
        "acreedor": "Quién es el acreedor (o 'No Aplica')",
        "deudor": "Quién es el deudor (o 'No Aplica')",
        "estado": "Estado del pago (ej. 'Pagado', 'Pendiente')",
        "monto": "Monto total (solo el número con dos decimales)"
    }}
    Devuelve ÚNICAMENTE el objeto JSON.
    """

    try:
        response = llm_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error en LLM: {e}")
        return {"error": True}

def calcular_codigo_y_nro(fecha_str: str) -> tuple:
    """Calcula el autoincremental del día usando la memoria local."""
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

    memoria = cargar_memoria()
    
    if memoria.get("fecha_actual") == fecha_str:
        nro_operacion_dia = memoria.get("conteo_dia", 0) + 1
    else:
        nro_operacion_dia = 1
        
    nro_str = f"{nro_operacion_dia:02d}" 
    codigo = f"{letra_mes}{fecha_ddmmyy}{nro_str}"
    
    return codigo, nro_operacion_dia

def guardar_en_sheets(datos: dict, saldo_previo: float) -> dict:
    """
    El nombre de la función se mantiene para no romper main.py, 
    pero ahora dispara los datos hacia Microsoft SharePoint.
    """
    codigo, nro_operacion_dia = calcular_codigo_y_nro(datos["fecha"])
    
    try:
        monto_float = float(datos["monto"])
    except ValueError:
        monto_float = 0.0

    ingreso_val = "-"
    egreso_val = "-"
    
    if datos["ing_eg"].lower() == "ingreso":
        ingreso_val = f"{monto_float:.2f}"
        nuevo_saldo = saldo_previo + monto_float
    else:
        egreso_val = f"{monto_float:.2f}"
        nuevo_saldo = saldo_previo - monto_float

    datos["codigo"] = codigo
    datos["nro_operacion_dia"] = str(nro_operacion_dia)
    datos["ingreso_final"] = ingreso_val
    datos["egreso_final"] = egreso_val
    datos["saldo"] = f"{nuevo_saldo:.2f}"

    # El JSON exacto que Power Automate está esperando
    payload = {
        "codigo": codigo,
        "fecha": datos["fecha"],
        "nro_operacion_dia": str(nro_operacion_dia),
        "concepto": datos["concepto"],
        "tipo": datos["tipo"],
        "ing_eg": datos["ing_eg"],
        "motivo": datos["motivo"],
        "acreedor": datos["acreedor"],
        "deudor": datos["deudor"],
        "estado": datos["estado"],
        "ingreso_final": ingreso_val,
        "egreso_final": egreso_val,
        "saldo": f"{nuevo_saldo:.2f}"
    }
    
    # Inyectar los datos a SharePoint
    response = requests.post(POWER_AUTOMATE_URL, json=payload)
    response.raise_for_status() 
    
    # Actualizar la memoria local si el guardado fue exitoso
    memoria = cargar_memoria()
    memoria["fecha_actual"] = datos["fecha"]
    memoria["conteo_dia"] = nro_operacion_dia
    memoria["ultimo_saldo"] = nuevo_saldo
    guardar_memoria(memoria)
    
    return datos