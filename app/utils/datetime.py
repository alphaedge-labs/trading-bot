from datetime import datetime, time
import pytz

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