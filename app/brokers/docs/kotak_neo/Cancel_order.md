# **Cancel_Order**

Cancel an order

## Method 1 - Quick Method

```python
client.cancel_order(order_id = "")
```

## Method 2 - Delayed Method

This method checks the order status first and then cancels the order if it is open.<br/>

```python
client.cancel_order(order_id = "", isVerify=True)
```

### Example

```python
from neo_api_client import NeoAPI

#First initialize session and generate session token

client = NeoAPI(consumer_key=" ",consumer_secret=" ",environment=" ")
client.login(mobilenumber=" ", password=" ")
client.session_2fa("")

try:
    # Cancel an order
    client.cancel_order(order_id = "")
except Exception as e:
    print("Exception when calling OrderApi->cancel_order: %s\n" % e)
```

### Parameters

| Name       | Description                                                 | Type    |
| ---------- | ----------------------------------------------------------- | ------- |
| _order_id_ | Order ID to cancel                                          | str     |
| _isVerify_ | Flag to check the status of order (Delayed method)          | boolean |
| _amo_      | After market order - YES, NO (optional, Default Value - NO) | str     |

### Return type

**object**

### Sample response

```json
{
	"stat": "Ok",
	"nOrdNo": "230120000017243",
	"stCode": 200
}
```

### HTTP request headers

-   **Accept**: application/json

### HTTP response details

| Status Code | Description                                  |
| ----------- | -------------------------------------------- |
| _200_       | Order cancelled successfully                 |
| _400_       | Invalid or missing input parameters          |
| _403_       | Invalid session, please re-login to continue |
| _429_       | Too many requests to the API                 |
| _500_       | Unexpected error                             |
| _502_       | Not able to communicate with OMS             |
| _503_       | Trade API service is unavailable             |
| _504_       | Gateway timeout, trade API is unreachable    |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
