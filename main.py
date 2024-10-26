from fastapi import FastAPI, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime 
from fastapi.middleware.cors import CORSMiddleware
from db import get_db  
from models import Evento, Asistente, EventoInDB  
from utils import generar_qr_base64, enviar_correo_html, enviar_correo_confirmacion  

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Endpoint para obtener todos los eventos
@app.get("/eventos/", response_model=List[EventoInDB])
async def obtener_eventos(db=Depends(get_db)):
    query = "SELECT id, nombre, descripcion, fecha FROM eventos"
    eventos = await db.fetch(query)
    
    # Convertimos la fecha a string antes de devolverla
    eventos_format = [
        {
            "id": evento["id"],
            "nombre": evento["nombre"],
            "descripcion": evento["descripcion"],
            "fecha": str(evento["fecha"])  # Convertir fecha a string
        }
        for evento in eventos
    ]
    return eventos_format


# Endpoint para crear un evento
@app.post("/eventos/", response_model=EventoInDB)
async def crear_evento(evento: Evento, db=Depends(get_db)):
    """
    Crea un nuevo evento y lo guarda en la base de datos.
    """
    # Convertimos la fecha del evento a un objeto datetime.date
    fecha = datetime.strptime(evento.fecha, "%Y-%m-%d").date()  # <-- Corrección aquí

    # Query para insertar el evento
    query = """
    INSERT INTO eventos (nombre, descripcion, fecha) 
    VALUES ($1, $2, $3) RETURNING *
    """
    nuevo_evento = await db.fetchrow(query, evento.nombre, evento.descripcion, fecha)

    # Devolvemos el evento creado con la fecha en formato string
    return {**nuevo_evento, "fecha": str(nuevo_evento["fecha"])}


# Endpoint para actualizar un evento existente
@app.put("/eventos/{evento_id}", response_model=EventoInDB)
async def actualizar_evento(evento_id: int, evento: Evento, db=Depends(get_db)):
    """
    Actualiza los datos de un evento por su ID.
    """
    # Convertimos la fecha a un objeto datetime.date
    fecha = datetime.strptime(evento.fecha, "%Y-%m-%d").date()

    # Query para actualizar el evento
    query = """
    UPDATE eventos 
    SET nombre = $1, descripcion = $2, fecha = $3 
    WHERE id = $4 RETURNING *
    """
    evento_actualizado = await db.fetchrow(query, evento.nombre, evento.descripcion, fecha, evento_id)

    if not evento_actualizado:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    # Devolvemos el evento actualizado con la fecha en formato string
    return {**evento_actualizado, "fecha": str(evento_actualizado["fecha"])}

# Endpoint para eliminar un evento
@app.delete("/eventos/{evento_id}")
async def eliminar_evento(evento_id: int, db=Depends(get_db)):
    """
    Elimina un evento por su ID.
    """
    query = "DELETE FROM eventos WHERE id = $1"
    resultado = await db.execute(query, evento_id)

    if resultado == "DELETE 0":
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return {"detail": "Evento eliminado correctamente"}

# Endpoint para registrar asistentes y enviar QR por correo
@app.post("/asistentes/")
async def registrar_asistente(asistente: Asistente, db=Depends(get_db)):
    """
    Registra un asistente, genera un QR y lo envía por correo.
    """
    # Aquí generamos un QR a partir del email del asistente y el evento_id
    qr_data = f"{asistente.email}"
    
    # Llamada correcta a `generar_qr_base64` con ambos parámetros
    qr_base64 = generar_qr_base64(qr_data, asistente.evento_id)

    # Resto de la lógica de registro del asistente
    query = """
    INSERT INTO asistentes (nombre, email, evento_id, qr_code)
    VALUES ($1, $2, $3, $4) RETURNING *
    """
    asistente_registrado = await db.fetchrow(query, asistente.nombre, asistente.email, asistente.evento_id, f"{asistente.email}-{asistente.evento_id}")

    if not asistente_registrado:
        raise HTTPException(status_code=400, detail="No se pudo registrar al asistente")

    # Obtener el nombre del evento para el correo
    nombre_evento = await db.fetchval("SELECT nombre FROM eventos WHERE id = $1", asistente.evento_id)

    # Enviar el correo con el QR
    await enviar_correo_html(
        asistente.email,
        asistente.nombre,
        nombre_evento,
        asistente.evento_id,
        qr_base64
    )

    return {"detail": "Registro exitoso, correo enviado."}


# Endpoint para obtener todos los asistentes
@app.get("/asistentes/", response_model=List[dict])
async def obtener_asistentes(db=Depends(get_db)):
    query = "SELECT * FROM asistentes"
    asistentes = await db.fetch(query)
    return [dict(asistente) for asistente in asistentes]  # Convertimos a dict para devolver en JSON

# Endpoint para obtener asistentes por evento
@app.get("/asistentes/evento/{evento_id}", response_model=List[dict])
async def obtener_asistentes_por_evento(evento_id: int, db=Depends(get_db)):
    query = "SELECT * FROM asistentes WHERE evento_id = $1"
    asistentes = await db.fetch(query, evento_id)

    if not asistentes:
        raise HTTPException(status_code=404, detail="No se encontraron asistentes para este evento")

    return [dict(asistente) for asistente in asistentes]

# Endpoint para eliminar un asistente con opción de confirmación
@app.delete("/asistentes/{email}")
async def eliminar_asistente(
    email: str,
    evento_id: Optional[int] = Query(None, description="ID del evento del que se quiere eliminar al asistente"),
    eliminar_todo: bool = Query(False, description="¿Eliminar al asistente de todos los eventos?"),
    db=Depends(get_db)
):
    # Verificar si el asistente existe
    query_verificar = "SELECT * FROM asistentes WHERE email = $1"
    asistente = await db.fetchrow(query_verificar, email)

    if not asistente:
        raise HTTPException(status_code=404, detail="El asistente no existe")

    if eliminar_todo:
        # Eliminar al asistente de todos los eventos
        query_eliminar_todo = "DELETE FROM asistentes WHERE email = $1"
        await db.execute(query_eliminar_todo, email)
        return {"detail": f"El asistente con email {email} fue eliminado de todos los eventos."}
    
    elif evento_id is not None:
        # Eliminar al asistente solo del evento específico
        query_eliminar_evento = "DELETE FROM asistentes WHERE email = $1 AND evento_id = $2"
        resultado = await db.execute(query_eliminar_evento, email, evento_id)

        if resultado == "DELETE 0":
            raise HTTPException(status_code=404, detail="El asistente no está registrado en este evento")

        return {"detail": f"El asistente con email {email} fue eliminado del evento {evento_id}."}

    else:
        raise HTTPException(
            status_code=400,
            detail="Debes indicar un evento o confirmar la eliminación de todos los eventos."
        )

# Endpoint para confirmar asistencia mediante QR
@app.get("/asistentes/confirmar/{qr_code}")
async def confirmar_asistencia(qr_code: str, db=Depends(get_db)):
    query = """
    UPDATE asistentes
    SET confirmado = TRUE
    WHERE qr_code = $1 AND confirmado = FALSE
    RETURNING *
    """
    asistente = await db.fetchrow(query, qr_code)

    if not asistente:
        raise HTTPException(status_code=404, detail="QR inválido o ya confirmado")

    # Suponemos que tienes el nombre del evento guardado y se puede acceder así:
    nombre_evento = await db.fetchval(
        "SELECT nombre FROM eventos WHERE id = $1", asistente["evento_id"]
    )

    # Llamada a la función corregida con los argumentos adecuados
    await enviar_correo_confirmacion(
        asistente["email"], nombre_evento, asistente["evento_id"]
    )

    return {"detail": "Asistencia confirmada. Correo enviado."}

