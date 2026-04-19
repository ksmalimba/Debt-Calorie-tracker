# 🔥 Tax Accountability App

Your workout. Your invoice. Your results.

Built on the **Accountability Tax Protocol** — a formula that ties your daily workout target directly to what you ate yesterday and your weekly weight loss goal.

## The Formula

```
ET = (Intake − TDEE) + (weekly_target_kg × kcal_per_kg / 7)
```

- **ET** = Exercise Target (kcal to burn today)
- **Intake** = What you ate yesterday
- **TDEE** = Your maintenance calories (auto-calculated via Mifflin-St Jeor)
- If ET > 800 kcal → debt is carried forward to the next day

---

## Local Setup

### 1. Clone & install
```bash
git clone <your-repo>
cd accountability-app
pip install -r requirements.txt
```

### 2. Set up environment
```bash
cp .env.example .env
# Leave defaults for local SQLite dev
```

### 3. Run
```bash
streamlit run app.py
```

---

## Deploy to Streamlit Cloud

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin <your-github-repo>
git push -u origin main
```

### 2. Set up Supabase
1. Create a free project at [supabase.com](https://supabase.com)
2. Run the SQL below in the Supabase SQL editor to create your tables
3. Copy your Project URL and anon key

### 3. Add Streamlit Secrets
In your Streamlit Cloud app settings → Secrets:
```toml
USE_SUPABASE = "true"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"
```

### Supabase SQL Schema
```sql
create table users (
  id serial primary key,
  email text unique not null,
  password_hash text not null,
  name text,
  height_cm real,
  weight_kg real,
  age integer,
  gender text,
  activity_level text,
  tdee real,
  target_weight real,
  weekly_target real default 0.5,
  kcal_per_kg real default 7700,
  created_at timestamptz default now()
);

create table daily_logs (
  id serial primary key,
  user_id integer references users(id),
  log_date date not null,
  calories_in real,
  tracked boolean default true,
  calories_burned real,
  notes text,
  unique(user_id, log_date)
);

create table debt_ledger (
  id serial primary key,
  user_id integer references users(id),
  debt_calories real not null,
  carried_from date not null,
  resolved boolean default false
);

create table weight_log (
  id serial primary key,
  user_id integer references users(id),
  log_date date not null,
  weight_kg real not null,
  unique(user_id, log_date)
);
```

---

## Project Structure

```
accountability-app/
├── app.py            ← Streamlit UI (all pages)
├── database.py       ← SQLite / Supabase data layer
├── auth.py           ← Login, register, session
├── calculations.py   ← All formulas (TDEE, tax, debt, audit)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Workout Tiers

| Tier | Target | Mode | BPM |
|------|--------|------|-----|
| 🟢 Green | < 350 kcal | Low intensity | 120–130 |
| 🟡 Yellow | 350–600 kcal | Steady state | 140–150 |
| 🔴 Red | > 600 kcal | Split AM/PM | 140–150 |
