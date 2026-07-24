from fastapi import APIRouter

from app.api.v1.endpoints import auth, tenants, users, documents, campaigns, calls, reports

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(documents.router, prefix="/documents", tags=["Knowledge Base"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])