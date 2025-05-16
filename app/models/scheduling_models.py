# app/models/scheduling_models.py
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, func,
    Boolean, Index # Index no se usa explícitamente si `index=True` está en mapped_column
)
# --- CORRECCIÓN: Importar Mapped y relationship ---
from sqlalchemy.orm import relationship, Mapped, mapped_column # Correcto
# -------------------------------------------------
from sqlalchemy.sql import expression # Para server_default=expression.false()
import datetime # Usado para type hints en Mapped
from typing import List, Optional, TYPE_CHECKING # Añadido Optional y List

# Intenta importar Base de la ubicación centralizada.
# Si falla (ej. al generar migraciones o en un contexto donde app.core no es accesible),
# usa un Base declarativo local.
try:
    from app.core.database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base # Correcto para fallback
    Base = declarative_base()

# --- Type Hinting para evitar importación circular con UserState ---
if TYPE_CHECKING:
    from .user_state import UserState # UserState usa Company
    # No es necesario redefinir Interaction y Appointment aquí si sus modelos
    # están en el mismo archivo o ya se importaron de alguna manera.
    # Si `user_state` también necesitara `Interaction` o `Appointment`,
    # se añadirían aquí.

class Company(Base):
    """Modelo para las Empresas/Marcas que el chatbot puede representar."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False) # `name` no debería ser nullable

    # Relaciones inversas: una compañía puede tener muchos estados de usuario, interacciones y citas.
    user_states: Mapped[List["UserState"]] = relationship(back_populates="company")
    
    # Si una compañía se elimina, todas sus interacciones asociadas se eliminarán.
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction", 
        back_populates="company", 
        cascade="all, delete-orphan" # Correcto si las interacciones dependen completamente de la compañía
    )
    
    # Si una compañía se elimina, las citas no se eliminarán automáticamente (RESTRICT por defecto si no se especifica ondelete en FK)
    # o fallará la eliminación si hay citas (si el FK en Appointment tiene ON DELETE RESTRICT).
    # Considerar el comportamiento deseado.
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="company")

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name='{self.name}')>"

class Interaction(Base):
    """
    Modelo para registrar interacciones significativas del usuario,
    especialmente aquellas que podrían llevar a una acción como una cita o una consulta RAG.
    Con el flujo simplificado de Calendly, una "Interaction" podría registrar
    el momento en que un usuario solicita información de agendamiento.
    """
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_wa_id: Mapped[str] = mapped_column(String, index=True, nullable=False) # ID de usuario no debería ser nullable
    platform: Mapped[str] = mapped_column(String(50), default='whatsapp', nullable=False)
    
    # Datos del usuario (estos podrían seguir siendo útiles si se recolectan por otros motivos o antes)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # A qué compañía/marca pertenece esta interacción
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('companies.id', ondelete='SET NULL'), # Si la compañía se borra, company_id se vuelve NULL
        index=True, 
        nullable=True # Permitir interacciones sin compañía asociada (ej. al inicio)
    )
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), # Generado por la base de datos
        nullable=False
    )

    # Relaciones
    company: Mapped[Optional["Company"]] = relationship(back_populates="interactions")
    
    # Una interacción puede (o no) llevar a una cita.
    # Si la interacción se elimina, la cita asociada también se eliminará.
    # Con el nuevo flujo, la creación de 'Appointment' es menos directa desde el bot.
    # Este modelo 'Appointment' podría usarse si importas eventos de Calendly vía webhooks.
    appointment: Mapped[Optional["Appointment"]] = relationship(
        back_populates="interaction", 
        uselist=False, # Una interacción tiene como máximo una cita directa
        cascade="all, delete-orphan" # Si la interacción se borra, la cita también
    )

    def __repr__(self) -> str:
        return f"<Interaction(id={self.id}, user_wa_id='{self.user_wa_id}', company_id={self.company_id}, created_at='{self.created_at}')>"

class Appointment(Base):
    """
    Modelo para las citas agendadas.
    Con el flujo simplificado de Calendly, este modelo se llenaría idealmente
    a través de webhooks de Calendly que notifiquen la creación/cancelación de citas,
    en lugar de ser creado directamente por el bot.
    """
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Clave foránea a Interaction: cada cita debe estar vinculada a una interacción.
    # Si la interacción se elimina, la cita también (CASCADE).
    interaction_id: Mapped[Optional[int]] = mapped_column( # Hacer opcional si una cita puede existir sin interacción previa directa del bot
        ForeignKey('interactions.id', ondelete='CASCADE'), 
        unique=True, # Una interacción solo puede tener una cita (si appointment es uselist=False en Interaction)
        index=True,
        nullable=True # Cambiar a False si una cita SIEMPRE debe originarse de una interacción registrada por el bot.
                      # Si las citas se crean vía webhooks de Calendly, podría no haber una `interaction_id` del bot.
    )
    
    # A qué compañía pertenece esta cita.
    # ON DELETE RESTRICT significa que no se puede borrar una compañía si tiene citas.
    # Considera SET NULL si quieres mantener la cita pero desvincularla de una compañía borrada.
    company_id: Mapped[Optional[int]] = mapped_column( # Hacer opcional si una cita puede existir sin compañía
        ForeignKey('companies.id', ondelete='SET NULL'), # O RESTRICT si es mandatorio
        index=True,
        nullable=True # Cambiar a False si una cita SIEMPRE debe tener una compañía.
    )
    
    # URIs de Calendly para referencia
    calendly_event_uri: Mapped[str] = mapped_column(Text, nullable=False) # URI del tipo de evento de Calendly
    calendly_invitee_uri: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True) # URI único del invitado/cita en Calendly

    # Detalles de la cita
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default='scheduled', index=True, nullable=False) # Ej: 'scheduled', 'cancelled'
    
    # Para seguimiento de recordatorios
    reminder_sent: Mapped[bool] = mapped_column(
        Boolean, 
        server_default=expression.false(), # Por defecto es False
        nullable=False,
        index=True
    )

    # Relaciones
    # Si interaction_id es nullable=True, esta relación también debe ser Optional.
    interaction: Mapped[Optional["Interaction"]] = relationship(back_populates="appointment")
    
    # Si company_id es nullable=True, esta relación también debe ser Optional.
    company: Mapped[Optional["Company"]] = relationship(back_populates="appointments")

    def __repr__(self) -> str:
        return (f"<Appointment(id={self.id}, invitee_uri='{self.calendly_invitee_uri}', "
                f"start='{self.start_time}', status='{self.status}')>")