from pydantic import BaseModel

class CustomerOut(BaseModel):
    id: int
    name: str
    segment: str
    health_score: float

    class Config:
        orm_mode = True
