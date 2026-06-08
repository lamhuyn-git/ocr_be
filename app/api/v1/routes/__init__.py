from fastapi import APIRouter
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.users import router as users_router
from app.api.v1.routes.organizations import router as orgs_router
from app.api.v1.routes.ocr import router as ocr_router
from app.api.v1.routes.form import router as form_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(orgs_router)
api_router.include_router(ocr_router)
api_router.include_router(form_router)
