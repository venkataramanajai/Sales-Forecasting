from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sqlite3
import joblib
import os

app = FastAPI(title="Sales Forecasting API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join("data", "sales.db")

model_data = None
df_processed = None

def load_resources():
    global model_data, df_processed
    model_path = os.path.join("models", "sales_model.pkl")
    processed_path = os.path.join("data", "processed", "sales_processed.csv")

    if os.path.exists(model_path):
        model_data = joblib.load(model_path)
        print("Model loaded.")

    if os.path.exists(processed_path):
        df_processed = pd.read_csv(processed_path)
        df_processed['date'] = pd.to_datetime(df_processed['date'])
        print("Processed data loaded.")

load_resources()

def get_db():
    """Return a live SQLite connection."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not found. Run train.py first.")
    return sqlite3.connect(DB_PATH)

class ForecastRequest(BaseModel):
    store: int
    item: int
    target_date: str

# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/meta")
def get_metadata():
    """Fetch available stores and items (with names) from the SQLite DB."""
    conn = get_db()
    stores = [{"id": r[0], "name": r[1]} for r in conn.execute("SELECT store_id, store_name FROM stores ORDER BY store_id").fetchall()]
    items  = [{"id": r[0], "name": r[1]} for r in conn.execute("SELECT item_id,  item_name  FROM items  ORDER BY item_id").fetchall()]
    conn.close()

    if df_processed is None:
        raise HTTPException(status_code=500, detail="Processed data not loaded.")

    max_date = df_processed['date'].max().strftime("%Y-%m-%d")
    return {"stores": stores, "items": items, "max_historical_date": max_date}

@app.post("/predict")
def generate_forecast(req: ForecastRequest):
    """Generate an AI forecast. Queries DB for history, then runs XGBoost."""
    if model_data is None or df_processed is None:
        raise HTTPException(status_code=500, detail="Model or data not loaded. Run train.py first.")

    try:
        target_dt = pd.to_datetime(req.target_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # ── 1. Fetch last 90 days of sales FROM SQLite DB ──────────────────────
    conn = get_db()
    rows = conn.execute("""
        SELECT date, units_sold
        FROM   sales_records
        WHERE  store_id = ? AND item_id = ?
        ORDER  BY date DESC
        LIMIT  90
    """, (req.store, req.item)).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this Store/Item combination.")

    history = [{"date": r[0], "sales": r[1]} for r in reversed(rows)]

    # ── 2. Build ML feature vector from processed data ─────────────────────
    store_item_df = df_processed[
        (df_processed['store'] == req.store) & (df_processed['item'] == req.item)
    ].sort_values('date')

    if store_item_df.empty:
        raise HTTPException(status_code=404, detail="No processed features for this Store/Item.")

    last = store_item_df.iloc[-1]

    input_dict = {
        'store': req.store,
        'item': req.item,
        'year': target_dt.year,
        'month': target_dt.month,
        'day_of_week': target_dt.dayofweek,
        'day_of_month': target_dt.day,
        'is_weekend': 1 if target_dt.dayofweek >= 5 else 0,
        'lag_1':  last['sales'],
        'lag_7':  last['lag_7'],
        'lag_30': last['lag_30'],
        'rolling_mean_7':  last['rolling_mean_7'],
        'rolling_mean_30': last['rolling_mean_30'],
    }

    input_df = pd.DataFrame([input_dict])[model_data['features']]
    prediction = max(0, int(round(model_data['model'].predict(input_df)[0])))

    return {
        "prediction": prediction,
        "target_date": target_dt.strftime("%Y-%m-%d"),
        "store": req.store,
        "item": req.item,
        "history": history,
        "last_rolling_7": round(last['rolling_mean_7']),
    }

@app.get("/db/summary")
def database_summary():
    """Return summary statistics directly from the SQLite database."""
    conn = get_db()
    total_records  = conn.execute("SELECT COUNT(*) FROM sales_records").fetchone()[0]
    total_stores   = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
    total_items    = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    date_range     = conn.execute("SELECT MIN(date), MAX(date) FROM sales_records").fetchone()
    conn.close()
    return {
        "total_records": total_records,
        "total_stores": total_stores,
        "total_items": total_items,
        "date_from": date_range[0],
        "date_to": date_range[1],
        "database_path": DB_PATH
    }
