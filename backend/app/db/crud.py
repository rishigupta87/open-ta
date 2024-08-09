from sqlalchemy.orm import Session
from .models import Data
from .schemas import DataCreate

def create_data(db: Session, data: DataCreate):
    db_data = Data(
        volume=data.volume,
        oi_change=data.oi_change,
        oi=data.oi,
        ltp=data.ltp,
        strike_price=data.strike_price,
        type=data.type,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data
