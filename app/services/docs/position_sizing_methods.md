# Position Sizing Methods: A Comprehensive Guide

This document outlines various position sizing methods used in trading to determine the quantity of an asset to trade. Each method is designed for different trading strategies and risk preferences.

## 1. Fixed Fractional Position Sizing

### Description

In this method, a fixed percentage of the account's capital is risked per trade.

### Formula

$$\text{Quantity} = \frac{\text{Risk Amount}}{\text{Risk Per Unit}}$$

### Steps

1. Determine the percentage of the account to risk.
2. Calculate the amount to risk.
3. Divide the risk amount by the risk per unit.

### Example

-   **Capital**: ₹10,000
-   **Risk Percentage**: 2%
-   **Entry Price**: ₹100
-   **Stop-Loss**: ₹95

#### Calculation

-   **Risk Amount**: ₹200
-   **Risk Per Unit**: ₹5
-   **Quantity**: 40 shares

## 2. Fixed Lot Size

### Description

The trader always trades a fixed number of lots, regardless of the risk or account size.

### Formula

$$\text{Quantity} = \text{Fixed Lot Size}$$

### Steps

1. Determine a fixed lot size.
2. Use this value directly for each trade.

### Example

-   **Fixed Lot Size**: 10

#### Calculation

Quantity = 10 (No other parameters are considered).

## 3. Volatility-Based Position Sizing

### Description

Adjusts position size based on market volatility, typically measured using the Average True Range (ATR).

### Formula

$$\text{Quantity} = \frac{\text{Risk Amount}}{\text{ATR} \times \text{Multiplier}}$$

### Steps

1. Calculate the ATR (volatility measure).
2. Adjust the ATR with a multiplier (e.g., 2x).
3. Divide the risk amount by the adjusted ATR.

### Example

-   **Risk Amount**: ₹200
-   **ATR**: 2.5
-   **Multiplier**: 2

#### Calculation

-   **Adjusted ATR**: 5
-   **Quantity**: 40 shares

## 4. Kelly Criterion

### Description

Determines the optimal fraction of capital to risk based on the probability of winning.

### Formula

$$f = \frac{bp - q}{b}$$

Where:

-   _f_: Fraction of capital to risk
-   _b_: Odds ratio
-   _p_: Probability of winning
-   _q_: Probability of losing (_1 - p_)

### Steps

1. Estimate win probability and odds ratio.
2. Calculate the Kelly fraction.
3. Use the fraction to determine the risk amount.

### Example

-   **Odds Ratio**: 1.5
-   **Win Probability**: 60%
-   **Capital**: ₹10,000

#### Calculation

-   Kelly Fraction: 0.2 (20% of capital)
-   Risk Amount: ₹2,000

## 5. Rupee-Based Position Sizing

### Description

The trader allocates a fixed rupee amount per trade, irrespective of account size or risk.

### Formula

$$\text{Quantity} = \frac{\text{Fixed Rupee Amount}}{\text{Risk Per Unit}}$$

### Steps

1. Determine a fixed rupee amount to risk.
2. Divide it by the risk per unit.

### Example

-   **Fixed Rupee Amount**: ₹100
-   **Entry Price**: ₹200
-   **Stop-Loss**: ₹190

#### Calculation

-   **Risk Per Unit**: 10
-   **Quantity**: 10 shares

## 6. Percent Volatility

### Description

A percentage of account equity is risked per unit of volatility (ATR).

### Formula

$$\text{Quantity} = \frac{\text{Account Balance} \times \text{Risk Percentage}}{\text{ATR}}$$

### Steps

1. Calculate the ATR.
2. Multiply account balance by the risk percentage.
3. Divide by ATR.

### Example

-   **Account Balance**: ₹10,000
-   **Risk Percentage**: 1%
-   **ATR**: 2.5

#### Calculation

-   **Risk Amount**: ₹100
-   **Quantity**: 40 shares

## 7. Equal Weighting

### Description

The account balance is divided equally among a predefined number of positions.

### Formula

$$\text{Quantity} = \frac{\text{Account Balance}}{\text{Max Open Positions} \times \text{Risk Per Unit}}$$

### Steps

1. Determine the maximum number of positions.
2. Divide account balance by the maximum positions.
3. Divide the result by risk per unit.

### Example

-   **Account Balance**: ₹10,000
-   **Max Positions**: 5
-   **Entry Price**: ₹100
-   **Stop-Loss**: ₹95

#### Calculation

-   **Allocation Per Trade**: ₹2,000
-   **Risk Per Unit**: ₹5
-   **Quantity**: 400 shares

## 8. Martingale Position Sizing

### Description

Increases position size after each losing trade, aiming to recover losses.

### Formula

$$\text{Quantity} = \frac{\text{Base Risk Amount} \times \text{Multiplier}}{\text{Risk Per Unit}}$$

### Steps

1. Check the outcome of the previous trade (win/loss).
2. Increase the risk amount after a loss using a multiplier (e.g., 2x).
3. Divide the risk amount by risk per unit.

### Example

-   **Base Risk Amount**: ₹100
-   **Multiplier (after loss)**: 2
-   **Entry Price**: ₹200
-   **Stop-Loss**: ₹190

#### Calculation

-   **Risk Amount**: ₹200
-   **Risk Per Unit**: ₹10
-   **Quantity**: 20 shares

## Conclusion

Each position sizing method serves different trading goals. Traders should choose the one that aligns with their risk tolerance, strategy, and market conditions.

### Method Selection Guide

| Method             | Best For                                   |
| ------------------ | ------------------------------------------ |
| Fixed Fractional   | General trading, consistent risk           |
| Fixed Lot Size     | Simplicity                                 |
| Volatility-Based   | Adapting to market conditions              |
| Kelly Criterion    | Maximizing growth with known probabilities |
| Rupee-Based        | Fixed risk per trade                       |
| Percent Volatility | Volatile markets                           |
| Equal Weighting    | Portfolio diversification                  |
| Martingale         | Aggressive recovery after losses           |
