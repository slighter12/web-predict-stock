# Plaform: Personal Quantitative Research Platform

## Project Vision

To build a personal tool inspired by Quant Research Firms. The core function is to provide an efficient, visual research loop that allows users to quickly "define features," "build models," "run backtests," and "evaluate strategies." This project does not pursue the ultra-low latency of HFT (High-Frequency Trading) but rather the Alpha discovery capabilities of medium-to-low frequency strategies.

## Key Features

*   **F-01: Data Pipeline:** A scheduled scraper to automatically fetch "Daily Candlestick (OHLCV)" and "Institutional Investor Trading" data from the Taiwan Stock Exchange (TWSE) daily. Data will be cleaned and stored in a PostgreSQL database.
*   **F-02: Dynamic Feature Engineering UI:** A graphical interface for users to define "feature vectors" without writing code.
*   **F-03: Modeling Engine:** The backend will receive feature configurations from F-02 and train a specified model.
*   **F-04: High-Speed Backtesting Engine:** Use the trained model to run backtests on historical data to evaluate the strategy's effectiveness.
*   **F-05: Strategy Dashboard:** Visualize backtest results on the frontend, including an equity curve, buy/sell points on a K-line chart, and Key Performance Indicators (KPIs).

## Architecture & Tech Stack

*   **Primary Language:** Python 3.12+
*   **Backend API:** FastAPI
*   **Frontend UI:** React / Vue
*   **Database:** PostgreSQL
*   **Data Processing:** Pandas
*   **Backtesting Engine:** VectorBT

## Development Phases

### Phase 1: Core Backtesting Loop (ARIMA + ML Workhorse)

The goal is to build an MVP (Minimum Viable Product) that implements the complete flow from "UI-defined features" to "XGBoost backtesting."

### Phase 2: Deep Learning Experiments & Data Expansion

The goal is to introduce more complex models and expand data sources to find stronger Alpha.
