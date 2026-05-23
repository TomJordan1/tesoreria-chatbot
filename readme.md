# Toribio Bot

<p align="center">
  <img src="/toribio_telegram.png" width="300" alt="Imagen de perfil del chatbot de Telegram">
</p>

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![FastAPI](https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi)

Toribio Bot es un bot de Telegram diseñado para automatizar el registro de gastos. Recibe fotografías de recibos o facturas, extrae la información clave mediante reconocimiento óptico de caracteres (OCR) y registra los datos automáticamente en una hoja de cálculo de Google Sheets.

## ✨ Características
* **Recepción de imágenes:** Interfaz directa a través de Telegram.
* **Procesamiento OCR:** Integración con la API de OCR.space para extraer texto de las imágenes.
* **Extracción inteligente:** Uso de expresiones regulares para identificar montos y proveedores.
* **Sincronización en la nube:** Registro automático y estructurado en Google Sheets.

## 🛠️ Stack Tecnológico
* **Lenguaje:** Python 3
* **Framework Web:** FastAPI (con Uvicorn)
* **Integraciones:** API de Telegram, OCR.space API, Google Sheets API (`gspread`)


## 🚀 Configuración e Instalación Local

Para correr este proyecto en tu máquina local y hacer pruebas, sigue estos pasos:

### 🔑 Paso 0: Obtención de Credenciales

Antes de empezar, necesitas obtener dos claves gratuitas para que el bot funcione:

**1. Telegram Bot Token:**
* Abre Telegram y busca al usuario oficial **@BotFather**.
* Envía el comando `/newbot` y sigue las instrucciones para darle un nombre y un *username* (debe terminar en `bot`).
* Al finalizar, te entregará un token similar a `1234567890:ABCDef...`. Este será tu `TELEGRAM_TOKEN`.

**2. OCR.space API Key (Plan Gratuito):**
* Ve a [ocr.space/ocrapi](https://ocr.space/ocrapi).
* Haz clic en **"Register for free API Key"** y llena el formulario corto.
* Revisa tu correo electrónico para encontrar tu clave alfanumérica. Este será tu `OCR_API_KEY`.


### 🛠️ Paso 1: Clonar e Instalar

**1. Clona el repositorio:**
```bash
git clone https://github.com/TomJordan1/toribio_bot.git
cd toribio_bot

```

**2. Crea un entorno virtual e instala las dependencias:**

```bash
# Crear entorno virtual (linux - python, windows - py)
python -3.11 -m venv venv


# Activar en Windows:
venv\bin\activate
# Activar en macOS/Linux:
source venv/bin/activate

# Instalar librerías necesarias
pip install fastapi uvicorn requests gspread google-auth

# (Alternativa opcional)

pip install > requirements.txt

```


### ⚙️ Paso 2: Configuración del Entorno y Google Sheets

**1. Variables de Entorno (.env):**
Crea un archivo llamado `.env` en la raíz del proyecto y añade tus tokens:

```env
TELEGRAM_TOKEN=tu_token_de_telegram_aqui
OCR_API_KEY=tu_api_key_de_ocr_aqui

```

**2. Credenciales de Google Sheets:**

* Ve a Google Cloud Console, crea un proyecto y habilita la **Google Sheets API** y la **Google Drive API**.
* Genera una cuenta de servicio (Service Account) en la opción "IAM y administración" y descarga el archivo JSON de las claves.
* Renombra el archivo a `cred.json` y colócalo en la raíz del proyecto.
* Crea una hoja de cálculo en Google Sheets llamada **Gastos**.
* Comparte esa hoja dándole permisos de "Editor" al correo de tu Service Account (el que termina en `@...iam.gserviceaccount.com`).


### ▶️ Paso 3: Ejecución y Webhook (Ngrok)

**1. Ejecuta el servidor local:**
Inicia FastAPI con Uvicorn. El servidor correrá en el puerto 8000.

```bash
uvicorn main:app --reload

```

**2. Expón tu servidor con Ngrok:**
Telegram no puede enviar mensajes a `localhost`. Para solucionarlo, abre una *nueva terminal* y ejecuta Ngrok para crear un túnel público:

```bash
ngrok http 8000

```

Copia la URL segura que genera (ej. `https://abcd-12-34-56.ngrok-free.app`).

**3. Configura el Webhook en Telegram:**
Abre tu navegador web y visita la siguiente URL, reemplazando los campos con tu Token y tu enlace de Ngrok:

```text
https://api.telegram.org/bot<TU_TELEGRAM_TOKEN>/setWebhook?url=<TU_URL_NGROK>/webhook

```

*Si todo sale bien, verás un mensaje JSON confirmando: `{"ok":true,"result":true,"description":"Webhook was set"}`.*

***¡Listo!*** Ya puedes enviarle la foto de un recibo a tu bot en Telegram y verás cómo el proceso se ejecuta en tu terminal local.

## ↗️ Roadmap
[Notion](https://goo.su/jHV8K)
