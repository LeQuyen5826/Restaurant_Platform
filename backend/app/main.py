from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .modules.auth.router import router as auth_router
from .modules.booking.router import router as booking_router
from .modules.dining.router import floor_router, guest_router, kitchen_router, qr_router
from .modules.menu.router import router as menu_router
from .modules.restaurant.overview import router as overview_router
from .modules.restaurant.router import router as staff_router
from .modules.restaurant.setup import router as setup_router

app = FastAPI(title="Restaurant Booking API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(staff_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
app.include_router(menu_router, prefix="/api")
for r in (booking_router, guest_router, floor_router, kitchen_router, qr_router, overview_router):
    app.include_router(r, prefix="/api")

UPLOADS = Path(settings.upload_dir)
UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=UPLOADS), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
