# models.py
from pydantic import BaseModel

class Evento(BaseModel):
    nombre: str
    descripcion: str
    fecha: str

class Asistente(BaseModel):
    nombre: str
    email: str
    evento_id: int

class EventoInDB(Evento):
    id: int
