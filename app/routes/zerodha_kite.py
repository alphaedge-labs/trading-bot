import json
from fastapi import APIRouter, Request, Query
from utils.logging import logger
from database.redis import redis_client
from utils.id_generator import generate_id

from constants.redis import HashSets, Channels

router = APIRouter()

'''
data recieved from zerodha kite postback:
{
    "user_id": "AB1234",
    "unfilled_quantity": 0,
    "app_id": 1234,
    "checksum": "2011845d9348bd6795151bf4258102a03431e3bb12a79c0df73fcb4b7fde4b5d",
    "placed_by": "AB1234",
    "order_id": "220303000308932",
    "exchange_order_id": "1000000001482421",
    "parent_order_id": null,
    "status": "COMPLETE",
    "status_message": null,
    "status_message_raw": null,
    "order_timestamp": "2022-03-03 09:24:25",
    "exchange_update_timestamp": "2022-03-03 09:24:25",
    "exchange_timestamp": "2022-03-03 09:24:25",
    "variety": "regular",
    "exchange": "NSE",
    "tradingsymbol": "SBIN",
    "instrument_token": 779521,
    "order_type": "MARKET",
    "transaction_type": "BUY",
    "validity": "DAY",
    "product": "CNC",
    "quantity": 1,
    "disclosed_quantity": 0,
    "price": 0,
    "trigger_price": 0,
    "average_price": 470,
    "filled_quantity": 1,
    "pending_quantity": 0,
    "cancelled_quantity": 0,
    "market_protection": 0,
    "meta": {},
    "tag": null,
    "guid": "XXXXXX"
}
'''

@router.post("/postback")
async def postback(request: Request, user_id: str = Query(...)):
    try:
        data = await request.json()
        logger.info(f"Received postback data for user {user_id}: {data}")
        
        # Publish the order update to redis
        hashset_name, request_id = f"{HashSets.ZERODHA_UPDATES.value}_{user_id}", generate_id() 
        await redis_client.set_hash(hashset_name, request_id, data)
        payload = {"request_id": request_id, "user_id": user_id}
        await redis_client.publish(Channels.ZERODHA_ORDERS.value, json.dumps(payload))
        
        return {"status": "success", "message": "Postback received"}
    except Exception as e:
        logger.error(f"Error processing postback: {e}")
        return {"status": "error", "message": str(e)}