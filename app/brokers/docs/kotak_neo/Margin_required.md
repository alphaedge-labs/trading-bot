# **Margin_Required**

Get required margin details

```python
client.margin_required(exchange_segment = "", price = "", order_type= "", product = "", quantity = "", instrument_token = "",
                       transaction_type = "")
```

### Example

```python
from neo_api_client import NeoAPI

#First initialize session and generate session token

client = NeoAPI(consumer_key=" ",consumer_secret=" ",environment=" ")
client.login(mobilenumber=" ", password=" ")
client.session_2fa("")

try:
    client.margin_required(exchange_segment = "", price = "", order_type= "", product = "",   quantity = "", instrument_token = "",  transaction_type = "")
except Exception as e:
    print("Exception when calling margin_required->margin_required: %s\n" % e)
```

### Parameters

| Name               | Description                                                                                       | Type |
| ------------------ | ------------------------------------------------------------------------------------------------- | ---- |
| _exchange_segment_ | nse_cm - NSE<br/>bse_cm - BSE<br/>nse_fo - NFO<br/>bse_fo - BFO<br/>cde_fo - CDS<br/>mcx_fo - MCX | Str  |
| _price_            | Price of the order                                                                                | Str  |
| _product_          | NRML - Normal<br/>CNC - Cash and Carry<br/>MIS - MIS<br/>INTRADAY - INTRADAY<br/>CO - Cover Order | Str  |
| _order_type_       | L - Limit<br/>MKT - Market<br/>SL - Stop loss limit<br/>SL-M - Stop loss market                   | Str  |
| _quantity_         | Quantity of the order                                                                             | Str  |
| _instrument_token_ | pSymbol in ScripMaster files                                                                      | Str  |
| _transaction_type_ | B(Buy), S(sell)                                                                                   | Str  |
| _trading_symbol_   | pTrdSymbol in ScripMaster files                                                                   | Str  |
| _transaction_type_ | B(Buy), S(sell)                                                                                   | Str  |
| _trigger_price_    | Optional, required for stop loss and cover order                                                  | Str  |

### Return type

**object**

### Sample response

```json
{
	"data": {
		"avlCash": "104.96",
		"insufFund": "12520.04",
		"stat": "Ok",
		"totMrgnUsd": "12625.00",
		"mrgnUsd": "0.00",
		"reqdMrgn": "12625.00",
		"avlMrgn": "104.96",
		"stCode": 200,
		"tid": "server2_2330220",
		"ordMrgn": "12625.00",
		"rmsVldtd": 78
	}
}
```

### HTTP request headers

-   **Accept**: application/json

### HTTP response details

| Status Code | Description                                        |
| ----------- | -------------------------------------------------- |
| _200_       | Gets the margin_required data for a client account |
| _400_       | Invalid or missing input parameters                |
| _403_       | Invalid session, please re-login to continue       |
| _429_       | Too many requests to the API                       |
| _500_       | Unexpected error                                   |
| _502_       | Not able to communicate with OMS                   |
| _503_       | Trade API service is unavailable                   |
| _504_       | Gateway timeout, trade API is unreachable          |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
