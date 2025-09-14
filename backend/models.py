"""
SQLAlchemy ORM models for the Customer Health app.

These tables capture customer entities and their related activity:
- Customer: core entity with segment and creation date
- Event: audit trail of activities (login, API call, feature use, etc.)
- Invoice: billing records with due/paid dates
- SupportTicket: customer support cases
- FeatureUsage: adoption of product features

Relationships are bidirectional with cascades for clean deletion.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Customer(Base):
    """Customer entity with segment, health placeholder, and related activity."""
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    segment = Column(String, nullable=False, default="SMB")
    health_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    events = relationship("Event", back_populates="customer", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan")
    tickets = relationship("SupportTicket", back_populates="customer", cascade="all, delete-orphan")
    features = relationship("FeatureUsage", back_populates="customer", cascade="all, delete-orphan")

class Event(Base):
    """Generic audit event: login, API call."""
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    type = Column(String, nullable=False)           # login | api_call | feature_used | ticket_opened | payment
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    meta = Column(JSON, nullable=True)

    customer = relationship("Customer", back_populates="events")

class Invoice(Base):
    """Billing record with due date, payment date, and amount."""
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    due_date = Column(DateTime, nullable=False)
    paid_date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=False, default=0.0)

    customer = relationship("Customer", back_populates="invoices")

class SupportTicket(Base):
    """Support case tied to a customer (open/closed)."""
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    status = Column(String, nullable=False, default="open")  # open | closed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="tickets")

class FeatureUsage(Base):
    """Record of a customer using a specific feature at a point in time."""
    __tablename__ = "feature_usage"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    feature_name = Column(String, nullable=False)
    used_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="features")
