from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.sql import func
from database import Base

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Item:
    pass