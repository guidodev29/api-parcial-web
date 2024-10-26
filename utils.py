import qrcode
import io
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from fastapi import HTTPException
from email.message import EmailMessage

import aiosmtplib
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SERVER = os.getenv("EMAIL_SERVER")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
NGROK_URL = "https://64a6-190-62-85-81.ngrok-free.app"

def generar_qr_base64(email: str, evento_id: int) -> str:
    """
    Genera un QR que contiene la URL pública con el email y evento_id,
    y lo convierte a base64.
    """
    try:
        # Crear la URL que se codificará en el QR
        qr_data = f"{NGROK_URL}/asistentes/confirmar/{email}-{evento_id}"

        # Generar el código QR con los datos
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Convertir el QR a imagen
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Guardar la imagen en un buffer y convertirla a base64
        buffer = io.BytesIO()
        qr_image.save(buffer, format='PNG')
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode()

    except Exception as e:
        print(f"Error al generar QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def generar_plantilla_html(nombre: str, nombre_evento: str, evento_id: int) -> str:
    """
    Genera una plantilla HTML más vistosa con el QR como imagen CID.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>QR Code</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #f4f4f4;
                    font-family: 'Arial', sans-serif;
                }}
                .container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }}
                .content {{
                    background-color: #fff;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    padding: 40px;
                    text-align: center;
                    max-width: 500px;
                    margin: auto;
                }}
                h1 {{
                    color: #4CAF50;
                    font-size: 24px;
                    margin-bottom: 10px;
                }}
                p {{
                    color: #333;
                    font-size: 18px;
                    margin: 10px 0;
                }}
                .qr-code {{
                    margin-top: 20px;
                    margin-bottom: 20px;
                }}
                .footer {{
                    margin-top: 30px;
                    font-size: 14px;
                    color: #888;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="content">
                    <h1>¡Registro Exitoso, {nombre}!</h1>
                    <p>Gracias por registrarte en <strong>{nombre_evento}</strong>, evento con ID {evento_id}.</p>
                    <div class="qr-code">
                        <img src="cid:qr-code" 
                             alt="QR Code" 
                             style="width: 300px; height: 300px;" />
                    </div>
                    <p>¡Te esperamos y esperamos que disfrutes del evento!</p>
                    <div class="footer">
                        <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

def generar_plantilla_confirmacion(nombre: str, evento_id: int) -> str:
    """
    Genera una plantilla HTML más atractiva para la confirmación de asistencia.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmación de Asistencia</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 50px auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #4CAF50;
                text-align: center;
            }}
            p {{
                font-size: 16px;
                color: #333;
                text-align: center;
            }}
            .footer {{
                margin-top: 20px;
                text-align: center;
                color: #777;
                font-size: 14px;
            }}
            .button {{
                display: inline-block;
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                font-size: 16px;
                margin-top: 20px;
                border-radius: 5px;
            }}
            .button:hover {{
                background-color: #45a049;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>¡Asistencia Confirmada!</h1>
            <p>Gracias por confirmar tu asistencia al <strong>evento con ID: {evento_id}</strong>.</p>
            <p>Nos alegra contar contigo, {nombre}. Estamos ansiosos por verte en el evento.</p>
            <div style="text-align: center; margin-top: 20px;">
                <a href="#" class="button">Ver detalles del evento</a>
            </div>
            <div class="footer">
                <p>¡Te esperamos!</p>
                <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
            </div>
        </div>
    </body>
    </html>
    """


async def enviar_correo_html(email: str, nombre: str, nombre_evento: str, evento_id: int, qr_base64: str):
    """
    Envía el correo con un QR incrustado usando Content-ID.
    """
    try:
        # Crear el mensaje multipart
        mensaje = MIMEMultipart('related')
        mensaje['Subject'] = f'QR Code para {nombre}'
        mensaje['From'] = EMAIL_USER
        mensaje['To'] = email

        # Crear la parte HTML
        html_content = generar_plantilla_html(nombre, nombre_evento, evento_id)
        parte_html = MIMEText(html_content, 'html')
        mensaje.attach(parte_html)

        # Crear la imagen del QR
        qr_bytes = base64.b64decode(qr_base64)
        imagen_qr = MIMEImage(qr_bytes)
        imagen_qr.add_header('Content-ID', '<qr-code>')
        imagen_qr.add_header('Content-Disposition', 'inline')
        mensaje.attach(imagen_qr)

        # Enviar el correo
        await aiosmtplib.send(
            mensaje,
            hostname=EMAIL_SERVER,
            port=EMAIL_PORT,
            username=EMAIL_USER,
            password=EMAIL_PASSWORD,
            start_tls=True
        )
        
    except Exception as e:
        print(f"Error al enviar correo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def enviar_correo_confirmacion(email: str, nombre_evento: str, evento_id: int):
    """
    Envía un correo de confirmación de asistencia.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Confirmación de Asistencia</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 50px auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #4CAF50;
                text-align: center;
            }}
            p {{
                font-size: 16px;
                color: #333;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>¡Asistencia Confirmada!</h1>
            <p>Gracias por confirmar tu asistencia al <strong>{nombre_evento}</strong> (ID: {evento_id}).</p>
            <p>Nos alegra contar contigo. ¡Te esperamos!</p>
        </div>
    </body>
    </html>
    """

    mensaje = EmailMessage()
    mensaje["From"] = EMAIL_USER
    mensaje["To"] = email
    mensaje["Subject"] = "Confirmación de Asistencia"
    mensaje.add_alternative(html_content, subtype='html')

    # Enviar correo usando aiosmtplib
    try:
        await aiosmtplib.send(
            mensaje,
            hostname=EMAIL_SERVER,
            port=EMAIL_PORT,
            start_tls=True,
            username=EMAIL_USER,
            password=EMAIL_PASSWORD,
        )
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo enviar el correo de confirmación.")
