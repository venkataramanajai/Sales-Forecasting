import os
import shutil
import sqlite3
import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import datetime, timedelta
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import time

DB_PATH = os.path.join("data", "sales.db")

# ─────────────────────────────────────────────
# STEP 1: DATA GENERATION / ACQUISITION
# ─────────────────────────────────────────────
def generate_synthetic_data(num_days=1825, num_stores=10, num_items=50):
    print("[INFO] Generating synthetic sales data...")
    start_date = datetime(2013, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(num_days)]
    stores = list(range(1, num_stores + 1))
    items = list(range(1, num_items + 1))

    item_base = {item: np.random.randint(10, 80) for item in items}
    store_multiplier = {store: np.random.uniform(0.8, 1.2) for store in stores}
    data = []

    for date in dates:
        days_passed = (date - start_date).days
        trend = 1.0 + (days_passed / 365) * 0.05
        seasonality = 1.0 + 0.3 * np.sin(2 * np.pi * date.timetuple().tm_yday / 365)
        weekend_mult = 1.25 if date.weekday() >= 5 else 1.0
        for store in stores:
            for item in items:
                base = item_base[item] * store_multiplier[store]
                noise = np.random.normal(1.0, 0.1)
                sales = max(0, int(base * trend * seasonality * weekend_mult * noise))
                data.append([date.strftime("%Y-%m-%d"), store, item, sales])

    df = pd.DataFrame(data, columns=["date", "store", "item", "sales"])
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv("data/raw/sales_data.csv", index=False)
    print(f"[INFO] Generated {len(df):,} records.")
    return df

def load_raw_data():
    try:
        import kagglehub
        print("[INFO] Attempting Kaggle download...")
        path = kagglehub.competition_download('demand-forecasting-kernels-only')
        shutil.copy2(os.path.join(path, "train.csv"), "data/raw/sales_data.csv")
        df = pd.read_csv("data/raw/sales_data.csv")
        print("[INFO] Kaggle dataset loaded successfully!")
        return df
    except Exception as e:
        print(f"[WARNING] Kaggle failed ({e}). Using synthetic data.")
        return generate_synthetic_data()

# ─────────────────────────────────────────────
# STEP 2: SAVE TO SQLITE DATABASE
# ─────────────────────────────────────────────
def save_to_database(df):
    """Save raw sales data to a SQLite relational database."""
    os.makedirs("data", exist_ok=True)
    print(f"\n[INFO] Connecting to SQLite database at {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a clean relational schema
    cursor.executescript("""
        DROP TABLE IF EXISTS stores;
        DROP TABLE IF EXISTS items;
        DROP TABLE IF EXISTS sales_records;

        CREATE TABLE stores (
            store_id   INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL
        );

        CREATE TABLE items (
            item_id    INTEGER PRIMARY KEY,
            item_name  TEXT NOT NULL
        );

        CREATE TABLE sales_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL,
            store_id    INTEGER NOT NULL,
            item_id     INTEGER NOT NULL,
            units_sold  INTEGER NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (item_id)  REFERENCES items(item_id)
        );
    """)

    # Named stores and items for realistic data
    STORE_NAMES = {
        1: "Apollo Supermart",
        2: "Green Valley Grocery",
        3: "Metro Fresh Market",
        4: "Sunrise Retail Hub",
        5: "City Centre Stores",
        6: "Lakeview Superstore",
        7: "Heritage General Store",
        8: "Nexus MegaMart",
        9: "BlueStar Express",
        10: "Eastern Trade Centre",
    }
    ITEM_NAMES = {
        1: "Premium Basmati Rice", 2: "Whole Wheat Bread", 3: "Full Cream Milk (1L)",
        4: "Farm Fresh Eggs (12pk)", 5: "Sunflower Cooking Oil", 6: "Refined Sugar (1kg)",
        7: "Iodised Salt (500g)", 8: "Turmeric Powder", 9: "Red Chilli Powder",
        10: "Coriander Seeds", 11: "Green Tea Bags", 12: "Instant Coffee",
        13: "Butter (200g)", 14: "Paneer (200g)", 15: "Cheddar Cheese Slices",
        16: "Orange Juice (1L)", 17: "Mango Juice (500ml)", 18: "Mineral Water (1L)",
        19: "Sparkling Water (500ml)", 20: "Energy Drink (250ml)", 21: "Potato Chips (100g)",
        22: "Multigrain Biscuits", 23: "Chocolate Cookies", 24: "Peanut Butter (350g)",
        25: "Strawberry Jam", 26: "Tomato Ketchup (500g)", 27: "Mustard Sauce",
        28: "Soya Sauce (200ml)", 29: "Apple Cider Vinegar", 30: "Pasta (500g)",
        31: "Spaghetti (500g)", 32: "Macaroni (500g)", 33: "Rolled Oats (1kg)",
        34: "Corn Flakes (400g)", 35: "Muesli Cereal (500g)", 36: "Dark Chocolate Bar",
        37: "Almonds (200g)", 38: "Cashews (200g)", 39: "Raisins (200g)",
        40: "Mixed Dry Fruits", 41: "Aloe Vera Shampoo", 42: "Moisturising Lotion",
        43: "Face Wash (100ml)", 44: "Toothpaste (150g)", 45: "Hand Sanitizer (200ml)",
        46: "Dishwashing Liquid", 47: "Laundry Detergent (1kg)", 48: "Floor Cleaner (1L)",
        49: "Toilet Cleaner", 50: "Air Freshener Spray",
    }

    # Insert dimension tables with real names
    stores = [(int(s), STORE_NAMES.get(int(s), f"Store {s}")) for s in sorted(df['store'].unique())]
    items  = [(int(i), ITEM_NAMES.get(int(i),  f"Item {i}"))  for i in sorted(df['item'].unique())]
    cursor.executemany("INSERT INTO stores VALUES (?, ?)", stores)
    cursor.executemany("INSERT INTO items  VALUES (?, ?)", items)

    # Insert fact table in batches for speed
    records = [(row['date'], int(row['store']), int(row['item']), int(row['sales'])) for _, row in df.iterrows()]
    cursor.executemany("INSERT INTO sales_records (date, store_id, item_id, units_sold) VALUES (?, ?, ?, ?)", records)

    conn.commit()
    conn.close()
    print(f"[INFO] {len(records):,} records saved to SQLite successfully!")

# ─────────────────────────────────────────────
# STEP 3: FEATURE ENGINEERING
# ─────────────────────────────────────────────
def feature_engineering(df):
    print("\n[INFO] Engineering ML features...")
    df['date'] = pd.to_datetime(df['date'])
    df = df.rename(columns={'store': 'store', 'item': 'item', 'sales': 'sales'})
    df = df.sort_values(by=['store', 'item', 'date']).reset_index(drop=True)

    df['year']         = df['date'].dt.year
    df['month']        = df['date'].dt.month
    df['day_of_week']  = df['date'].dt.dayofweek
    df['day_of_month'] = df['date'].dt.day
    df['is_weekend']   = df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)

    grouped = df.groupby(['store', 'item'])['sales']
    df['lag_1']  = grouped.shift(1)
    df['lag_7']  = grouped.shift(7)
    df['lag_30'] = grouped.shift(30)
    df['rolling_mean_7']  = grouped.transform(lambda x: x.shift(1).rolling(7).mean())
    df['rolling_mean_30'] = grouped.transform(lambda x: x.shift(1).rolling(30).mean())

    df = df.dropna().reset_index(drop=True)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv("data/processed/sales_processed.csv", index=False)
    print(f"[INFO] Feature engineering complete. Final shape: {df.shape}")
    return df

# ─────────────────────────────────────────────
# STEP 4: MODEL TRAINING
# ─────────────────────────────────────────────
def train_model(df):
    print("\n[INFO] Preparing data for training...")
    df = df.sort_values('date')
    split_date = df['date'].max() - pd.Timedelta(days=90)

    features = ['store', 'item', 'year', 'month', 'day_of_week', 'day_of_month',
                'is_weekend', 'lag_1', 'lag_7', 'lag_30', 'rolling_mean_7', 'rolling_mean_30']

    X_train = df[df['date'] <= split_date][features]
    y_train = df[df['date'] <= split_date]['sales']
    X_test  = df[df['date'] >  split_date][features]
    y_test  = df[df['date'] >  split_date]['sales']

    print(f"[INFO] Training XGBoost on {len(X_train):,} rows...")
    model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print("\n  === Model Evaluation (Last 90 Days) ===")
    print(f"  MAE  : {mean_absolute_error(y_test, preds):.2f}")
    print(f"  RMSE : {np.sqrt(mean_squared_error(y_test, preds)):.2f}")

    os.makedirs("models", exist_ok=True)
    joblib.dump({'model': model, 'features': features}, "models/sales_model.pkl")
    print("\n[INFO] Model saved to models/sales_model.pkl")

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  SALES FORECASTING ML PIPELINE")
    print("=" * 55)

    df_raw = load_raw_data()
    save_to_database(df_raw)      # <-- REAL DATABASE STEP
    df_processed = feature_engineering(df_raw)
    train_model(df_processed)

    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("  Run start.bat to launch the web application.")
    print("=" * 55)
