# app/models/user_state.py

from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, Index
from app.core.database import Base
import datetime

class UserState(Base):
    __tablename__ = "user_states"

    user_id = Column(String, index=True, nullable=False)
    platform = Column(String, index=True, nullable=False)
    current_brand = Column(String(100), index=True, nullable=True)
    stage = Column(String(50), default="selecting_brand", index=True, nullable=False)
    last_interaction_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'platform', name='user_states_pk'),
    )

    def __repr__(self):
        return f"<UserState(id='{self.platform}:{self.user_id}', brand='{self.current_brand}', stage='{self.stage}')>"