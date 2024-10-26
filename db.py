# db.py
from asyncpg import create_pool
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    """Establece una conexión con la base de datos PostgreSQL."""
    pool = await create_pool(DATABASE_URL)
    async with pool.acquire() as connection:
        yield connection
