import os
from fpdf import FPDF

def generar_comprobante_pdf(datos: dict, ruta_salida: str) -> str:
    """
    Lee un archivo HTML externo, inyecta los datos del diccionario y 
    lo convierte en un PDF usando el motor HTML de FPDF2.
    """
    # 1. Leer el diseño desde el archivo externo
    ruta_plantilla = "plantilla.html"
    
    if not os.path.exists(ruta_plantilla):
        raise FileNotFoundError(f"No se encontró el archivo de diseño: {ruta_plantilla}")

    with open(ruta_plantilla, "r", encoding="utf-8") as archivo:
        html_texto = archivo.read()

    # 2. Reemplazar las etiquetas {{campo}} con los valores reales
    # Por defecto, si un dato no existe, ponemos "N/A"
    campos_requeridos = [
        "id", "fecha_registro", "comprador", "proyecto", "categoria_gasto", 
        "ruc", "proveedor", "fecha", "monto", "estado_reembolso"
    ]
    
    for campo in campos_requeridos:
        valor = str(datos.get(campo, "N/A"))
        html_texto = html_texto.replace(f"{{{{{campo}}}}}", valor)

    # 3. Generar el PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Escribir el HTML transformado dentro del PDF
    pdf.write_html(html_texto)
    
    # 4. Guardar en el disco duro local
    pdf.output(ruta_salida)
    
    return ruta_salida