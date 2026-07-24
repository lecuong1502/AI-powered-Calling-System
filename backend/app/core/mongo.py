import beanie
import motor.motor_asyncio

from app.core.config import settings


async def init_mongo() -> None:
    """Initialize Beanie ODM with all document models."""
    # Import here to avoid circular imports
    from app.models.mongo import CallSession, CallTranscript, CallSummary

    client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongo_url)
    await beanie.init_beanie(
        database=client[settings.mongo_db],
        document_models=[CallSession, CallTranscript, CallSummary],
    )