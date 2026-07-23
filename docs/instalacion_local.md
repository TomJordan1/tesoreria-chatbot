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
POWER_AUTOMATE_URL=tu_url_del_webhook_de_power_automate
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