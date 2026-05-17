# Toribio Bot

Toribio es un bot de Telegram diseñado para automatizar el registro de gastos. Recibe fotografías de recibos o facturas, extrae la información clave (proveedor y monto) mediante reconocimiento óptico de caracteres (OCR) y registra los datos automáticamente en una hoja de cálculo de Google Sheets.

## ✨ Características Principales
* **Recepción de imágenes:** Interfaz directa a través de Telegram.
* **Procesamiento OCR:** Integración con la API de OCR.space para extraer texto de las imágenes.
* **Extracción inteligente:** Uso de expresiones regulares para identificar montos y proveedores.
* **Sincronización en la nube:** Registro automático y estructurado en Google Sheets.

## 🛠️ Stack Tecnológico
* **Lenguaje:** Python 3
* **Framework Web:** FastAPI (con Uvicorn)
* **Integraciones:** API de Telegram, OCR.space API, Google Sheets API (`gspread`)

## 🚀 Configuración e Instalación Local

Para correr este proyecto en tu máquina local, sigue estos pasos:

1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/TomJordan1/toribio_bot.git
   cd toribio_bot

2. **WIP**

## ↗️ Roadmap
https://goo.su/jHV8K
