# Acceso a Toribio desde Excel

La lista de personas habilitadas se administra en el mismo archivo de Excel de SharePoint que ya usa el bot (`MS_ITEM_ID`). No se necesitan nuevas variables de entorno en Render, claves, archivos de credenciales ni servicios de pago.

## Configuración inicial

1. Abre el Excel de SharePoint que contiene la tabla de movimientos. Crea una hoja adicional, por ejemplo `Accesos`.
2. Agrega los encabezados `telegram_id`, `nombre` y `activo`. Configura la columna `telegram_id` como **Texto** antes de pegar identificadores.
3. Selecciona los encabezados y al menos una fila de datos y usa **Insertar > Tabla**, indicando que tiene encabezados. No basta con escribir las celdas: debe ser una tabla de Excel.
4. En las opciones de diseño de la tabla, cambia su nombre a **`USUARIOS_AUTORIZADOS`**. Ese es el nombre de la tabla, independientemente del nombre de la hoja. Puedes dejar una fila vacía hasta obtener tu ID.
5. Despliega la versión del bot que incorpora este control. Mientras no haya usuarios activos, solo funcionará `/mi_id`.
6. Escribe `/mi_id` al bot y pega el identificador que devuelve en `telegram_id`. Escribe tu nombre y `Sí` en `activo`. Guarda los cambios en Excel y espera hasta dos minutos antes de volver a usar el bot.

Ejemplo con IDs ficticios:

| telegram_id | nombre | activo |
|---|---|---|
| 123456789 | Tom | Sí |
| 987654321 | Ana | No |

El identificador es el número que muestra `/mi_id`, no el teléfono ni el usuario `@nombre`. La columna `nombre` sirve para reconocer a cada persona; el permiso se decide por su ID y la columna `activo`. Se reconocen los encabezados independientemente de su orden, mayúsculas o espacios exteriores.

## Agregar o retirar personas

* **Alta:** la persona escribe `/mi_id`, te comparte el número y agregas una fila con su ID, nombre y `Sí`.
* **Baja:** cambia `activo` a `No` o elimina la fila. El cambio se aplica al renovar la lista, hasta dos minutos después en condiciones normales.
* **Valores admitidos:** `Sí`, `Si`, `TRUE` o `1` habilitan el acceso, sin distinguir mayúsculas y tolerando espacios exteriores. Otros valores, incluida una celda vacía, lo deshabilitan.
* **Duplicados:** evita repetir un ID; si tiene filas activas e inactivas, prevalece la inactiva.

## Respuestas de Toribio

Cualquier persona puede ejecutar `/mi_id`, incluso cuando no se logra leer Excel:

> Tu identificador de Telegram es: 123456789
>
> Compártelo con el equipo de tesorería para que puedan darte acceso. ¡Muu! 🐮

Si alguien no está habilitado, cualquier otro mensaje, foto o comando recibe:

> ¡Muu! Todavía no te conozco 🐮. Pídele al equipo de tesorería que te dé acceso. Escribe /mi_id y compárteles tu identificador.

Eso incluye ayuda, cancelación, registro y exportación de PDF de prueba. No se procesa la foto, no se consume cuota de Groq ni se modifica una sesión por mensajes de personas sin acceso. `/mi_id` tampoco altera una operación en curso. La identificación usa el remitente del mensaje, no el ID del chat o grupo.

## Caché y errores

La lista se lee mediante Microsoft Graph con las credenciales existentes y se conserva dos minutos en memoria. Si el proceso reinicia, se consulta de nuevo. Si la tabla no existe, sus encabezados son incorrectos o falla la consulta al vencer la caché, se descarta la lista vencida y se bloquea el uso del bot, excepto `/mi_id`. Se reintenta la lectura con el siguiente mensaje una vez transcurridos 30 segundos desde el fallo.

Si nadie puede entrar, comprueba el nombre de la tabla, los encabezados, el ID, la columna `activo` y la conexión existente a SharePoint. Una tabla vacía no autoriza a nadie. Los registros contables y el formato de la tabla de movimientos no se modifican al administrar accesos.

El control usa el ID de remitente recibido en el webhook. La verificación del origen de ese webhook mediante un secreto de Telegram sigue siendo una mejora pendiente; esta lista no autentica por sí sola las llamadas HTTP entrantes.

Referencia técnica de la lectura utilizada: [Microsoft Graph: rango de una tabla](https://learn.microsoft.com/en-us/graph/api/table-range?view=graph-rest-1.0).
