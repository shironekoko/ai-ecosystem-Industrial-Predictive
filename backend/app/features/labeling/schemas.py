from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any

class ProjectSummary(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    task_count: Optional[int] = None
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class ProjectListResponse(BaseModel):
    projects: List[ProjectSummary]
    total: int

class CreateProjectRequest(BaseModel):
    title: str
    description: Optional[str] = None
    label_config: str

class ProjectDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    label_config: Optional[str] = None
    task_number: Optional[int] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TaskSummary(BaseModel):
    id: int
    data: Dict[str, Any]
    annotations_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class TaskListResponse(BaseModel):
    project_id: int
    tasks: List[TaskSummary]
    total: int

class CreateTaskRequest(BaseModel):
    data: Dict[str, Any]

class CreateTasksRequest(BaseModel):
    tasks: List[Dict[str, Any]]

class MessageResponse(BaseModel):
    message: str
