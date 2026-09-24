"""
Labeling Service — Business logic สำหรับจัดการ Label Studio projects & tasks
"""

import logging

from fastapi import HTTPException, status

from core.label_studio_client import get_client

logger = logging.getLogger(__name__)


def _get_ls_client():
    """สร้าง Label Studio client — raise 503 ถ้าเชื่อมต่อไม่ได้"""
    try:
        return get_client()
    except Exception as e:
        logger.error(f"Failed to initialize Label Studio client: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Label Studio client is not available.",
        )


def list_projects() -> list[dict]:
    """ดึงรายการ project ทั้งหมดจาก Label Studio"""
    try:
        ls = _get_ls_client()
        projects = ls.projects.list()

        items = list(projects) if not isinstance(projects, list) else projects

        result = []
        for p in items:
            if isinstance(p, dict):
                result.append(p)
            else:
                result.append({
                    "id": getattr(p, "id", None),
                    "title": getattr(p, "title", ""),
                    "description": getattr(p, "description", None),
                    "task_count": getattr(p, "task_number", None),
                    "created_at": str(getattr(p, "created_at", "")) if getattr(p, "created_at", None) else None,
                })
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def create_project(title: str, description: str | None = None, label_config: str | None = None) -> dict:
    """สร้าง project ใหม่ใน Label Studio"""
    try:
        ls = _get_ls_client()
        project = ls.projects.create(
            title=title,
            description=description,
            label_config=label_config,
        )
        if isinstance(project, dict):
            return project
        return {
            "id": getattr(project, "id", None),
            "title": getattr(project, "title", ""),
            "description": getattr(project, "description", None),
            "label_config": getattr(project, "label_config", None),
            "task_number": getattr(project, "task_number", None),
            "created_at": str(getattr(project, "created_at", "")) if getattr(project, "created_at", None) else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def get_project(project_id: int) -> dict:
    """ดึงรายละเอียด project ตาม ID"""
    try:
        ls = _get_ls_client()
        project = ls.projects.get(id=project_id)
        if isinstance(project, dict):
            return project
        return {
            "id": getattr(project, "id", None),
            "title": getattr(project, "title", ""),
            "description": getattr(project, "description", None),
            "label_config": getattr(project, "label_config", None),
            "task_number": getattr(project, "task_number", None),
            "created_at": str(getattr(project, "created_at", "")) if getattr(project, "created_at", None) else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found.")


def delete_project(project_id: int) -> None:
    """ลบ project ออกจาก Label Studio"""
    try:
        ls = _get_ls_client()
        ls.projects.delete(id=project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def list_tasks(project_id: int) -> list[dict]:
    """ดึงรายการ task ทั้งหมดใน project"""
    try:
        ls = _get_ls_client()
        tasks = ls.tasks.list(project=project_id)

        items = list(tasks) if not isinstance(tasks, list) else tasks

        result = []
        for t in items:
            if isinstance(t, dict):
                result.append(t)
            else:
                result.append({
                    "id": getattr(t, "id", None),
                    "data": getattr(t, "data", {}),
                    "annotations_count": len(getattr(t, "annotations", [])) if hasattr(t, "annotations") else 0,
                })
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tasks for project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def import_tasks(project_id: int, tasks: list[dict]) -> int:
    """นำเข้า tasks แบบ batch เข้า project"""
    try:
        ls = _get_ls_client()
        ls.projects.import_tasks(id=project_id, request=tasks)
        return len(tasks)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing tasks to project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
