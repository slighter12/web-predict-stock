import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Use a relative import to access other modules within the same package
from .feature_engine import add_features

def train_xgboost(df: pd.DataFrame):
    """
    Trains a simple XGBoost classifier to predict the next day's price movement.

    Args:
        df (pd.DataFrame): DataFrame containing OHLCV and feature data.

    Returns:
        tuple: A tuple containing:
            - model (XGBClassifier): The trained XGBoost model.
            - X_test (pd.DataFrame): The testing feature set.
            - y_test (pd.Series): The testing target set.
    """
    # --- 1. Create the Target Variable ---
    # The target is 1 if the next day's closing price is higher than the current day's, else 0.
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

    # --- 2. Clean Data ---
    # Drop rows with NaN values (e.g., the last row due to shifting, or from feature calculation)
    df.dropna(inplace=True)

    # --- 3. Define Features (X) and Target (y) ---
    # Features are all columns except the original OHLCV, symbol, date, and the target itself.
    # This assumes that any column not in the original set is a feature.
    original_cols = ['open', 'high', 'low', 'close', 'volume', 'target', 'date', 'symbol']
    features = [col for col in df.columns if col not in original_cols]

    X = df[features]
    y = df['target']

    if X.empty:
        raise ValueError("No features available for training. Ensure the feature engine added columns.")

    # --- 4. Split Data into Training and Testing Sets ---
    # We use a time-series split, training on the past and testing on the most recent data.
    # shuffle=False is crucial for time-series data.
    test_size = 0.2
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, shuffle=False
    )

    if len(X_train) == 0 or len(X_test) == 0:
        raise ValueError(f"Not enough data to create a training/test split with test_size={test_size}.")

    # --- 5. Train the XGBoost Model ---
    model = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        n_estimators=100,
        random_state=42,
        use_label_encoder=False
    )
    model.fit(X_train, y_train)

    print(f"Model trained successfully. Test set accuracy: {accuracy_score(y_test, model.predict(X_test)):.4f}")

    return model, X_test, y_test

if __name__ == '__main__':
    # --- Example Usage ---
    # Create a sample DataFrame
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
        print("\n--- Model Training Complete ---")
        print(f"Model: {trained_model}")
        print(f"X_test shape: {X_test_data.shape}")
        print(f"y_test shape: {y_test_data.shape}")
    except ValueError as e:
        print(f"Error during model training: {e}")
