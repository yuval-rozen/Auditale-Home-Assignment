from pydantic import BaseModel
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

class CustomerOut(BaseModel):
    id: int
    name: str
    segment: str
    health_score: float
    model_config = ConfigDict(from_attributes=True)

class HealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    factors: Dict[str, float]
    weights: Dict[str, float]
    healthScore: float

class EventIn(BaseModel):
    type: str
    timestamp: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

