from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
from .schemas import QCTargetResponse, BladeQCResponse, VerifyQCRequest, VerifyQCResponse
from . import service

router = APIRouter(prefix="/qc", tags=["Visual QC & Verification"])

@router.get("/target", response_model=QCTargetResponse, summary="Get active dismounted tool target on bench")
async def get_qc_target(tool: Optional[int] = Query(None), run: Optional[int] = Query(None)):
    """Retrieve metadata of the tool assembly currently staged on the optical inspection station"""
    return service.get_qc_target(tool, run)

@router.get("/tools/{tool_id}/runs/{run_index}/blades/{blade_index}", response_model=BladeQCResponse, summary="Get blade inspection results")
async def get_blade_qc(tool_id: int, run_index: int, blade_index: int):
    """Retrieve optical scan metadata, wear prediction, and sensor assessment for a specific cutting flute/blade"""
    return service.get_blade_qc(tool_id, run_index, blade_index)

@router.post("/verify", response_model=VerifyQCResponse, summary="Submit engineer sign-off decision")
async def verify_qc(req: VerifyQCRequest):
    """Submit human verification sign-off (CONFIRMED_WEAR / FALSE_ALARM) into MinIO ground truth pool"""
    return service.verify_blade(req)

@router.get("/images/{record_id}.jpg", summary="Serve microscope flank face image")
async def get_microscope_image(record_id: str):
    """Serve the raw optical microscope photograph for the cutting blade"""
    path = service.get_image_file_path(record_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Image for {record_id} not found")
    return FileResponse(str(path), media_type="image/jpeg")

@router.get("/gradcam/{record_id}.jpg", summary="Serve Grad-CAM heatmap visualization")
async def get_gradcam_image(record_id: str):
    """Serve Grad-CAM XAI explanation overlay"""
    path = service.get_image_file_path(record_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Grad-CAM image for {record_id} not found")
    return FileResponse(str(path), media_type="image/jpeg")

@router.post("/inspection-images", summary="Ingest optical photo from edge microscope camera")
async def upload_inspection_image(
    tool_id: int = Form(...),
    pass_index: int = Form(...),
    blade_index: int = Form(...),
    image: UploadFile = File(...),
):
    """Edge endpoint for optical microscope camera to ingest a newly captured blade image"""
    return {
        "job_id": f"qc-job-{tool_id}-{pass_index}-{blade_index}",
        "status": "QUEUED",
        "recordId": f"T{tool_id}R{pass_index}B{blade_index}",
        "filename": image.filename,
        "message": "Image received and queued for Dual-AI inference",
    }
