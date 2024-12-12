import pytest
from datetime import datetime
from app.brokers.paper_broker import PaperBroker
from app.constants.brokers import Broker

@pytest.fixture
def paper_broker():
    return PaperBroker(client_id="test_client", client_secret="test_secret")

def test_paper_broker_initialization():
    broker = PaperBroker(client_id="test_client", client_secret="test_secret")
    assert broker.client_id == "test_client"
    assert broker.client_secret == "test_secret"

def test_paper_broker_initialization_failure():
    with pytest.raises(ValueError):
        PaperBroker(client_id="", client_secret="")

def test_form_order(paper_broker):
    test_data = {
        "symbol": "NIFTY",
        "quantity": 100,
        "transaction_type": "BUY",
        "entry_price": 18000,
        "stop_loss": 17900,
        "strike_price": 18000,
        "expiry_date": "2024-03-28",
        "right": "CE"
    }
    
    order = paper_broker.form_order(test_data)
    
    assert order["symbol"] == "NIFTY"
    assert order["quantity"] == 100
    assert order["transaction_type"] == "BUY"
    assert order["product"] == "MIS"
    assert order["order_type"] == "LIMIT"
    assert order["strike_price"] == 18000
    assert order["expiry_date"] == "2024-03-28"
    assert order["right"] == "CE"

@pytest.mark.asyncio
async def test_place_order(paper_broker):
    test_order = {
        "symbol": "NIFTY",
        "quantity": 100,
        "transaction_type": "BUY",
        "price": 18000,
        "variety": "REGULAR",
        "validity": "DAY",
        "product": "MIS",
        "exchange": "NSE"
    }
    
    result = await paper_broker.place_order(test_order)
    
    assert result["status"] == "COMPLETE"
    assert result["broker"] == Broker.PAPER_BROKER.value
    assert result["quantity"] == test_order["quantity"]
    assert result["transaction_type"] == test_order["transaction_type"] 