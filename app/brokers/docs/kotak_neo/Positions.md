# **Positions**

Gets positions

```python
client.positions()
```

### Example

```python

from neo_api_client import NeoAPI

#First initialize session and generate session token

client = NeoAPI(consumer_key=" ",consumer_secret=" ",environment=" ")
client.login(mobilenumber=" ", password=" ")
client.session_2fa("")

try:
    client.positions()
except Exception as e:
    print("Exception when calling PositionsApi->positions: %s\n" % e)
```

### Return type

**object**

### Sample response

```json
{
	"stat": "Ok",
	"stCode": 200,
	"data": [
		{
			"buyAmt": "2625.00",
			"cfSellAmt": "0.00",
			"prod": "NRML",
			"exSeg": "nse_fo",
			"sqrFlg": "Y",
			"actId": "PRS2206",
			"cfBuyQty": "0",
			"cfSellQty": "0",
			"tok": "53179",
			"flBuyQty": "25",
			"flSellQty": "25",
			"sellAmt": "2625.00",
			"posFlg": "true",
			"cfBuyAmt": "0.00",
			"stkPrc": "0.00",
			"trdSym": "BANKNIFTY21JULFUT",
			"sym": "BANKNIFTY",
			"expDt": "29 Jul, 2021",
			"type": "FUTIDX",
			"series": "XX",
			"brdLtQty": "25",
			"exp": "1627569000",
			"optTp": "XX",
			"genNum": "1",
			"genDen": "1",
			"prcNum": "1",
			"prcDen": "1",
			"lotSz": "25",
			"multiplier": "1",
			"precision": "2",
			"hsUpTm": "2021/07/13 18:34:44"
		}
	]
}
```

### Positions Calculations

#### Quantity Fields

1. Total Buy Qty = (`cfBuyQty` + `flBuyQty`)
2. Total Sell qty = (`cfSellQty` + `flSellQty`)
3. Carry Fwd Qty = (`cfBuyQty` - `cfSellQty`)
4. Net qty = Total Buy Qty - Total Sell qty </br>
   For FnO Scrips, divide all the parameters from Positions API response(`cfBuyQty`, `flBuyQty`, `cfSellQty`, `flSellQty`) by `lotSz`

#### Amount Fields

1. Total Buy Amt = (`cfBuyAmt` + `buyAmt`)
2. Total Sell Amt = (`cfSellAmt` + `sellAmt`)

#### Avg Price Fields

1. Buy Avg Price = <sup>Total Buy Amt</sup>/<sub>(Total Buy Qty _ `multiplier` _ (`genNum`/`genDen`) \* (`prcNum`/ `prcDen`))</sub>

2. Sell Avg Price = <sup>Total Sell Amt</sup>/<sub>(Total Sell qty _ `multiplier` _ (`genNum`/ `genDen`) \* (`prcNum`/ `prcDen`))</sub>
3. Avg Price </br>
   a. If Total Buy Qty > Total Sell qty, then Buy Avg Price </br>
   b. If Total Buy Qty < Total Sell qty, then Sell Avg Price </br>
   c. If Total Buy Qty = Total Sell qty, then 0 </br>
   You need to calculate the average price to a specific number of decimal places that is decided by `precision` field.

#### Profit N Loss

PnL = (Total Sell Amt - Total Buy Amt) + (Net qty _ LTP _ `multiplier` _ (<sup>`genNum`</sup>/<sub>`genDen`</sub>) _ (<sup>`prcNum`</sup>/<sub>`prcDen`</sub>) )

### HTTP request headers

-   **Accept**: application/json

### HTTP response details

| Status Code | Description                                  |
| ----------- | -------------------------------------------- |
| _200_       | Gets the Positoin data for a client account  |
| _400_       | Invalid or missing input parameters          |
| _403_       | Invalid session, please re-login to continue |
| _429_       | Too many requests to the API                 |
| _500_       | Unexpected error                             |
| _502_       | Not able to communicate with OMS             |
| _503_       | Trade API service is unavailable             |
| _504_       | Gateway timeout, trade API is unreachable    |
