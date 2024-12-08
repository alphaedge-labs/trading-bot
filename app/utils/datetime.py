from datetime import datetime
import pytz

UTC = pytz.timezone("UTC")
IST = pytz.timezone("Asia/Kolkata")

def get_ist_time():
    return datetime.now(IST)

def is_within_trading_hours(start_time_str: str, end_time_str: str) -> bool:
    """Check if current time is within trading hours"""
    current_time = get_ist_time().time()
    
    # Convert string times to time objects
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()
    
    return start_time <= current_time <= end_time

def _parse_datetime(dt_string: str) -> datetime:
    """Helper function to parse different datetime formats"""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # For ISO format: 2024-12-08T00:28:11.805344
        "%a %b %d %H:%M:%S %Y"   # For day format: Sun Dec 08 00:35:44 2024
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime string: {dt_string}")