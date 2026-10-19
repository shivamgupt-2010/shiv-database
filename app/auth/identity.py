import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def generate_unique_shiv_id(db: AsyncSession) -> str:
    """
    Generates a unique, immutable, human-readable SHIV ID.
    Format: SHV-XXXXXX (e.g. SHV-10482, SHV-82914)
    """
    from app.database.models.auth import User

    for _ in range(20):
        # Generate 5 to 6 digits integer
        num = secrets.randbelow(900000) + 100000  # 100000 to 999999
        candidate_id = f"SHV-{num}"

        stmt = select(User.id).where(User.shiv_id == candidate_id).limit(1)
        res = await db.execute(stmt)
        if res.scalar_one_or_none() is None:
            return candidate_id

    # Fallback with extra random suffix if dense
    random_hex = secrets.token_hex(3).upper()
    return f"SHV-{random_hex}"
