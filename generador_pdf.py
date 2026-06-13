import os
from fpdf import FPDF

def generar_comprobante_pdf(datos: dict, ruta_salida: str) -> str:
    ruta_plantilla = "plantilla.html"
    if not os.path.exists(ruta_plantilla): raise FileNotFoundError(f"Error: {ruta_plantilla}")

    with open(ruta_plantilla, "r", encoding="utf-8") as archivo:
        html_texto = archivo.read()

    campos_requeridos = [
        "codigo", "fecha", "nro_operacion_dia", "concepto", "tipo", 
        "motivo", "acreedor", "deudor", "estado", "ingreso_final", 
        "egreso_final", "saldo", "ruc", "proveedor", "fecha_registro"
    ]
    
    for campo in campos_requeridos:
        valor = str(datos.get(campo, "N/A"))
        html_texto = html_texto.replace(f"{{{{{campo}}}}}", valor)

    pdf = FPDF()
    pdf.add_page()
    pdf.write_html(html_texto)
    pdf.output(ruta_salida)
    
    return ruta_salida
