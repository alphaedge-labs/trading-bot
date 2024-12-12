import pytest
from datetime import datetime
from app.services.user_service import UserService
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
async def user_service(mock_redis, mock_mongodb):
    service = UserService()
    service.redis_client = mock_redis
    service.users_collection = mock_mongodb
    return service

@pytest.mark.asyncio
async def test_initialize(user_service):
    # Mock data
    mock_users = [
        {"_id": "user1", "is_active": True},
        {"_id": "user2", "is_active": True}
    ]
    user_service.users_collection.find.return_value.to_list = AsyncMock(return_value=mock_users)
    
    await user_service.initialize()
    
    assert len(user_service.users) == 2
    assert user_service.redis_client.set_hash.call_count == 2

@pytest.mark.asyncio
async def test_block_capital_success(user_service):
    user_id = "user1"
    amount = 1000.0
    
    # Mock user data
    mock_user = {
        "_id": user_id,
        "capital": {
            "available_balance": 2000.0,
            "total_deployed": 1000.0
        }
    }
    
    user_service.get_user = AsyncMock(return_value=mock_user)
    user_service.users_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    
    result = await user_service.block_capital(user_id, amount)
    
    assert result is True
    assert user_service.users[user_id]["capital"]["available_balance"] == 1000.0
    assert user_service.users[user_id]["capital"]["total_deployed"] == 2000.0

@pytest.mark.asyncio
async def test_release_capital_success(user_service):
    user_id = "user1"
    amount = 1000.0
    pnl = 100.0
    
    mock_user = {
        "_id": user_id,
        "capital": {
            "available_balance": 1000.0,
            "total_deployed": 2000.0
        }
    }
    
    user_service.get_user = AsyncMock(return_value=mock_user)
    user_service.users_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    
    result = await user_service.release_capital(user_id, amount, pnl)
    
    assert result is True
    assert user_service.users[user_id]["capital"]["available_balance"] == 2100.0
    assert user_service.users[user_id]["capital"]["total_deployed"] == 1000.0 