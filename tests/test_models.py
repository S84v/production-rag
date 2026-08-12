from sqlalchemy import select

from production_rag.db.session import async_session_factory
from production_rag.models.collection import Collection


async def test_create_and_read_collection():
    async with async_session_factory() as session:
        collection = Collection(
            name="test-collection",
            description="Integration test collection",
        )

        session.add(collection)
        await session.commit()

        result = await session.execute(
            select(Collection).where(Collection.id == collection.id)
        )
        persisted_collection = result.scalar_one()

        assert persisted_collection.id == collection.id
        assert persisted_collection.name == "test-collection"
        assert persisted_collection.description == "Integration test collection"
        assert persisted_collection.created_at is not None
        assert persisted_collection.updated_at is not None

        await session.delete(persisted_collection)
        await session.commit()
