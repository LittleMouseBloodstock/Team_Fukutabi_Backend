from pydantic import BaseModel, Field

class DestinationBase(BaseModel):
    placeId: str = Field(..., description="Google Place ID")
    name: str
    address: str
    lat: float
    lng: float

class DestinationCreate(DestinationBase):
    pass

class DestinationRead(DestinationBase):
    id: str

class DestinationBrief(BaseModel):
    placeId: str
    name: str