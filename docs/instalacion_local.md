## 🚀 Instalación y Ejecución Local

### 🔑 Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/TomJordan1/toribio_bot.git
cd toribio_bot
```

---

### 🛠️ Paso 2: Crear Entorno Virtual e Instalar Dependencias

```bash
# Crear entorno virtual
python -m venv venv

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
GROQ_API_KEY=tu_api_key_de_groq
MS_TENANT_ID=tu_tenant_id_de_microsoft
MS_CLIENT_ID=tu_client_id_de_microsoft
MS_CLIENT_SECRET=tu_client_secret_de_microsoft
MS_SITE_ID=tu_site_id_de_sharepoint
MS_DRIVE_ID=tu_drive_id_de_sharepoint
MS_ITEM_ID=tu_item_id_del_excel
MS_TABLE_NAME=REGISTRODIARIO3
```

---

### ▶️ Paso 4: Ejecutar el Servidor Local

```bash
uvicorn main:app --reload
```

El servidor quedará disponible en:

```text
http://127.0.0.1:8000
```

---

### 🌐 Paso 5: Exponer el Servidor con Ngrok

Telegram no puede conectarse a `localhost`, así que necesitas un túnel público.

En otra terminal ejecuta:

```bash
ngrok http 8000
```

Ngrok generará una URL HTTPS similar a:

```text
https://abcd-1234.ngrok-free.app
```

---

### 🔗 Paso 6: Configurar el Webhook de Telegram

Abre en tu navegador:

```text
https://api.telegram.org/bot<TU_TELEGRAM_TOKEN>/setWebhook?url=<TU_URL_NGROK>/webhook
```

Ejemplo:

```text
https://api.telegram.org/bot123456:ABCDEF/setWebhook?url=https://abcd-1234.ngrok-free.app/webhook
```

Si todo salió bien, Telegram responderá:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

### ✅ Listo

Ahora puedes enviar fotos o mensajes a tu bot desde Telegram y el servidor local procesará las solicitudes en tiempo real.