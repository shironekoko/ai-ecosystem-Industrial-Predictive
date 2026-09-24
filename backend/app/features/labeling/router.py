"""
Labeling Router — API endpoints สำหรับจัดการ Label Studio projects & tasks
"""

from fastapi import APIRouter

from . import schemas, service

router = APIRouter(prefix="/labeling", tags=["Labeling (Label Studio)"])


@router.get(
    "/projects",
    response_model=schemas.ProjectListResponse,
    summary="ดึงรายการโปรเจกต์ทั้งหมด",
    description="ดึงรายการโปรเจกต์ทั้งหมดที่มีอยู่ใน Label Studio",
)
def get_projects():
    projects = service.list_projects()
    return schemas.ProjectListResponse(projects=projects, total=len(projects))


@router.post(
    "/projects",
    response_model=schemas.ProjectDetailResponse,
    summary="สร้างโปรเจกต์ใหม่",
    description="สร้างโปรเจกต์สำหรับ labeling ใหม่ โดยกำหนด title และ label_config",
)
def create_project(request: schemas.CreateProjectRequest):
    project = service.create_project(
        title=request.title,
        description=request.description,
        label_config=request.label_config,
    )
    return project


@router.get(
    "/projects/{project_id}",
    response_model=schemas.ProjectDetailResponse,
    summary="ดึงข้อมูลโปรเจกต์",
    description="ดึงรายละเอียดโปรเจกต์ตาม ID ที่ระบุ",
)
def get_project(project_id: int):
    return service.get_project(project_id)


@router.delete(
    "/projects/{project_id}",
    response_model=schemas.MessageResponse,
    summary="ลบโปรเจกต์",
    description="ลบโปรเจกต์ออกจาก Label Studio",
)
def delete_project(project_id: int):
    service.delete_project(project_id)
    return schemas.MessageResponse(message=f"Project {project_id} deleted successfully.")


@router.get(
    "/projects/{project_id}/tasks",
    response_model=schemas.TaskListResponse,
    summary="ดึงรายการ Tasks ในโปรเจกต์",
    description="ดึงรายการ task ทั้งหมดที่อยู่ในโปรเจกต์ที่ระบุ",
)
def get_tasks(project_id: int):
    tasks = service.list_tasks(project_id)
    return schemas.TaskListResponse(project_id=project_id, tasks=tasks, total=len(tasks))


@router.post(
    "/projects/{project_id}/tasks",
    response_model=schemas.MessageResponse,
    summary="นำเข้า Tasks แบบกลุ่ม",
    description="นำเข้าข้อมูล task เข้าสู่โปรเจกต์เพื่อการ label",
)
def create_tasks(project_id: int, request: schemas.CreateTasksRequest):
    count = service.import_tasks(project_id, request.tasks)
    return schemas.MessageResponse(message=f"Successfully imported {count} tasks.")
