"""EDA + model that predicts how wrong a temperature forecast will be.

Run locally:   python analysis.py
Run in Colab:  paste each "# %%" block into its own cell.
Needs DATABASE_URL (env var) and optionally WANDB_API_KEY.
"""
# %% Load data
import os

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(os.environ["DATABASE_URL"])
df = pd.read_sql("SELECT * FROM forecast_errors", engine,
                 parse_dates=["issued_date", "target_date"])
print(df.shape)
print(df.head())
assert len(df) > 50, "Not enough joined rows yet - let the collector run longer."

# %% EDA: error by lead time and city
print("\nMean absolute error of max temperature by lead time (deg C):")
print(df.groupby("lead_days")["abs_err_temp_max"].mean().round(2))

print("\nMAE by city and lead time:")
print(df.pivot_table(index="lead_days", columns="city",
                     values="abs_err_temp_max", aggfunc="mean").round(2))

# Rain: did "rain > 1 mm" get forecast correctly?
df["fc_rain"] = df["fc_precip"] > 1
df["act_rain"] = df["act_precip"] > 1
print("\nRain hit rate by lead time:")
print((df["fc_rain"] == df["act_rain"]).groupby(df["lead_days"]).mean().round(3))

# %% Plot
import matplotlib.pyplot as plt

mae = df.pivot_table(index="lead_days", columns="city",
                     values="abs_err_temp_max", aggfunc="mean")
mae.plot(marker="o", figsize=(7, 4))
plt.ylabel("Mean absolute error (deg C)")
plt.title("Forecast error grows with lead time")
plt.tight_layout()
plt.savefig("mae_by_lead.png", dpi=150)

# %% Features
df["fc_range"] = df["fc_temp_max"] - df["fc_temp_min"]
df["month"] = df["target_date"].dt.month
FEATURES_NUM = ["lead_days", "fc_temp_max", "fc_range", "fc_precip", "fc_wind"]
FEATURES_CAT = ["city"]
TARGET = "abs_err_temp_max"

df = df.dropna(subset=FEATURES_NUM + FEATURES_CAT + [TARGET]).sort_values("issued_date")

# Time-based split (never shuffle time series): last 20% of days = test
cut = df["issued_date"].quantile(0.8)
train, test = df[df["issued_date"] <= cut], df[df["issued_date"] > cut]
print(f"train={len(train)}  test={len(test)}")

# %% Models
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

USE_WANDB = bool(os.getenv("WANDB_API_KEY"))
if USE_WANDB:
    import wandb


def make(model):
    pre = ColumnTransformer([
        ("num", StandardScaler(), FEATURES_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT),
    ])
    return Pipeline([("pre", pre), ("model", model)])


candidates = {
    "ridge": Ridge(alpha=1.0),
    "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=5, random_state=0),
    "gradient_boosting": GradientBoostingRegressor(random_state=0),
}

# Baseline: predict the average error for that lead time
base_pred = test["lead_days"].map(train.groupby("lead_days")[TARGET].mean())
base_pred = base_pred.fillna(train[TARGET].mean())
results = {"baseline_by_lead": mean_absolute_error(test[TARGET], base_pred)}

for name, model in candidates.items():
    pipe = make(model).fit(train[FEATURES_NUM + FEATURES_CAT], train[TARGET])
    pred = pipe.predict(test[FEATURES_NUM + FEATURES_CAT])
    results[name] = mean_absolute_error(test[TARGET], pred)

    if USE_WANDB:
        run = wandb.init(project="forecast-error", name=name,
                         config={"model": name, "n_train": len(train)}, reinit=True)
        wandb.log({"test_mae": results[name]})
        run.finish()

print("\nTest MAE (deg C), lower is better:")
for k, v in sorted(results.items(), key=lambda kv: kv[1]):
    print(f"  {k:20s} {v:.3f}")
print("\nIf no model beats 'baseline_by_lead', say so in your write-up.")
