# Chatbot de tesorería

<p align="center">
  <img src="docs/toribio_telegram.png" width="250" alt="Imagen de perfil del chatbot de Telegram">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Groq_AI-f55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq AI">
</p>

Este chatbot de tesorería de Telegram, diseñado para la gestión y automatización del registro de gastos en tiempo real para proyectos y auditorías internas de grupos estudiantiles. 

El bot recibe fotografías de recibos, boletas o facturas, utiliza un Modelo de Lenguaje Visual (VLM) para comprender e inyectar la información en una base de datos centralizada en SharePoint a través de Microsoft Graph API, y ofrece la capacidad opcional de generar al instante un comprobante de validación en PDF procesado 100% de manera local.

## Alcance y operación sin costo adicional

El proyecto está pensado para pocos usuarios y uso ocasional, utilizando el plan gratuito de Render y los modelos disponibles en el plan gratuito de Groq. El objetivo es no generar gastos adicionales por alojar el bot ni por procesar comprobantes, aprovechando el entorno Microsoft 365 ya disponible en la organización.

Se aceptan los tiempos de arranque tras el reposo de Render y los límites de uso de Groq. Las sesiones son temporales y se mantienen en memoria: una operación sin confirmar puede perderse al reiniciar o suspenderse el proceso. En ese caso se debe reenviar la foto. El aviso de reposo se intenta enviar durante el apagado, pero no está garantizado. Los registros ya guardados permanecen en Excel de SharePoint.

La arquitectura actual no requiere una base de datos de sesiones, colas externas ni servicios de pago adicionales. Las mejoras deben priorizar la integridad de los registros y mantener este alcance.

## ✨ Características
* **Webhook Protegido:** Las solicitudes requieren el secreto compartido con Telegram antes de procesar mensajes. Configura `TELEGRAM_WEBHOOK_SECRET` y registra el mismo valor en Telegram según [la guía del webhook](docs/webhook_telegram.md).
* **Acceso desde Excel:** Solo los IDs activos de la tabla `USUARIOS_AUTORIZADOS` pueden usar el bot. `/mi_id` es público para solicitar el alta. Se usa un Excel separado configurado con `MS_USUARIOS_ITEM_ID`; [consulta la guía de configuración](docs/control_acceso.md) antes de habilitar esta versión.
* **Procesamiento de Imágenes con IA:** Pipeline de dos pasos: (1) un modelo de visión transcribe el texto del comprobante, y (2) un modelo de texto interpreta y estructura los datos en un esquema JSON. Los modelos son configurables desde un bloque centralizado en `servicios.py`.
* **Flujo Conversacional Interactivo:** Sistema dinámico que permite al usuario confirmar los datos extraídos, editarlos manualmente en bloque mediante un formato estructurado con signos de interrogación (`?`) o cancelar la operación antes de registrar.
* **Validación antes de Guardar:** El monto debe ser numérico, finito y mayor que cero; Ing/Eg debe ser Ingreso o Egreso. Los datos inválidos se conservan para corregirlos con la opción 3.
* **Errores Diferenciados:** Una falla consultando Excel permite reintentar sin pedir un saldo inicial nuevo. Si falla el PDF después de guardar, el bot aclara que el registro ya existe y no debe repetirse.
* **PDF de Prueba sin Registro:** La opción 5 genera el comprobante sin guardar en Excel y lo marca como prueba. Si falta el saldo inicial o falla su consulta, `/solo_pdf` permite continuar para probar. Los datos quedan disponibles para editar o cancelar.
* **Asignación Correlativa:** Generación automática de un índice incremental (`ID`) en la base de datos para facilitar auditorías de gastos futuros.
* **Generación Local de PDF:** Creación de comprobantes con `fpdf2` y una plantilla separada (`plantilla.html`), con la imagen original en una segunda página y archivos temporales locales durante el envío.
* **Limpieza de Almacenamiento:** Tras generar y enviar el PDF, o si falla el proceso, se intenta borrar tanto el PDF como la imagen temporal del servidor.

## 🛠️ Stack Tecnológico
* **Core:** Python 3.11+ & FastAPI (servidor web asíncrono gestionado con Uvicorn).
* **Inteligencia Artificial:** OpenAI SDK (redireccionado a Groq). Pipeline OCR multimodal + interpretación de texto.
* **Manipulación de PDFs:** `fpdf2` (conversión nativa y ligera de HTML a PDF en local).
* **Integración de Datos:** Conexión nativa a Microsoft Graph API (con `msal`) para registrar en SharePoint de forma directa.

## 📂 Estructura del repositorio
```text
tesoreria-chatbot/
│
├── main.py              # Lógica principal de FastAPI, webhooks y estados de los usuarios en Telegram.
├── servicios.py         # Configuración de modelos, pipeline OCR+LLM, y operaciones CRUD en SharePoint.
├── generador_pdf.py     # Módulo encargado de leer el HTML, inyectar variables y compilar el PDF local.
├── plantilla.html       # Molde de diseño y estructura visual con etiquetas {{campo}} para el PDF.
├── requirements.txt     # Dependencias y librerías de Python requeridas para producción.
├── **.env               # Variables de entorno y tokens de autenticación estrictamente secretos (ignorado en git).
├── infografia.png       # Imagen guía del flujo del chatbot.
└── logo.png             # Imagen de identidad visual del bot para documentación.
```

Consulta los detalles de operación y cambios en [la documentación de integración](docs/documentacion_integracion.md) y [la guía de producción](docs/instalacion_prod.md).
