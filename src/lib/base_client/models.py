import time
from typing import Optional

from pydantic import BaseModel, Field


class QuarantineItem(BaseModel):
    data: Optional[dict] = None
    timestamp: float = Field(default_factory=time.time)


class LockItem(BaseModel):
    level: int = 0
    timestamp: float
