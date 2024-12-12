import pytest
from datetime import datetime, time
from app.utils.datetime import is_within_trading_hours, _parse_datetime

def test_is_within_trading_hours():
    # Test cases for trading hours
    assert is_within_trading_hours("09:15", "15:30") == True  # During market hours
    assert is_within_trading_hours("00:00", "01:00") == False  # Outside market hours

def test_parse_datetime():
    # Test ISO format
    iso_dt = "2024-12-08T00:28:11.805344"
    parsed_iso = _parse_datetime(iso_dt)
    assert isinstance(parsed_iso, datetime)
    
    # Test day format
    day_dt = "Sun Dec 08 00:35:44 2024"
    parsed_day = _parse_datetime(day_dt)
    assert isinstance(parsed_day, datetime)
    
    # Test invalid format
    with pytest.raises(ValueError):
        _parse_datetime("invalid_datetime") 