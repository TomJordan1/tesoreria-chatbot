## 🚀 Instalación y Producción

### 🔑 Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/TomJordan1/toribio_bot.git
cd toribio_bot
```

---

### 🛠️ Paso 2: Crear el Entorno Virtual e Instalar Dependencias

```bash
# Crear entorno virtual
python -3.11 -m venv venv

# Activar en Windows
venv\Scripts\activate

# Activar en macOS/Linux
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

### ⚙️ Paso 3: Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
TELEGRAM_TOKEN=tu_token_de_telegram
TELEGRAM_WEBHOOK_SECRET=tu_secreto_aleatorio_del_webhook
GROQ_API_KEY=tu_api_key_de_groq
MS_TENANT_ID=tu_tenant_id_de_microsoft
MS_CLIENT_ID=tu_client_id_de_microsoft
MS_CLIENT_SECRET=tu_client_secret_de_microsoft
MS_SITE_ID=tu_site_id_de_sharepoint
MS_DRIVE_ID=tu_drive_id_de_sharepoint
MS_ITEM_ID=tu_item_id_del_excel
MS_USUARIOS_ITEM_ID=tu_item_id_del_excel_de_usuarios
MS_TABLE_NAME=REGISTRODIARIO3
FORMATO_FECHA_EXCEL=PE
```

---

## ☁️ Producción (Deploy en Render)

Este proyecto utiliza Render y Groq en sus planes gratuitos, para pocos usuarios y uso ocasional. No requiere servicios adicionales de pago; la integración con SharePoint utiliza el entorno Microsoft 365 existente de la organización.

Las sesiones se guardan únicamente en memoria. Si Render suspende o reinicia el proceso, las operaciones sin confirmar pueden perderse y habrá que reenviar la foto. Es una limitación aceptada de este despliegue. El primer acceso tras el reposo puede demorar; el aviso de apagado es un intento y no está garantizado. También se aceptan los límites del plan gratuito de Groq.

No se agregaron variables de entorno ni dependencias para las correcciones de validación y manejo de errores descritas en la documentación de integración.

Para experimentar sin escribir en SharePoint, envía una foto, completa los datos y elige **5) Generar PDF sin registrar en Excel** en el resumen. Si Excel está vacío o falla la consulta inicial de saldo, usa `/solo_pdf` para continuar sin saldo inicial. El PDF se marca como prueba y la sesión permanece abierta para editar o cancelar. Las opciones 1 y 2 sí guardan registros reales.

### 1. Crear Web Service

En Render:

- Crear un nuevo **Web Service**
- Conectar el repositorio de GitHub

---

### 2. Configuración del Servicio

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

### 3. Variables de Entorno

Agregar en Render:

```env
TELEGRAM_TOKEN=tu_token_de_telegram
TELEGRAM_WEBHOOK_SECRET=tu_secreto_aleatorio_del_webhook
GROQ_API_KEY=tu_api_key_de_groq
MS_TENANT_ID=tu_tenant_id_de_microsoft
MS_CLIENT_ID=tu_client_id_de_microsoft
MS_CLIENT_SECRET=tu_client_secret_de_microsoft
MS_SITE_ID=tu_site_id_de_sharepoint
MS_DRIVE_ID=tu_drive_id_de_sharepoint
MS_ITEM_ID=tu_item_id_del_excel
MS_USUARIOS_ITEM_ID=tu_item_id_del_excel_de_usuarios
MS_TABLE_NAME=REGISTRODIARIO3
FORMATO_FECHA_EXCEL=PE
```

> **Nota:** `FORMATO_FECHA_EXCEL` acepta `PE` (DD/MM/YYYY, por defecto) o `US` (MM/DD/YYYY). Cambiar solo si la región del Excel Online está configurada en inglés.

---

### 4. Configurar Webhook de Telegram

Configura `TELEGRAM_WEBHOOK_SECRET` en Render y registra el mismo valor como `secret_token` en Telegram. Sigue [la guía del webhook protegido](webhook_telegram.md), que incluye generación del secreto y registro por POST sin introducir credenciales en el historial de comandos. Usa la URL `https://<TU_APP>.onrender.com/webhook`.

Prepara la variable y el registro en Telegram antes de desplegar esta versión: la aplicación no inicia sin un secreto válido y las llamadas sin la cabecera correcta reciben 403.

Si todo salió correctamente, Telegram responderá:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

### ✅ Listo

Antes de habilitar esta versión, prepara la tabla `USUARIOS_AUTORIZADOS` en otro Excel de la misma biblioteca de SharePoint. Sigue [Control de acceso desde Excel](control_acceso.md) para dar de alta a la primera persona con `/mi_id`. Configura `MS_USUARIOS_ITEM_ID` en Render con el ID del archivo de usuarios. Sin usuarios habilitados, solo funciona `/mi_id`; las altas y bajas se reflejan al renovar la lista, hasta dos minutos después.

Ahora puedes enviar fotos o mensajes a tu bot desde Telegram y el servidor procesará las solicitudes.
