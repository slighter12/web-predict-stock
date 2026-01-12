from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import date
from typing import Dict, List, Any

# Use relative imports for intra-package dependencies
from . import data_service
from . import feature_engine
from . import model_service
from . import backtest_service

# Initialize the FastAPI app
app = FastAPI(
    title="Personal Quantitative Research Platform API",
    description="An API for backtesting trading strategies.",
    version="1.0.0",
)

# --- Pydantic Models for API Request Body ---
class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="The stock symbol to backtest.", example="2330")
    start_date: date = Field(..., description="The start date for the backtest.", example="2023-01-01")
    end_date: date = Field(..., description="The end date for the backtest.", example="2023-12-31")
    feature_config: Dict[str, Any] = Field(
        ...,
        description="Configuration for the feature engine.",
        example={'ma': [5, 20, 60], 'rsi': 14}
    )

# --- API Endpoints ---
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Quant Platform API. Visit /docs for documentation."}

@app.post("/api/v1/backtest", tags=["Backtesting"])
def run_backtest_endpoint(request: BacktestRequest):
    """
    Runs a complete backtest for a given stock, date range, and feature configuration.
    """
    try:
        # --- Step A: Get Data ---
        # Fetch the historical OHLCV data from the database
        df = data_service.get_data(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date
        )
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for symbol '{request.symbol}' in the specified date range.")

        # --- Step B: Add Features ---
        # Add technical indicator features to the DataFrame
        df_features = feature_engine.add_features(df.copy(), request.feature_config)

        # --- Step C: Train Model ---
        # Train the XGBoost model on the feature-rich DataFrame
        # The service handles splitting data, so we pass the full DataFrame
        model, X_test, y_test = model_service.train_xgboost(df_features)

        # --- Step D: Run Backtest ---
        # Get the closing prices for the test period to run the backtest against
        price_data_for_backtest = df_features.loc[X_test.index, 'close']

        # Run the backtest using the trained model and test data
        kpis = backtest_service.run_backtest(model, X_test, price_data_for_backtest)

        # --- Step E: Return Results ---
        # Return the calculated Key Performance Indicators
        return kpis

    except ValueError as ve:
        # Catch specific value errors, e.g., not enough data for a train/test split
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Catch any other unexpected errors during the process
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

# To run this API locally:
# uvicorn backend.main:app --reload
