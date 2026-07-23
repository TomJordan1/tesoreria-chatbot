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
GROQ_API_KEY=tu_api_key_de_groq
POWER_AUTOMATE_URL=tu_url_del_webhook_de_power_automate
```

---

## ☁️ Producción (Deploy en Render)

### 1. Crear Web Service

En :contentReference[oaicite:0]{index=0}:

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
GROQ_API_KEY=tu_api_key_de_groq
POWER_AUTOMATE_URL=tu_url_del_webhook_de_power_automate
```

---

### 4. Configurar Webhook de Telegram

Reemplaza los valores y abre en tu navegador:

```text
https://api.telegram.org/bot<TU_TELEGRAM_TOKEN>/setWebhook?url=https://<TU_APP>.onrender.com/webhook
```

Si todo salió correctamente, Telegram responderá:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

### ✅ Listo

Ahora puedes enviar fotos o mensajes a tu bot desde Telegram y el servidor procesará las solicitudes.