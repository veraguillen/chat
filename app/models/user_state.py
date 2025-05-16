# app/models/user_state.py
from sqlalchemy import String, DateTime, func, Integer, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.core.database import Base # Asumiendo que Base está aquí
from datetime import datetime # ### CORRECCIÓN ### Importar datetime directamente
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .scheduling_models import Company

class UserState(Base):
    __tablename__ = "user_states"

    # --- Clave Primaria Compuesta ---
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True) 
    platform: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, default="whatsapp")
    # __table_args__ = (UniqueConstraint('user_id', 'platform', name='uq_user_platform'),) # Implícito con PK compuesta

    # --- Campo de Suscripción ---
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Relación con Company ---
    current_brand_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('companies.id', name='fk_user_states_company_id', ondelete='SET NULL'), 
        index=True, 
        nullable=True
    )
    company: Mapped[Optional["Company"]] = relationship(
        "Company",
        # foreign_keys=[current_brand_id], # Opcional si no hay ambigüedad
        back_populates="user_states",
        lazy="selectin"
    )
    
    # --- Estado del Flujo ---
    stage: Mapped[str] = mapped_column(String(100), default="selecting_brand", index=True, nullable=False)

    # --- Campos de Información Recolectada ---
    collected_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collected_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    collected_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purpose_of_inquiry: Mapped[Optional[str]] = mapped_column(Text, nullable=True) 
    location_info: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # --- Timestamps ---
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"<UserState(user_id='{self.user_id}', platform='{self.platform}', stage='{self.stage}', subscribed={self.is_subscribed})>"