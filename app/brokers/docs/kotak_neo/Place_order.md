# Place_Order

Place a New order

```python
client.place_order(exchange_segment="", product="", price="", order_type="", quantity="", validity="", trading_symbol="",
                   transaction_type="", amo="", disclosed_quantity="", market_protection="", pf="", trigger_price="",
                   tag=)
```

### Example

```python
from neo_api_client import NeoAPI

#First initialize session and generate session token

client = NeoAPI(consumer_key=" ",consumer_secret=" ",environment=" ")
client.login(mobilenumber=" ", password=" ")
client.session_2fa(" ")

try:
    # Place a Order
    client.place_order(exchange_segment="", product="", price="", order_type="", quantity="", validity="", trading_symbol="",
                       transaction_type="", amo="NO", disclosed_quantity="0", market_protection="0", pf="N",
                       trigger_price="0", tag=None)
except Exception as e:
    print("Exception when calling OrderApi->place_order: %s\n" % e)
```

### Parameters

| Name                 | Description                                                                                       | Type           |
| -------------------- | ------------------------------------------------------------------------------------------------- | -------------- |
| _amo_                | YES/NO - (Default Value - NO)                                                                     | Str [optional] |
| _disclosed_quantity_ | (Default Value - 0)                                                                               | Str [optional] |
| _exchange_segment_   | nse_cm - NSE<br/>bse_cm - BSE<br/>nse_fo - NFO<br/>bse_fo - BFO<br/>cde_fo - CDS<br/>mcx_fo - MCX | Str            |
| _market_protection_  | (Default Value - 0)                                                                               | Str [optional] |
| _product_            | NRML - Normal<br/>CNC - Cash and Carry<br/>MIS - MIS<br/>CO - Cover Order<br/>                    | Str            |
| _pf_                 | Default Value - “N”                                                                               | Str [optional] |
| _price_              | price of the order                                                                                | Str [optional] |
| _order_type_         | L - Limit<br/>MKT - Market<br/>SL - Stop loss limit<br/>SL-M - Stop loss market                   | Str            |
| _quantity_           | quantity of the order                                                                             | Str            |
| _validity_           | Validity of the order - DAY, IOC, GTC, EOS                                                        | Str            |
| _trigger_price_      | Optional, required for stop loss and cover order                                                  | Str [optional] |
| _trading_symbol_     | pTrdSymbol in ScripMaster file                                                                    | Str            |
| _transaction_type_   | B(Buy), S(Sell)                                                                                   | Str            |
| _tag_                | Tag for this order                                                                                | Str [optional] |

### Return type

**object**

### Sample response

```json
{
	"stat": "Ok",
	"nOrdNo": "237362700735243",
	"stCode": 200
}
```

### HTTP request headers

-   **Content-Type**: application/json
-   **Accept**: application/json

### HTTP response details

| Status Code | Description                                  |
| ----------- | -------------------------------------------- |
| _200_       | Order placed successfully                    |
| _400_       | Invalid or missing input parameters          |
| _403_       | Invalid session, please re-login to continue |
| _429_       | Too many requests to the API                 |
| _500_       | Unexpected error                             |
| _502_       | Not able to communicate with OMS             |
| _503_       | Trade API service is unavailable             |
| _504_       | Gateway timeout, trade API is unreachable    |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
