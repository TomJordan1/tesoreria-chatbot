# Toribio Bot

<p align="center">
  <img src="toribio_telegram.png" width="250" alt="Imagen de perfil del chatbot de Telegram">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Groq_AI-f55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq AI">
</p>

Toribio Bot es un chatbot de Telegram diseñado para la gestión y automatización del registro de gastos en tiempo real para proyectos y auditorías internas de grupos estudiantiles. 

El bot recibe fotografías de recibos, boletas o facturas, utiliza un Modelo de Lenguaje Visual (VLM) para comprender e inyectar la información en una base de datos centralizada de Google Sheets, y ofrece la capacidad opcional de generar al instante un comprobante de validación en PDF procesado 100% de manera local.

## ✨ Características Principal
* **Procesamiento de Imágenes con IA:** Integración con la API de Groq utilizando el modelo de visión estable `llama-3.2-11b-vision-instruct` para extraer de forma conceptual campos complejos como RUC, Proveedor, Monto Total, Fecha de Emisión y Categoría.
* **Flujo Conversacional Interactivo:** Sistema dinámico que permite al usuario confirmar los datos extraídos, editarlos manualmente en bloque mediante un formato estructurado con barras (`?`) o cancelar la operación antes de registrar.
* **Asignación Correlativa:** Generación automática de un índice incremental (`ID`) en la base de datos para facilitar auditorías de gastos futuras.
* **Generación Local de PDF Externa:** Compilación asíncrona y ultra-rápida de comprobantes en PDF basada en un archivo de diseño separado (`plantilla.html`) usando la memoria RAM, eliminando dependencias pesadas y cuotas limitadas de almacenamiento en la nube.
* **Limpieza Inmediata de Almacenamiento:** Política de borrado en tiempo real que elimina los PDFs locales del servidor inmediatamente después de ser despachados por Telegram, manteniendo el uso de disco del servidor en 0 MB de forma persistente.

## 🛠️ Stack Tecnológico
* **Core:** Python 3.11+ & FastAPI (servidor web asíncrono gestionado con Uvicorn).
* **Inteligencia Artificial:** OpenAI SDK (redireccionado a los endpoints de visión de Groq).
* **Manipulación de PDFs:** `fpdf2` (conversión nativa y ligera de HTML a PDF en local).
* **Integración de Datos:** Google Drive & Google Sheets API a través de la librería `gspread`.

## 📂 Estructura de Archivos del Directorio
```text
toribio_bot/
│
├── main.py              # Lógica principal de FastAPI, webhooks y estados de los usuarios en Telegram.
├── servicios.py         # Conexión con la IA de Groq (VLM) y operaciones CRUD en Google Sheets.
├── generador_pdf.py     # Módulo encargado de leer el HTML, inyectar variables y compilar el PDF local.
├── plantilla.html       # Molde de diseño y estructura visual con etiquetas {{campo}} para el PDF.
├── requirements.txt     # Dependencias y librerías de Python requeridas para producción.
├── cred.json            # Archivo de claves privadas de la Cuenta de Servicio de Google Cloud (ignorado en git).
├── .env                 # Variables de entorno y tokens de autenticación estrictamente secretos.
└── toribio_telegram.png # Imagen de identidad visual del bot para documentación.
