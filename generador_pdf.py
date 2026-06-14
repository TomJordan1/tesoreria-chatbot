import os
from fpdf import FPDF

def generar_comprobante_pdf(datos: dict, ruta_salida: str, ruta_imagen: str = None) -> str:
    """
    Lee la plantilla HTML de Tesorería, inyecta las variables cruzadas
    y genera el archivo PDF local. Si se envía una imagen, la adjunta en una 2da página.
    """
    ruta_plantilla = "plantilla.html"
    
    if not os.path.exists(ruta_plantilla):
        raise FileNotFoundError(f"Error: {ruta_plantilla}")

    with open(ruta_plantilla, "r", encoding="utf-8") as archivo:
        html_texto = archivo.read()

    # Campos requeridos a inyectar
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
    
    # --- CARGA DE LA FUENTE ARIAL REAL ---
    archivos_fuente_existen = (
        os.path.exists("arial.ttf") and 
        os.path.exists("arialbd.ttf") and 
        os.path.exists("ariali.ttf")
    )
    
    if archivos_fuente_existen:
        pdf.add_font("Arial", "", "arial.ttf")      
        pdf.add_font("Arial", "B", "arialbd.ttf")   
        pdf.add_font("Arial", "I", "ariali.ttf")    
        pdf.set_font("Arial", size=11)
    else:
        print("🐂⚠️ Aviso de Toribio: No encontré los archivos .ttf de Arial. Usaré Helvetica temporalmente.")
        pdf.set_font("helvetica", size=11)
        
    pdf.write_html(html_texto)
    
    # --- NUEVA LÓGICA: SEGUNDA PÁGINA PARA LA FOTO ---
    if ruta_imagen and os.path.exists(ruta_imagen):
        pdf.add_page()
        
        # Título centrado para la evidencia
        if archivos_fuente_existen:
            pdf.set_font("Arial", style="B", size=14)
        else:
            pdf.set_font("helvetica", style="B", size=14)
            
        pdf.cell(0, 10, "Evidencia Adjunta", ln=True, align="C")
        pdf.ln(5)
        
        # Insertar imagen. x=20 la centra aproximadamente, w=170 la ajusta al ancho A4
        try:
            pdf.image(ruta_imagen, x=45, w=120)
        except Exception as e:
            print(f"Error al estampar la imagen con mis pezuñas: {e}")
            if archivos_fuente_existen:
                pdf.set_font("Arial", style="I", size=11)
            else:
                pdf.set_font("helvetica", style="I", size=11)
            pdf.cell(0, 10, "Ocurrió un error al cargar la imagen original.", ln=True, align="C")
            
    pdf.output(ruta_salida)
    
    return ruta_salida
