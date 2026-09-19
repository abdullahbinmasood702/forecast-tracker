-- Run this once in the Neon SQL Editor.

CREATE TABLE IF NOT EXISTS forecasts (
    id          SERIAL PRIMARY KEY,
    city        TEXT    NOT NULL,
    issued_date DATE    NOT NULL,   -- local date the forecast was made
    target_date DATE    NOT NULL,   -- local date being forecast
    lead_days   INT     NOT NULL,   -- 0 = same day, 1 = tomorrow, ... 7
    temp_max    REAL,
    temp_min    REAL,
    precip_sum  REAL,
    wind_max    REAL,
    UNIQUE (city, issued_date, target_date)
);

CREATE TABLE IF NOT EXISTS actuals (
    city        TEXT NOT NULL,
    date        DATE NOT NULL,
    temp_max    REAL,
    temp_min    REAL,
    precip_sum  REAL,
    wind_max    REAL,
    PRIMARY KEY (city, date)
);

-- Every forecast joined to what actually happened.
CREATE OR REPLACE VIEW forecast_errors AS
SELECT
    f.city,
    f.issued_date,
    f.target_date,
    f.lead_days,
    f.temp_max   AS fc_temp_max,
    f.temp_min   AS fc_temp_min,
    f.precip_sum AS fc_precip,
    f.wind_max   AS fc_wind,
    a.temp_max   AS act_temp_max,
    a.temp_min   AS act_temp_min,
    a.precip_sum AS act_precip,
    a.wind_max   AS act_wind,
    f.temp_max - a.temp_max      AS err_temp_max,
    ABS(f.temp_max - a.temp_max) AS abs_err_temp_max,
    ABS(f.temp_min - a.temp_min) AS abs_err_temp_min,
    ABS(f.precip_sum - a.precip_sum) AS abs_err_precip,
    ABS(f.wind_max - a.wind_max) AS abs_err_wind
FROM forecasts f
JOIN actuals a ON a.city = f.city AND a.date = f.target_date;
