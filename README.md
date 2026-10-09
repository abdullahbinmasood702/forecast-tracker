# Forecast Accuracy Tracker

Collects daily weather forecasts (1-7 days ahead) for several cities, later compares them
with what actually happened, models when forecasts are most wrong, and shows it all on a
live dashboard.

```
Open-Meteo API --> GitHub Actions (daily) --> Neon Postgres --> analysis.py (Colab/local) + W&B
                                                     |
                                                     +--> app.py (Streamlit on Render)
```

| Piece | Tool | Cost |
|---|---|---|
| Weather data | Open-Meteo (no API key) | free, non-commercial use |
| Scheduler | GitHub Actions cron | free |
| Database | Neon Postgres | free tier |
| Analysis | Colab or local Python | free |
| Experiment tracking | Weights & Biases | free for personal projects |
| Dashboard hosting | Render web service | free tier |

Why Open-Meteo instead of Tomorrow.io/WeatherXu (listed in free-for-dev)? It needs no key
and has a free archive of past weather, which we need to score the forecasts.

---

## Results (as of Oct 8, 2026)

Based on 324 scored forecasts across 3 cities (Islamabad, London, New York) over about 3 weeks.

**1. Forecast error grows with lead time, as expected**
Same-day forecasts (lead_days = 0) were off by 0.58°C on average. By 7 days out, that grew to roughly
1.5-2.0°C. Day 7 showed a slight dip below day 6 in this sample, likely noise from the small sample
size (30 rows) at that lead time rather than a real pattern.

![Error grows with lead time](mae_by_lead.png)

**2. Forecast reliability varies a lot by city, not just by lead time**
New York was consistently the hardest city to forecast — its error was close to double Islamabad's at
most lead times (e.g. day 6: 3.22°C vs 1.35°C). Location matters as much as how far ahead you look.

**3. Rain forecasts also get less reliable further out**
The forecast correctly predicted rain/no-rain 90% of the time same-day, dropping to 67-75% by day 6-7.

**4. A simple model beat the naive baseline**
I trained 3 models (Ridge, Random Forest, Gradient Boosting) to predict how wrong a forecast's max
temperature would be, using lead time and the forecast's own values as features, with a time-based
train/test split (no shuffling, since this is time series data).

| Model | Test MAE (°C) |
|---|---|
| **Ridge regression** | **0.495** |
| Random Forest | 0.670 |
| Gradient Boosting | 0.676 |
| Baseline (avg error per lead time) | 0.692 |

Ridge regression beat the baseline by about 28%. The tree-based models (Random Forest, Gradient
Boosting) didn't beat the baseline here, most likely because 261 training rows isn't enough for them
to outperform a simpler linear model — tree ensembles typically need more data to show their advantage.

**Live dashboard:** https://forecast-tracker.streamlit.app

## Step 0: What you need
- Python 3.10+ and Git installed (`python --version`, `git --version`)
- A GitHub account
- About 1 hour for setup, then 2-3 weeks of waiting for data

## Step 1: Create the database (Neon)
1. Sign up at neon.tech and create a project (any name, e.g. `forecast-tracker`).
2. On the project dashboard, copy the **connection string**. It looks like
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`.
   Treat it like a password. Never commit it to GitHub.
3. Open **SQL Editor** in Neon, paste the whole of `schema.sql`, and run it.
   You now have tables `forecasts`, `actuals` and a view `forecast_errors`.

## Step 2: Run the collector on your computer once
```bash
cd forecast-tracker
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="paste-your-neon-string-here"     # Windows PowerShell: $env:DATABASE_URL="..."
python collect.py                  # should print: Stored 24 forecast rows for 3 cities.
python actuals.py                  # prints 0 now; nothing is old enough yet
```
Check it worked: Neon -> Tables -> `forecasts` should show 24 rows.

Edit `config.py` to change cities. Coordinates: search "<city> latitude longitude".
More cities = more data = better model. Keep it to 3-6.

## Step 3: Automate it (GitHub Actions)
1. Create a new GitHub repo (public is good for a portfolio) and push:
   ```bash
   git init
   git add .
   git commit -m "Forecast tracker: collector"
   git branch -M main
   git remote add origin https://github.com/<you>/forecast-tracker.git
   git push -u origin main
   ```
2. In the repo: **Settings -> Secrets and variables -> Actions -> New repository secret**.
   Name: `DATABASE_URL`, value: your Neon string.
3. Go to the **Actions** tab -> "Collect weather data" -> **Run workflow**. It should go green.
4. From now on it runs daily at 03:00 UTC by itself.

Things to know:
- GitHub can delay scheduled runs by many minutes. That's normal.
- GitHub pauses scheduled workflows after 60 days without repo activity. Push a small
  commit now and then.
- Do not fix a failing run by pasting the secret into code.

## Step 4: Wait
`actuals.py` only fills a date once Open-Meteo's archive has it (a few days lag).
After about 10 days you have the first scored forecasts. Aim for 3 weeks or more.
Check in Neon SQL Editor:
```sql
SELECT COUNT(*) FROM forecast_errors;
SELECT lead_days, ROUND(AVG(abs_err_temp_max)::numeric, 2) AS mae
FROM forecast_errors GROUP BY lead_days ORDER BY lead_days;
```
(Use the wait to build the dashboard and write the README/article skeleton.)

## Step 5: Analysis and modeling
```bash
pip install -r requirements-analysis.txt
export DATABASE_URL="..."
wandb login                        # optional: get a free key at wandb.ai
python analysis.py
```
What it does:
1. Loads `forecast_errors`.
2. Prints error by lead time and city, and rain hit-rate.
3. Saves `mae_by_lead.png`.
4. Trains Ridge, Random Forest and Gradient Boosting to predict `abs_err_temp_max`,
   using a time-based train/test split (last 20% of days = test).
5. Compares them against a baseline (average error for that lead time) and logs each run
   to Weights & Biases if `WANDB_API_KEY` is set.

**Be honest with the results.** Forecast error mostly depends on lead time, so a fancy
model may not beat the baseline. Reporting that is a stronger result than hiding it.
Ideas to improve it once you have more data: add month, weekday, previous-day error,
forecast change between yesterday's and today's forecast for the same target date.

To use Colab: upload the repo files or paste blocks, `!pip install -r requirements-analysis.txt`,
and set the secret with
```python
import os
from google.colab import userdata
os.environ["DATABASE_URL"] = userdata.get("DATABASE_URL")
```

## Step 6: Dashboard
Local test:
```bash
pip install -r requirements-app.txt
export DATABASE_URL="..."
python -m streamlit run app.py
```
Deploy on Render:
1. render.com -> New -> **Web Service** -> connect your GitHub repo.
2. Runtime: Python. Instance type: **Free**.
3. Build command: `pip install -r requirements-app.txt`
4. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. Environment: add `DATABASE_URL` with your Neon string.
6. Deploy. You get a public `onrender.com` link.

Free-tier behavior: the app sleeps when idle, so the first visit can take up to about a
minute. Neon also auto-suspends, causing a slow first query. Mention this in the README
so recruiters aren't confused. (Alternative host: Hugging Face Spaces with Streamlit.)

## Step 7: Polish for your resume
- Add a screenshot of the dashboard and a link to the live app at the top of the repo README.
- Add an architecture diagram (the block above is fine).
- Write a short article (Dev.to / Hashnode): problem, data pipeline, findings, what didn't
  work. Include one chart.
- Pin the repo on your GitHub profile and add it under Projects on LinkedIn.

Resume bullet (edit numbers to match reality):
> Built an automated pipeline (GitHub Actions, PostgreSQL) collecting daily weather forecasts
> across N cities and scoring them against observed outcomes; modeled forecast error with
> scikit-learn (tracked in Weights & Biases) and deployed a live Streamlit dashboard.

## Troubleshooting
| Problem | Fix |
|---|---|
| `KeyError: 'DATABASE_URL'` | Env var not set in that terminal, or secret missing in GitHub. |
| `SSL` / connection errors | Make sure the string ends with `?sslmode=require`. |
| Workflow fails on `actuals.py` | Read the log. Usually a network blip; it self-heals next day. |
| `forecast_errors` empty | Normal for the first ~4-10 days. Actuals lag. |
| Analysis says not enough rows | Wait longer or add cities. |
| Render app crashes on boot | Check logs. Usually missing `DATABASE_URL` or wrong start command. |

## Limits and honesty notes
- "Actual" values are ERA5 reanalysis (a model blended with observations), not readings
  from a weather station. Say so in your write-up.
- Open-Meteo's free API is for non-commercial use. Keep the request volume low (this
  project makes about 6 calls per day).
- Neon's free tier has a small storage cap. This project adds about 24 rows per day
  for 3 cities, far below it.
- Check each service's current free limits before relying on them.

## Files
```
config.py            cities and variables
db.py                database connection
collect.py           daily forecast collector
actuals.py           fills in what really happened
schema.sql           tables + forecast_errors view
analysis.py          EDA + models + W&B
app.py               Streamlit dashboard
.github/workflows/collect.yml   daily schedule
```
