# Documentación de Arquitectura e Integración (v2.0)

Este documento detalla la arquitectura técnica actual del sistema de tesorería y registra los cambios implementados para la migración de un flujo manual/local a un entorno completamente integrado en la nube (Telegram + SharePoint + Power BI).

## 1. Arquitectura del Sistema
El sistema se compone de cuatro nodos principales que interactúan de forma secuencial:

1. **Interfaz de Usuario (Telegram):** Punto de entrada. Los usuarios envían comprobantes fotográficos e instrucciones textuales al bot (Toribio).
2. **Motor de Procesamiento (FastAPI + Groq LLM):** El servidor en Render recibe los webhooks de Telegram. Si hay una imagen, se utiliza la API de Groq para extraer el texto y clasificar los datos en un esquema JSON estructurado.
3. **Base de Datos (Excel en SharePoint):** Repositorio central de datos (`REGISTRODIARIO3`). El backend de Python se comunica con Excel usando la API de Microsoft Graph para insertar y leer filas.
4. **Visualización (Power BI):** El modelo semántico alojado en Power BI Service se conecta directamente al archivo de SharePoint mediante una URL web, actualizando los dashboards de forma programada.

> [!WARNING]
> **Aclaración sobre Integración:** Se identificó que otras partes de la documentación (`readme.md` y guías de instalación) mencionan el uso de webhooks hacia **Power Automate** con la variable `POWER_AUTOMATE_URL`. Sin embargo, la arquitectura real y actual implementada en el código backend (`servicios.py`) realiza una conexión **directa** a Microsoft Graph API (usando `msal` y Client Credentials), ofreciendo una integración más veloz, segura y sin depender de servicios puente como Power Automate.

---

## 2. Registro de Cambios y Actualizaciones

A continuación se detallan las modificaciones realizadas respecto a la versión anterior del sistema.

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

### 2.3 Generación de PDF (Comprobantes)
*   **Limpieza de Variables Residuales:** Se eliminaron las variables `proveedor`, `ruc` y `fecha_registro` de la lista de campos requeridos en `generador_pdf.py`. Operativamente, el campo `acreedor` cubre la función de identificar al proveedor comercial.
*   **Ajuste de Plantilla HTML:** Se eliminó la etiqueta de tabla (`<tr>`) correspondiente al Proveedor Comercial en `plantilla.html` para evitar la impresión de celdas vacías (`N/A`) en el PDF final enviado al usuario.

### 2.4 Power BI (Visualización)
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
