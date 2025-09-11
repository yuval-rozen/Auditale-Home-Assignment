from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from db import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    segment = Column(String, nullable=False, default="SMB")
    health_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
