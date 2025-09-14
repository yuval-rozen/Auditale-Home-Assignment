"""
Pydantic schemas for API input/output.

These classes define how data is serialized/deserialized between the API
and clients. They are used in FastAPI route definitions as response models
or request bodies.

Schemas:
- CustomerOut: lightweight customer record returned in listings.
- HealthOut: detailed derived health breakdown for a single customer.
- EventIn: request body for ingesting a new customer activity event.
"""

from pydantic import BaseModel
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

class CustomerOut(BaseModel):
    """Public customer view for GET /api/customers."""
    id: int
    name: str
    segment: str
    health_score: float
    model_config = ConfigDict(from_attributes=True)

class HealthOut(BaseModel):
    """Detailed health breakdown returned by GET /api/customers/{id}/health."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    factors: Dict[str, float]
    weights: Dict[str, float]
    healthScore: float

class EventIn(BaseModel):
    """Input schema for POST /api/customers/{id}/events."""
    type: str
    timestamp: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

