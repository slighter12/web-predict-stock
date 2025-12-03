import pandas as pd
import numpy as np
import vectorbt as vbt
from xgboost import XGBClassifier

# Use relative imports to access other modules within the same package
from .feature_engine import add_features
from .model_service import train_xgboost

def run_backtest(model: XGBClassifier, X_test: pd.DataFrame, price_data: pd.Series) -> dict:
    """
    Runs a backtest using vectorbt based on model predictions.

    Args:
        model (XGBClassifier): The trained machine learning model.
        X_test (pd.DataFrame): The feature set for the test period.
        price_data (pd.Series): The series of closing prices for the test period.

    Returns:
        dict: A dictionary containing key performance indicators (KPIs)
              like Total Return, Sharpe Ratio, and Max Drawdown.
    """
    # --- 1. Generate Prediction Signals ---
    # predict() returns 1 for "up" and 0 for "down" or "hold"
    predictions = model.predict(X_test)
    signals = pd.Series(predictions, index=X_test.index)

    # --- 2. Align Data ---
    # Ensure the price data and signals have the same index for vectorbt
    aligned_price, aligned_signals = price_data.align(signals, join='inner')

    if aligned_price.empty or aligned_signals.empty:
        raise ValueError("Price data and signals could not be aligned. Check for index mismatch.")

    # Define entry and exit signals based on the model's predictions
    # Enter a position when the model predicts the price will go up (signal == 1)
    # Exit a position when the model predicts it will not go up (signal == 0)
    entries = aligned_signals == 1
    exits = aligned_signals == 0

    # --- 3. Run the Backtest using vectorbt ---
    portfolio = vbt.Portfolio.from_signals(
        close=aligned_price,
        entries=entries,
        exits=exits,
        freq='D',          # Assume daily frequency
        init_cash=100000,  # Starting with $100,000
        sl_stop=0.05,      # 5% stop-loss
        tp_stop=0.10,      # 10% take-profit
    )

    # --- 4. Extract and Return KPIs ---
    stats = portfolio.stats()
    kpis = {
        'Total Return [%]': float(round(stats['Total Return [%]'], 2)),
        'Sharpe Ratio': float(round(stats['Sharpe Ratio'], 2)),
        'Max Drawdown [%]': float(round(stats['Max Drawdown [%]'], 2)),
        'Win Rate [%]': float(round(stats['Win Rate [%]'], 2)),
        'Profit Factor': float(round(stats['Profit Factor'], 2)),
        'Total Trades': int(stats['Total Trades']),
    }

    return kpis

if __name__ == '__main__':
    # --- Example Usage ---
    # Create a sample DataFrame (same as in model_service)
    data = {
        'open': np.random.rand(100) * 10 + 100,
        'high': np.random.rand(100) * 10 + 102,
        'low': np.random.rand(100) * 10 + 98,
        'close': np.random.rand(100) * 10 + 100,
        'volume': np.random.randint(1000, 5000, 100)
    }
    sample_df = pd.DataFrame(data, index=pd.to_datetime(pd.date_range('2023-01-01', periods=100)))

    # 1. Add features
    feature_config = {'ma': [5, 10, 20], 'rsi': 14}
    df_with_features = add_features(sample_df.copy(), feature_config)

    # 2. Train the model
    try:
        trained_model, X_test_data, y_test_data = train_xgboost(df_with_features)

        # 3. Get the price data corresponding to the test period
        test_price_data = df_with_features.loc[X_test_data.index, 'close']

        # 4. Run the backtest
        backtest_results = run_backtest(trained_model, X_test_data, test_price_data)

        print("\n--- Backtest Results ---")
        import json
        print(json.dumps(backtest_results, indent=2))

    except ValueError as e:
        print(f"An error occurred during the example run: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
