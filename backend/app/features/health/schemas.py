from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List

class ComponentStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    status: str
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    status: str
    timestamp: datetime
    version: str
    components: Optional[List[ComponentStatus]] = None
