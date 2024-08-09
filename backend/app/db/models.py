from sqlalchemy import Column, Integer, Float, String
from .database import Base

class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True, index=True)
    volume = Column(Float)
    oi_change = Column(Float)
    oi = Column(Float)
    ltp = Column(Float)
    strike_price = Column(Float)
    type = Column(String(255))
