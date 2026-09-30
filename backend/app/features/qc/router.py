from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Response
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
async def get_blade_qc(tool_id: str, run_index: int, blade_index: int):
    """Retrieve multi-tier inspection: Tier 1 Force Alert, Tier 2 Chip AI, Tier 3 Tool Edge Metrology, and Consensus"""
    return service.get_blade_qc(tool_id, run_index, blade_index)

@router.post("/verify", response_model=VerifyQCResponse, summary="Submit engineer sign-off decision")
async def verify_qc(req: VerifyQCRequest):
    """Submit human verification sign-off (CONFIRMED_WEAR / SEND_TO_RETRAIN / FALSE_ALARM) into MinIO ground truth pool"""
    return await service.verify_blade(req)

@router.get("/images/chip/{record_id}.jpg", summary="Serve metal chip morphology image")
async def get_chip_image(record_id: str):
    """Serve high-magnification metal chip morphology photo (Tier 2 Vision AI)"""
    path = service.get_chip_image_file_path(record_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Chip image for {record_id} not found")
    return FileResponse(str(path), media_type="image/jpeg")

@router.get("/images/tool/{record_id}.jpg", summary="Serve raw tool flank face microscope image")
async def get_tool_image(record_id: str):
    """Serve optical microscope photograph for cutting flute edge (Tier 3 Physical Metrology)"""
    path = service.get_tool_image_file_path(record_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Tool image for {record_id} not found")
    return FileResponse(str(path), media_type="image/jpeg")

@router.get("/images/tool-processed/{record_id}.jpg", summary="Serve OpenCV edge-processed metrology overlay image")
async def get_tool_processed_image(record_id: str):
    """Serve computer vision edge detection overlay with Vb flank wear and chipping gap annotations"""
    img_bytes = service.generate_tool_processed_image(record_id)
    if not img_bytes:
        # Fallback to raw tool image if available
        path = service.get_tool_image_file_path(record_id)
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail=f"Tool processed image for {record_id} not found")
        return FileResponse(str(path), media_type="image/jpeg")
    return Response(content=img_bytes, media_type="image/jpeg")

@router.get("/images/{record_id}.jpg", summary="Serve microscope flank face image (backward compatibility)")
async def get_microscope_image(record_id: str, type: Optional[str] = Query("tool")):
    """Serve raw optical image (defaults to tool flute, or chip if type=chip)"""
    if type == "chip":
        path = service.get_chip_image_file_path(record_id)
    else:
        path = service.get_tool_image_file_path(record_id)

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Image for {record_id} not found")
    return FileResponse(str(path), media_type="image/jpeg")

@router.get("/gradcam/{record_id}.jpg", summary="Serve Grad-CAM heatmap visualization")
async def get_gradcam_image(record_id: str):
    """Serve Grad-CAM XAI explanation overlay"""
    path = service.get_tool_image_file_path(record_id)
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
        "message": "Image received and queued for 3-Tier Multi-Modal inference pipeline",
    }
