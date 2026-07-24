from datetime import datetime
from pydantic import BaseModel ,Field

class JobProgress(BaseModel):
    job_id:str=Field(description="Unique processing job identifier")
    status:str=Field(examples=["queued","extracting","analyzing","summarizing","done"])
    progress:int=Field(ge=0,le=100,examples=[25])
    timestamp:datetime
    