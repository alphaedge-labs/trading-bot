# **Modify_Order**

Modify an existing order

## **Method 1 - Quick method**

```python
client.modify_order(instrument_token = "", exchange_segment = "", product = "", price = "", order_type = "", quantity= "",
                    validity = "", trading_symbol = "", transaction_type = "", order_id = "")
```

## **Method 2 - Delayed method**

This method verifies the order status first and then modifies the order if it is open.

```python
client.modify_order(order_id = "", price = "", quantity = "", trigger_price = "", validity = "", order_type = "", amo = "")
```

### Example

```python
from neo_api_client import NeoAPI

#First initialize session and generate session token

client = NeoAPI(consumer_key=" ",consumer_secret=" ",environment=" ")
client.login(mobilenumber=" ", password=" ")
client.session_2fa("")

try:
    # Modify an existing order
    client.modify_order(instrument_token = "", exchange_segment = "", product = "", price = "",
                        order_type = "", quantity= "", validity = "", trading_symbol = "",transaction_type = "", order_id = "", amo = "")
except Exception as e:
    print("Exception when calling OrderApi->modify_order: %s\n" % e)

```

### Parameters

| Name                | Description                                                                                       | Type           |
| ------------------- | ------------------------------------------------------------------------------------------------- | -------------- |
| _instrument_token_  | pSymbol in ScripMaster file (first Column)                                                        | Str [optional] |
| _market_protection_ | String - (Default Value - 0)                                                                      | Str [optional] |
| _product_           | NRML - Normal<br/>CNC - Cash and Carry<br/>MIS - MIS<br/>INTRADAY - INTRADAY<br/>CO - Cover Order | Str            |
| _dd_                | Default Value - “NA”                                                                              | Str [optional] |
| _filled_quantity_   | (Default Value - 0)                                                                               | Str [optional] |
| _validity_          | Validity of the order - DAY, IOC                                                                  | Str [optional] |
| _trading_symbol_    | pTrdSymbol in ScripMaster file                                                                    | Str            |
| _transaction_type_  | B(Buy), S(sell)                                                                                   | Str            |
| _order_type_        | L - Limit<br/>MKT - Market<br/>SL - Stop loss limit<br/>SL-M - Stop loss market                   | Str            |
| _trigger_price_     | Optional, required for stop loss and cover order                                                  | Str [optional] |
| _quantity_          | quantity of the order                                                                             | Str            |
| _order_id_          | order id of the order you want to modify                                                          | Str            |
| _exchange_segment_  | nse_cm - NSE<br/>bse_cm - BSE<br/>nse_fo - NFO<br/>bse_fo - BFO<br/>cde_fo - CDS<br/>mcx_fo - MCX | Str [optional] |

### Return type

**object**

### Sample response

```json
{
	"stat": "Ok",
	"nOrdNo": "220621000000097",
	"stCode": 200
}
```

### HTTP request headers

-   **Content-Type**: application/json
-   **Accept**: application/json

### HTTP response details

| Status Code | Description                                  |
| ----------- | -------------------------------------------- |
| _200_       | Order modified successfully                  |
| _400_       | Invalid or missing input parameters          |
| _403_       | Invalid session, please re-login to continue |
| _429_       | Too many requests to the API                 |
| _500_       | Unexpected error                             |
| _502_       | Not able to communicate with OMS             |
| _503_       | Trade API service is unavailable             |
| _504_       | Gateway timeout, trade API is unreachable    |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
