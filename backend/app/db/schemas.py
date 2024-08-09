from pydantic import BaseModel

class DataCreate(BaseModel):
    volume: float
    oi_change: float
    oi: float
    ltp: float
    strike_price: float
    type: str  # 'CALL' or 'PUT'
