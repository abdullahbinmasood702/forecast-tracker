"""Streamlit dashboard: python -m streamlit run app.py"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Forecast Accuracy Tracker", layout="wide")


@st.cache_resource
def get_engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@st.cache_data(ttl=600)
def load(query: str) -> pd.DataFrame:
    return pd.read_sql(query, get_engine())


st.title("Forecast Accuracy Tracker")
st.caption("How wrong are weather forecasts, and when? Data collected daily "
           "from Open-Meteo. 'Actual' = ERA5 reanalysis, not a weather station.")

errors = load("SELECT * FROM forecast_errors")
if errors.empty:
    st.info("No completed forecasts yet. Actual values arrive a few days "
            "after the forecast date. Check back soon.")
    st.stop()

errors["target_date"] = pd.to_datetime(errors["target_date"])

# Sidebar filter
cities = sorted(errors["city"].unique())
picked = st.sidebar.multiselect("Cities", cities, default=cities)
errors = errors[errors["city"].isin(picked)]

# Headline numbers
c1, c2, c3, c4 = st.columns(4)
c1.metric("Forecasts scored", f"{len(errors):,}")
c2.metric("Cities", errors["city"].nunique())
c3.metric("Avg temp error (deg C)", f"{errors['abs_err_temp_max'].mean():.2f}")
c4.metric("Data through", errors["target_date"].max().strftime("%Y-%m-%d"))

left, right = st.columns(2)

# Error vs lead time
by_lead = (errors.groupby(["city", "lead_days"], as_index=False)
           ["abs_err_temp_max"].mean())
fig = px.line(by_lead, x="lead_days", y="abs_err_temp_max", color="city",
              markers=True,
              labels={"lead_days": "Days ahead", "abs_err_temp_max": "Mean abs error (deg C)"},
              title="Error grows with lead time")
left.plotly_chart(fig, use_container_width=True)

# Error over time
daily = (errors.groupby(["city", "target_date"], as_index=False)
         ["abs_err_temp_max"].mean())
fig = px.line(daily, x="target_date", y="abs_err_temp_max", color="city",
              labels={"target_date": "Date", "abs_err_temp_max": "Mean abs error (deg C)"},
              title="Error over time")
right.plotly_chart(fig, use_container_width=True)

# Upcoming forecasts with typical error attached
st.subheader("Upcoming forecasts and how far to trust them")
upcoming = load("""
    SELECT DISTINCT ON (city, target_date)
           city, target_date, lead_days, temp_max, temp_min, precip_sum
    FROM forecasts
    WHERE target_date >= CURRENT_DATE
    ORDER BY city, target_date, issued_date DESC
""")
if not upcoming.empty:
    typical = by_lead.rename(columns={"abs_err_temp_max": "typical_error_c"})
    upcoming = upcoming.merge(typical, on=["city", "lead_days"], how="left")
    upcoming = upcoming[upcoming["city"].isin(picked)]
    upcoming["typical_error_c"] = upcoming["typical_error_c"].round(2)
    st.dataframe(upcoming, use_container_width=True, hide_index=True)
    st.caption("typical_error_c = historical average error for that city and lead time.")
