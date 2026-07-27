from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.database import init_db, seed_erp_students_from_pi_sheet, seed_school_data
from app.routes import admin, auth, chat, erp, erp_fees, groups

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    seed_school_data()
    seed_erp_students_from_pi_sheet()
    auth.bootstrap_admin_pin()
    logger.info("PPIS Messenger backend started")
    yield


app = FastAPI(title="PPIS Messenger", lifespan=lifespan)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(erp.router, prefix="/api/erp", tags=["erp"])
app.include_router(erp_fees.router, prefix="/api/erp", tags=["erp-fees"])


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
