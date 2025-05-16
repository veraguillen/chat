# test.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv
import os
# from datetime import datetime # Ya no necesitamos datetime para el nombre de prueba

load_dotenv() 

DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL no encontrada en .env. Asegúrate de que el archivo .env exista en la raíz y contenga la variable.")
        return

    print(f"Conectando a la base de datos: {DATABASE_URL}")
    # Añadir echo=True temporalmente para ver las sentencias SQL que se ejecutan
    engine = create_async_engine(DATABASE_URL, echo=True) 

    async_session_factory = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        try:
            print("Iniciando transacción para actualizar nombres de compañías a versiones finales...")
            async with session.begin(): # Iniciar una transacción explícita
                # Nombres finales y limpios para las compañías
                final_company_names = {
                    1: 'Corporativo Ehécatl SA de CV',
                    2: 'Frente Estudiantil Social (FES)', # Asumiendo que este ya estaba bien, pero lo incluimos para asegurar
                    3: 'Fundación Desarrollemos México A.C.',
                    4: 'CONSULTOR: Javier Bazán',
                    5: 'Universidad para el Desarrollo Digital (UDD)' # Asumiendo que este ya estaba bien
                }

                for company_id, final_name in final_company_names.items():
                    print(f"Actualizando compañía ID {company_id} al nombre: '{final_name}'")
                    await session.execute(
                        text("UPDATE companies SET name = :new_name WHERE id = :company_id"),
                        {"new_name": final_name, "company_id": company_id}
                    )
            
            # El bloque 'async with session.begin()' hace commit automáticamente si no hay excepciones,
            # o rollback si las hay.
            print("Transacción de UPDATEs completada y (debería haberse) comiteado desde Python.")

            # Leer y mostrar los datos DE NUEVO para verificar la persistencia de los nombres finales
            print("\nVerificando nombres de compañías DESPUÉS de la actualización desde Python:")
            result = await session.execute(text("SELECT id, name FROM companies ORDER BY id;"))
            companies = result.fetchall()
            if companies:
                for company_id, company_name in companies:
                    print(f"  ID: {company_id}, Name: '{company_name}' (repr: {repr(company_name)})")
            else:
                print("No se encontraron compañías después de la actualización (esto sería inesperado).")
        
        except Exception as e:
            print(f"Error durante la actualización/verificación de la DB en Python: {e}")
            # El rollback es automático con session.begin() si ocurre una excepción dentro del bloque.
        finally:
            # No es estrictamente necesario cerrar la sesión aquí si se usa el context manager 'async with async_session_factory() as session:'
            # pero no hace daño y es explícito.
            await session.close() 
            
    # Cerrar todas las conexiones del pool del engine al finalizar el script.
    await engine.dispose() 
    print("\nScript de actualización y verificación de nombres de compañías finalizado.")

if __name__ == "__main__":
    asyncio.run(main())