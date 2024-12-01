from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def get_ist_time():
    return datetime.now(IST)