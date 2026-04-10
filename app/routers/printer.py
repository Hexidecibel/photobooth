"""Print API endpoint for submitting and checking print jobs."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/printer", tags=["printer"])


@router.post("/print/{photo_id}")
async def print_photo(photo_id: str, request: Request):
    """Submit a photo for printing."""
    printer = request.app.state.printer
    if not printer or not printer.is_available:
        raise HTTPException(503, "Printer not available")

    config = request.app.state.config
    photo_path = Path(config.general.save_dir) / "photos"
    matches = list(photo_path.rglob(f"{photo_id}.*"))
    if not matches:
        raise HTTPException(404, "Photo not found")

    job_id = await printer.print_photo(matches[0], config.printer.copies)
    if job_id is None:
        raise HTTPException(500, "Print job failed")

    return {"status": "submitted", "job_id": job_id}


@router.get("/status")
async def printer_status(request: Request):
    """Return current printer availability."""
    printer = request.app.state.printer
    return {
        "available": printer is not None and printer.is_available,
        "printer_name": printer._printer_name if printer else None,
    }
