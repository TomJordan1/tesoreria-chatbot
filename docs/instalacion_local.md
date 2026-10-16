## 🚀 Instalación y Ejecución Local

### 🔑 Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/TomJordan1/tesoreria-chatbot.git
cd tesoreria-chatbot
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
TELEGRAM_WEBHOOK_SECRET=tu_secreto_aleatorio_del_webhook
GROQ_API_KEY=tu_api_key_de_groq
GROQ_MODELO_VISION=qwen/qwen3.6-27b
GROQ_MODELO_TEXTO=llama-3.3-70b-versatile
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

Agrega `TELEGRAM_WEBHOOK_SECRET` a tu `.env` y registra el mismo valor como `secret_token` con Telegram, usando la URL HTTPS de Ngrok terminada en `/webhook`. Sigue [la guía de configuración del webhook protegido](webhook_telegram.md). La aplicación no inicia sin un secreto válido y una llamada HTTP directa sin la cabecera correcta recibe 403, incluso para `/mi_id`.

Si todo salió bien, Telegram responderá:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

### ✅ Listo

Antes de probar registros, configura la tabla de usuarios siguiendo [Control de acceso desde Excel](control_acceso.md). Mientras no figure tu Telegram ID como activo, solo podrás usar `/mi_id`. La lista vive en otro Excel de la misma biblioteca, identificado por `MS_USUARIOS_ITEM_ID`. Conserva `MS_ITEM_ID` para el archivo contable.

Ahora puedes enviar fotos o mensajes a tu bot desde Telegram y el servidor local procesará las solicitudes en tiempo real.

Para probar sin insertar registros en Excel, elige **5) Generar PDF sin registrar en Excel** en el resumen. Si la consulta inicial de saldo falla o la tabla está vacía, usa `/solo_pdf` para continuar sin saldo inicial. El PDF lleva un aviso de prueba; puedes editar los datos o terminar con `/cancelar`. Las opciones 1 y 2 sí guardan en la tabla configurada, incluso cuando el servidor corre localmente.

### Modelos de IA configurables

`GROQ_MODELO_VISION` y `GROQ_MODELO_TEXTO` son opcionales y conservan los modelos actuales si se omiten. Se pueden cambiar sin editar código; al guardar, reinicia o despliega el servicio para aplicar la configuración. Si el nuevo modelo de visión no admite `reasoning_effort`, configura `GROQ_VISION_EXTRA_PARAMS={}`. Consulta [la guía de modelos de Groq](modelos_groq.md) para las opciones específicas.
