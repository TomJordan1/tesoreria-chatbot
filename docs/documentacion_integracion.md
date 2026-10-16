# Documentación de Arquitectura e Integración (v2.0)

Este documento detalla la arquitectura técnica actual del sistema de tesorería y registra los cambios implementados para la migración de un flujo manual/local a un entorno completamente integrado en la nube (Telegram + SharePoint + Power BI).

## 1. Arquitectura del Sistema
El sistema se compone de cuatro nodos principales que interactúan de forma secuencial:

1. **Interfaz de Usuario (Telegram):** Punto de entrada. Los usuarios envían comprobantes fotográficos e instrucciones textuales al bot (Toribio).
2. **Motor de Procesamiento (FastAPI + Groq LLM):** El servidor en Render recibe los webhooks de Telegram. Si hay una imagen, se ejecuta un pipeline de dos pasos: (1) un modelo multimodal transcribe el texto del comprobante, y (2) un modelo de texto clasifica y estructura los datos en un esquema JSON. Los modelos son intercambiables desde la configuración centralizada en `servicios.py`.
3. **Base de Datos (Excel en SharePoint):** Repositorio central de datos (`REGISTRODIARIO3`). El backend de Python se comunica con Excel usando la API de Microsoft Graph para insertar y leer filas.
4. **Visualización (Power BI):** El modelo semántico alojado en Power BI Service se conecta directamente al archivo de SharePoint mediante una URL web, actualizando los dashboards de forma programada.

---

## 2. Registro de Cambios y Actualizaciones

A continuación se detallan las modificaciones realizadas respecto a la versión anterior del sistema (previo a la versión producción final).

### Criterios de operación

El bot se utiliza por un grupo reducido, de forma ocasional. Se usan el plan gratuito de Render y modelos del plan gratuito de Groq para evitar gastos adicionales, junto con el entorno Microsoft 365 existente. Se aceptan el reposo y arranque de Render, los límites de Groq y las sesiones temporales en memoria. No se requiere persistencia de sesiones ni infraestructura externa adicional. Si el proceso se reinicia, puede ser necesario reenviar los comprobantes todavía sin confirmar; el aviso de apagado no está garantizado.

### Actualización del 16 de octubre de 2026: integridad del registro

* **Validación de monto y clasificación:** Antes de consultar el saldo para guardar y también dentro de `guardar_en_excel`, se exige un monto numérico, finito y mayor que cero y una clasificación Ingreso o Egreso. Se toleran mayúsculas y espacios exteriores en la clasificación. No se convierten datos inválidos a cero ni clasificaciones desconocidas a egreso. La sesión permanece abierta para editar con la opción 3.
* **Saldo vacío frente a error:** `obtener_saldo_actual` devuelve `None` únicamente para una tabla sin filas o con filas vacías. Los fallos de autenticación, conexión, respuesta o registros sin saldo válido generan `ErrorConsultaSaldo`. Al recibir la foto, se conserva para reintentar con 1; al confirmar, se conservan los datos y no se escribe con un saldo desactualizado cuando falla la consulta. Un saldo inicial no puede ser NaN ni infinito.
* **Guardado separado del PDF:** Tras una escritura confirmada, la sesión se cierra antes de generar o enviar el respaldo. Si falla ese paso, se informa que la operación ya está en Excel y no debe registrarse otra vez. El envío del PDF tiene timeout y comprueba tanto el estado HTTP como la confirmación de Telegram; se intenta limpiar los archivos temporales incluso al fallar.
* **Escritura sin confirmación:** Si falla la escritura, no se afirma que Excel no guardó. La sesión pasa a `verificar_guardado` y bloquea nuevos intentos de inserción desde esa sesión hasta que se revise Excel y se use `/cancelar`. Esto reduce el riesgo de duplicar una escritura cuyo resultado se desconoce; no constituye una garantía de deduplicación persistente.
* **Alcance conservado:** No se cambian los modelos, el formato de fechas ni el esquema de 13 columnas de Excel. No se agregan dependencias de producción o servicios de pago.

### Exportar PDF sin registrar (opción 5)

La opción **5) Solo generar PDF de prueba (sin guardar)** del resumen genera y envía el comprobante sin consultar saldos, calcular correlativos ni insertar filas en Excel durante la exportación. Las opciones 1 y 2 conservan el guardado habitual. Se valida el monto y la clasificación también para exportar.

El documento lleva el aviso **PRUEBA - SIN REGISTRO EN EXCEL**, un identificador temporal `PRUEBA_...`, número de operación sin registro y saldo no calculado. Incluye la imagen del comprobante como el respaldo normal. Los datos originales se conservan para editar, volver a exportar o confirmar un registro real posteriormente; `/cancelar` termina la sesión. Si falla la exportación, se puede reintentar con 5. Se limpian los archivos temporales tanto al finalizar como al fallar.

Si la consulta inicial de saldo falla o Excel está vacío, `/solo_pdf` permite continuar con la foto sin introducir saldo inicial. Después de procesarla, se elige 5. Si luego se decide guardar con 1 o 2 y la tabla sigue vacía, se solicita el saldo inicial y se vuelve al resumen sin repetir el OCR. La exportación de un comprobante ya procesado no llama a Groq otra vez.

### Verificación local

Ejecutar `python -m unittest discover -s tests -v` desde la raíz. Las pruebas usan la biblioteca estándar y sustituyen las integraciones externas, sin consumir cuota de Groq, enviar mensajes ni escribir en SharePoint. Cubren validación, conservación de sesiones ante errores, reintento de consulta de saldo, guardado de ingresos/egresos, incertidumbre de escritura, fallos del PDF, exportación sin acceso a Excel y aviso de prueba en la plantilla. No reemplazan una prueba de integración con las credenciales y servicios reales ni una revisión visual del PDF renderizado.

### Acceso mediante lista de usuarios en Excel

Se agrega la tabla `USUARIOS_AUTORIZADOS` al mismo libro configurado, con columnas `telegram_id`, `nombre` y `activo`. El nombre de tabla está definido en `servicios.py`; no se agregan variables de entorno ni dependencias. El permiso se comprueba antes de procesar fotos, comandos, estados, IA, registros o PDFs, usando `message.from.id` y no el ID del chat. `/mi_id` es público, no consulta Excel y conserva la sesión actual; las personas no autorizadas reciben el mensaje de Toribio acordado.

La lista se cachea dos minutos en memoria. Al vencer, un fallo descarta el acceso anterior y establece 30 segundos antes de reintentar, manteniendo `/mi_id` disponible. Una fila inactiva prevalece ante duplicados. Las pruebas cubren lectura por encabezados, bajas y expiración, fallos de consulta, acceso público al ID y bloqueo del resto del flujo para desconocidos.

Antes de habilitar esta versión, preparar la tabla siguiendo [la guía de control de acceso](control_acceso.md). La lectura real en SharePoint debe comprobarse en el despliegue con las credenciales existentes. La autenticación del origen HTTP del webhook y la deduplicación mediante `update_id` siguen pendientes.

### 2.1 Backend y Bot de Telegram (Python)
*   **Manejo de Estados de Sesión:** Se corrigió el orden de evaluación en el bucle principal. Los comandos `/ayuda` y `/cancelar` ahora se procesan antes de validar la existencia de un estado activo, permitiendo su ejecución global en cualquier momento de la conversación.
*   **Comando de Ayuda:** Se implementó el comando `/ayuda` que renderiza una infografía almacenada localmente en el repositorio (`infografia.png`) utilizando el método `sendPhoto` de la API de Telegram.
*   **Ajuste de Endpoints (MS Graph):** El payload de escritura se ajustó para enviar un array exacto de 13 elementos por fila, previniendo errores HTTP 400 por desajuste de dimensiones con la tabla destino.
*   **Delegación de Código Autoincremental:** El script ahora envía el valor nulo (`None`) en la primera columna del array correspondiente a `CÓDIGO`. Esto permite que la base de datos (Excel) asuma la responsabilidad de generar el identificador de la transacción.
*   **Lectura Inversa de Saldos:** La función `obtener_saldo_actual` se reescribió para iterar el JSON de respuesta de Microsoft Graph en orden inverso (`reversed(filas)`). Esto evita colisiones o lecturas nulas causadas por filas vacías pre-asignadas en el final de la tabla de Excel.
*   **Refactorización de Nomenclatura:** Se renombró la función principal de escritura de `guardar_en_sheets` a `guardar_en_excel` para reflejar con exactitud la migración de plataforma. Se unificó el nombre del bot a "Toribio" en todos los mensajes.
*   **Formato de Salida:** Se estandarizó el uso de sintaxis HTML para el envío de mensajes por Telegram, debido a que el parseador Markdown generaba conflictos con ciertos caracteres de respuesta del LLM.
*   **Ajuste de Tono y Mensajes:** Se actualizaron los mensajes de respuesta del bot para tener un tono más amigable y conversacional (ej. "¡Muuucho éxito!", "Dame un segundito..."). También se mejoraron los mensajes de error para indicar claramente al usuario qué hacer en caso de fallas de anotación (ej. contactar al área TIC).

### 2.2 Base de Datos (Excel en SharePoint)
*   **Columna Calculada:** Se modificó la columna `CÓDIGO` en la tabla para ejecutar una fórmula nativa (ej. `CHOOSE(MONTH(...))`). La columna calcula su propio valor automáticamente cuando Microsoft Graph inserta una nueva fila.
*   **Alineación de Configuración Regional:** Se detectó un fallo en la inserción de fechas enviadas en formato `DD/MM/YYYY`, provocado por la configuración regional (US) de la cuenta de Microsoft 365. La solución implementada es cambiar la región a nivel de cuenta (Español/Perú) para alinear el motor de parseo interno de Excel con el formato emitido por el script en Python.

### 2.3 Pipeline de Extracción con IA (servicios.py)
*   **Separación en Dos Pasos:** Se reemplazó la consulta multimodal única (imagen + prompt largo) por un pipeline desacoplado:
    1.  **Paso 1 (OCR):** El modelo de visión recibe la imagen y transcribe todo el texto plano visible, sin interpretar ni estructurar.
    2.  **Paso 2 (Interpretación):** Un modelo de texto recibe la transcripción y la estructura en el JSON financiero requerido.
*   **Desactivación de Razonamiento:** Se utiliza el parámetro `reasoning_effort="none"` (API oficial de Groq) para evitar que Qwen3 genere bloques `<think>` que consumían tokens sin aportar a la transcripción. Se mantiene limpieza defensiva con regex por si el modelo ignora el parámetro.
*   **Configuración Centralizada de Modelos:** Los modelos y sus parámetros específicos se definen en un bloque `MODELO_VISION` y `MODELO_TEXTO` al inicio de `servicios.py`. Esto permite cambiar de modelo sin modificar la lógica de las funciones.
*   **Manejo de Errores con Personalidad:** Se implementó `_identificar_error_llm()` que clasifica errores de la API (modelo no encontrado, rate limit, autenticación, timeout) y devuelve mensajes en el personaje de Toribio para que el usuario sepa qué hacer.
*   **Defensas Anti-Inyección:** El paso 2 usa un system prompt que declara los bloques `<COMPROBANTE>` y `<CONTEXTO>` como datos puros, nunca instrucciones. El contexto del usuario se sanitiza (reemplazo de `{}`, `` ``` ``, `<>`) y se limita a 200 caracteres.
*   **Timeouts en Todas las Llamadas:** Se configuró timeout de 30s para Groq (a nivel del cliente OpenAI) y 15s para todas las llamadas a Microsoft Graph y Telegram API.

### 2.4 Generación de PDF (Comprobantes)
*   **Limpieza de Variables Residuales:** Se eliminaron las variables `proveedor`, `ruc` y `fecha_registro` de la lista de campos requeridos en `generador_pdf.py`. Operativamente, el campo `acreedor` cubre la función de identificar al proveedor comercial.
*   **Ajuste de Plantilla HTML:** Se eliminó la etiqueta de tabla (`<tr>`) correspondiente al Proveedor Comercial en `plantilla.html` para evitar la impresión de celdas vacías (`N/A`) en el PDF final enviado al usuario.

### 2.5 Manejo de Fechas y Saldos
*   **Saldo Actualizado al Guardar:** Se re-consulta `obtener_saldo_actual()` justo antes de escribir en Excel, previniendo cálculos incorrectos si otro usuario guardó una operación entre el envío de la imagen y la confirmación.
*   **Fecha por Defecto:** Si el LLM no detecta la fecha en el comprobante, se usa automáticamente la fecha actual de Perú (UTC-5). El usuario la ve en el resumen y puede editarla.
*   **Toggle de Formato PE/USA:** La opción 4 del menú de confirmación alterna entre DD/MM/YYYY y MM/DD/YYYY de forma reversible.
*   **Variable `FORMATO_FECHA_EXCEL`:** Variable de entorno (por defecto `PE`) que define el formato base de fecha para el parseo interno del código. Configurable desde Render sin tocar código. Solo cambiar a `US` si la región del Excel Online está en inglés.

### 2.6 Power BI (Visualización)
*   **Migración de Origen de Datos:** Se reemplazó el origen de datos local en Power Query (`C:\Users\...`) por una conexión Web hacia la ruta absoluta del documento en SharePoint.
*   **Eliminación de Gateway Local:** Al apuntar directamente a la nube de Microsoft, se eliminó la dependencia de un "Personal Gateway" instalado en una máquina física.
*   **Actualización Programada:** Se configuraron credenciales OAuth2 (Nivel Organizacional) en Power BI Service. Se programó el modelo semántico para ejecutar actualizaciones autónomas y periódicas (ej. diaria a la 1:00 a.m.), obteniendo la data de SharePoint sin intervención manual.

---

## 3. Trazabilidad de Configuración de Accesos (Microsoft Entra ID)
Para permitir que el servidor en Python se comunique e inyecte datos autónomamente en el Excel de SharePoint a través de Microsoft Graph API, se realizó la siguiente configuración de infraestructura en la nube de Microsoft:

1.  **Registro de Aplicación (App Registration):** Se registró una aplicación en el Centro de Administración de Microsoft Entra llamada `Tesoreria-chatbot-api`.
2.  **Autenticación y Credenciales:** Se generó un *Secreto de cliente* (Client Secret) para habilitar el flujo de credenciales de cliente (Client Credentials flow). Esto permite la autenticación de tipo servidor a servidor.
3.  **Gestión de Permisos (Graph API):** Durante las pruebas con Graph Explorer, se identificó que la inserción de datos arrojaba un error de autorización (HTTP 403 Forbidden). Para solucionarlo, se asignaron permisos de aplicación en Microsoft Graph, específicamente los de escritura y lectura de archivos/sitios (ej. `Files.ReadWrite.All` o `Sites.ReadWrite.All`).
4.  **Consentimiento de Administrador (Admin Consent):** Finalmente, se otorgó el "Consentimiento de administrador en nombre de la organización" a los permisos solicitados. Este paso crítico autoriza a la aplicación a editar el archivo de Excel en SharePoint sin requerir que un usuario inicie sesión de forma interactiva.
