import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta

from database import (
    init_db, upsert_daily_log, get_log_for_date, get_logs_for_range,
    add_debt, get_active_debt, get_total_active_debt, resolve_debt,
    upsert_weight, get_weight_history, update_user_profile, get_user_by_id
)
from auth import (
    login_user, register_user, set_session, clear_session,
    current_user, is_logged_in
)
from calculations import (
    calculate_tdee, calculate_exercise_target, split_target_if_needed,
    effective_target_with_debt, weekly_audit, kg_to_goal,
    estimated_weeks_to_goal, kcal_to_minutes, ACTIVITY_MULTIPLIERS
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tax Accountability",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init DB ────────────────────────────────────────────────────────────────────
init_db()

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg:       #0d0d0d;
    --surface:  #161616;
    --border:   #2a2a2a;
    --accent:   #e8ff47;
    --accent2:  #ff6b35;
    --text:     #f0f0f0;
    --muted:    #888;
    --green:    #4ade80;
    --red:      #f87171;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Syne', sans-serif;
}

[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border);
}

h1, h2, h3 { font-family: 'Syne', sans-serif; font-weight: 800; }

.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.metric-label {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 6px;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 36px;
    font-weight: 800;
    color: var(--accent);
    line-height: 1;
}
.metric-sub {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    margin-top: 4px;
}
.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
.tag-green { background: rgba(74,222,128,0.15); color: var(--green); border: 1px solid var(--green); }
.tag-red   { background: rgba(248,113,113,0.15); color: var(--red);   border: 1px solid var(--red); }
.tag-yellow{ background: rgba(232,255,71,0.15);  color: var(--accent); border: 1px solid var(--accent); }
.tag-orange{ background: rgba(255,107,53,0.15);  color: var(--accent2);border: 1px solid var(--accent2); }

.debt-banner {
    background: rgba(255,107,53,0.1);
    border: 1px solid var(--accent2);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 20px;
}

.stButton > button {
    background: var(--accent) !important;
    color: #000 !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    letter-spacing: 1px !important;
}
.stButton > button:hover {
    background: #d4eb00 !important;
}

.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stRadio > div {
    background-color: var(--surface) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}

[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
}

.section-title {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 3px;
    margin: 28px 0 14px 0;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def tier_tag(kcal):
    if kcal < 350:
        return '<span class="tag tag-green">TIER 1 — GREEN</span>'
    elif kcal < 600:
        return '<span class="tag tag-yellow">TIER 2 — YELLOW</span>'
    else:
        return '<span class="tag tag-orange">TIER 3 — RED</span>'


def plotly_dark_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Space Mono", color="#888", size=11),
        xaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
        yaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
        margin=dict(l=10, r=10, t=30, b=10),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH PAGES
# ═══════════════════════════════════════════════════════════════════════════════

def page_login():
    st.markdown("<br>", unsafe_allow_html=True)
    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("## 🔥 TAX ACCOUNTABILITY")
        st.markdown('<p style="color:#888;font-family:Space Mono,monospace;font-size:13px;">Your workout. Your invoice. Your results.</p>', unsafe_allow_html=True)
        st.markdown("---")

        tab_login, tab_reg = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            email = st.text_input("Email", key="li_email")
            password = st.text_input("Password", type="password", key="li_pass")
            if st.button("SIGN IN", key="btn_login"):
                user = login_user(email, password)
                if user:
                    set_session(user)
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

        with tab_reg:
            _registration_form()


def _registration_form():
    st.markdown('<p class="section-title">Personal Info</p>', unsafe_allow_html=True)
    name     = st.text_input("Full Name", key="r_name")
    email    = st.text_input("Email", key="r_email")
    password = st.text_input("Password", type="password", key="r_pass")
    password2= st.text_input("Confirm Password", type="password", key="r_pass2")

    st.markdown('<p class="section-title">Body Stats</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        gender     = st.selectbox("Gender", ["Male", "Female"], key="r_gender")
        age        = st.number_input("Age", 16, 90, 30, key="r_age")
        height_cm  = st.number_input("Height (cm)", 140.0, 220.0, 175.0, key="r_height")
    with c2:
        weight_kg  = st.number_input("Current Weight (kg)", 40.0, 250.0, 85.0, key="r_weight")
        target_wt  = st.number_input("Target Weight (kg)", 40.0, 250.0, 75.0, key="r_target")
        weekly_tgt = st.number_input("Weekly Loss Goal (kg)", 0.1, 1.5, 0.5, step=0.05, key="r_weekly")

    activity = st.selectbox("Activity Level", list(ACTIVITY_MULTIPLIERS.keys()), key="r_activity")

    # Live TDEE preview
    if height_cm and weight_kg and age and gender and activity:
        tdee = calculate_tdee(weight_kg, height_cm, int(age), gender, activity)
        st.info(f"📊 Estimated TDEE: **{tdee:.0f} kcal/day**")
    else:
        tdee = 2200

    if st.button("CREATE ACCOUNT", key="btn_register"):
        if password != password2:
            st.error("Passwords do not match.")
            return
        if not name or not email or not password:
            st.error("Please fill in all fields.")
            return
        ok, err = register_user(
            email, password, name, height_cm, weight_kg, int(age),
            gender, activity, tdee, target_wt, weekly_tgt
        )
        if ok:
            user = login_user(email, password)
            set_session(user)
            st.success("Account created!")
            st.rerun()
        else:
            st.error(err)


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar(user):
    with st.sidebar:
        st.markdown(f"### 👋 {user['name'].split()[0]}")
        st.markdown(f'<span class="tag tag-green">ACTIVE</span>', unsafe_allow_html=True)
        st.markdown("---")

        page = st.radio("Navigate", [
            "🏠  Dashboard",
            "📋  Daily Log",
            "⚖️  Weight Log",
            "📊  History",
            "⚙️  Settings",
        ], label_visibility="collapsed")

        st.markdown("---")
        if st.button("SIGN OUT"):
            clear_session()
            st.rerun()

        # Quick stats in sidebar
        st.markdown('<p class="section-title">Your Profile</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">TDEE: <span style="color:#e8ff47">{user["tdee"]:.0f} kcal</span></p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Goal: <span style="color:#e8ff47">-{user["weekly_target"]} kg/wk</span></p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Weight: <span style="color:#e8ff47">{user["weight_kg"]} kg</span></p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Target: <span style="color:#4ade80">{user["target_weight"]} kg</span></p>', unsafe_allow_html=True)

    return page.split("  ")[-1].strip()


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard(user):
    today = date.today()
    yesterday = today - timedelta(days=1)

    st.markdown("# DASHBOARD")
    st.markdown(f'<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">{today.strftime("%A, %d %B %Y")}</p>', unsafe_allow_html=True)

    # ── Yesterday's log ───────────────────────────────────────────────────────
    ylog = get_log_for_date(user["id"], yesterday)
    calories_in = ylog["calories_in"] if ylog and ylog["calories_in"] else None
    tracked = bool(ylog["tracked"]) if ylog else False

    # ── Active debt ───────────────────────────────────────────────────────────
    active_debt = get_total_active_debt(user["id"])

    # ── Calculate today's target ──────────────────────────────────────────────
    if calories_in:
        base_et = calculate_exercise_target(
            calories_in, user["tdee"], user["weekly_target"],
            user.get("kcal_per_kg", 7700), tracked
        )
    else:
        base_et = calculate_exercise_target(
            user["tdee"], user["tdee"], user["weekly_target"],
            user.get("kcal_per_kg", 7700), True
        )
        st.warning("⚠️ No intake logged for yesterday. Using your TDEE as the estimate. Log yesterday's intake for accuracy.")

    today_target, new_debt_preview = effective_target_with_debt(base_et, active_debt)
    approx_minutes = kcal_to_minutes(today_target)

    # ── Debt banner ───────────────────────────────────────────────────────────
    if active_debt > 0:
        st.markdown(f"""
        <div class="debt-banner">
            <span style="font-family:Space Mono,monospace;font-size:11px;color:#ff6b35;letter-spacing:2px;">⚠️ OUTSTANDING DEBT</span><br>
            <span style="font-size:28px;font-weight:800;color:#ff6b35;">{active_debt:.0f} kcal</span>
            <span style="font-family:Space Mono,monospace;font-size:12px;color:#888;"> carried forward</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Top metrics ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Today's Tax</div>
            <div class="metric-value">{today_target:.0f}</div>
            <div class="metric-sub">kcal to burn</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Approx Time</div>
            <div class="metric-value">{approx_minutes}</div>
            <div class="metric-sub">minutes on bike</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        yin = f"{calories_in:.0f}" if calories_in else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Yesterday Intake</div>
            <div class="metric-value">{yin}</div>
            <div class="metric-sub">kcal consumed</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        gap = kg_to_goal(user["weight_kg"], user["target_weight"])
        wks = estimated_weeks_to_goal(user["weight_kg"], user["target_weight"], user["weekly_target"])
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">To Goal</div>
            <div class="metric-value">{gap:.1f}</div>
            <div class="metric-sub">kg · ~{wks} weeks</div>
        </div>""", unsafe_allow_html=True)

    # ── Tier tag ──────────────────────────────────────────────────────────────
    st.markdown(f'<br>{tier_tag(today_target)}&nbsp;&nbsp;', unsafe_allow_html=True)
    if today_target < 350:
        st.markdown('<span style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Easy day — 120–130 BPM. Scroll emails.</span>', unsafe_allow_html=True)
    elif today_target < 600:
        st.markdown('<span style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Steady state — 140–150 BPM. Rhythmic breathing.</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="font-family:Space Mono,monospace;font-size:12px;color:#888;">High output — consider splitting AM/PM to manage cortisol.</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Today's burn log ──────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Log Today\'s Burn</p>', unsafe_allow_html=True)
    tlog = get_log_for_date(user["id"], today)
    current_burned = tlog["calories_burned"] if tlog and tlog["calories_burned"] else 0.0

    col_a, col_b = st.columns([2, 1])
    with col_a:
        burned_input = st.number_input(
            "Calories burned today", 0.0, 3000.0,
            float(current_burned), step=10.0, key="burn_input"
        )
    with col_b:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("SAVE BURN"):
            upsert_daily_log(user["id"], today, calories_burned=burned_input)

            # Resolve or add debt
            if burned_input >= today_target:
                debts = get_active_debt(user["id"])
                for d in debts:
                    resolve_debt(d["id"])
                st.success(f"🎯 Target hit! {burned_input:.0f} / {today_target:.0f} kcal")
            else:
                shortfall = today_target - burned_input
                if shortfall > 50:
                    add_debt(user["id"], shortfall, today)
                st.info(f"Logged {burned_input:.0f} kcal. Shortfall of {today_target - burned_input:.0f} kcal carried forward.")
            st.rerun()

    # ── Progress bar ──────────────────────────────────────────────────────────
    if today_target > 0:
        pct = min(1.0, current_burned / today_target)
        bar_color = "#4ade80" if pct >= 1.0 else "#e8ff47"
        st.markdown(f"""
        <div style="margin-top:16px;">
            <div style="font-family:Space Mono,monospace;font-size:11px;color:#888;margin-bottom:6px;">
                PROGRESS — {current_burned:.0f} / {today_target:.0f} kcal ({pct*100:.0f}%)
            </div>
            <div style="background:#2a2a2a;border-radius:6px;height:10px;width:100%;">
                <div style="background:{bar_color};border-radius:6px;height:10px;width:{pct*100:.1f}%;transition:width 0.4s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Weekly snapshot ───────────────────────────────────────────────────────
    st.markdown('<p class="section-title">This Week\'s Snapshot</p>', unsafe_allow_html=True)
    week_start = today - timedelta(days=today.weekday())
    logs = get_logs_for_range(user["id"], week_start, today)
    if logs:
        audit = weekly_audit(logs, user["tdee"], user["weekly_target"], user.get("kcal_per_kg", 7700))
        w1, w2, w3, w4 = st.columns(4)
        with w1: st.metric("Total In", f"{audit['total_in']:.0f} kcal")
        with w2: st.metric("Total Burned", f"{audit['total_burned']:.0f} kcal")
        with w3: st.metric("Net Deficit", f"{audit['deficit_achieved']:.0f} kcal")
        with w4:
            status = "✅ On Track" if audit["on_track"] else "⚠️ Off Track"
            st.metric("Status", status)
    else:
        st.markdown('<p style="color:#888;font-family:Space Mono,monospace;font-size:12px;">No logs this week yet.</p>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY LOG
# ═══════════════════════════════════════════════════════════════════════════════

def page_daily_log(user):
    st.markdown("# DAILY LOG")
    st.markdown('<p style="font-family:Space Mono,monospace;font-size:12px;color:#888;">Log what you ate yesterday to calculate today\'s tax.</p>', unsafe_allow_html=True)

    yesterday = date.today() - timedelta(days=1)
    log_date = st.date_input("Log Date", yesterday, max_value=date.today())
    existing = get_log_for_date(user["id"], log_date)

    c1, c2 = st.columns(2)
    with c1:
        default_in = float(existing["calories_in"]) if existing and existing["calories_in"] else 0.0
        calories_in = st.number_input("Total Calories Consumed", 0.0, 10000.0, default_in, step=50.0)
        tracked = st.checkbox("I tracked this accurately", value=bool(existing["tracked"]) if existing else True)
    with c2:
        default_burned = float(existing["calories_burned"]) if existing and existing["calories_burned"] else 0.0
        calories_burned = st.number_input("Calories Burned (exercise)", 0.0, 5000.0, default_burned, step=10.0)
        notes = st.text_area("Notes (optional)", value=existing["notes"] or "" if existing else "", height=100)

    if calories_in > 0:
        et = calculate_exercise_target(
            calories_in, user["tdee"], user["weekly_target"],
            user.get("kcal_per_kg", 7700), tracked
        )
        today_target, carry = split_target_if_needed(et)
        mins = kcal_to_minutes(today_target)

        st.markdown(f"""
        <div class="metric-card" style="margin-top:16px;">
            <div class="metric-label">Calculated Tax for Next Day</div>
            <div class="metric-value">{today_target:.0f} <span style="font-size:18px;color:#888;">kcal</span></div>
            <div class="metric-sub">≈ {mins} minutes on bike</div>
            {"<br><span style='font-family:Space Mono,monospace;font-size:12px;color:#ff6b35;'>⚠️ " + str(carry) + " kcal will carry forward to the day after.</span>" if carry > 0 else ""}
        </div>
        """, unsafe_allow_html=True)
        st.markdown(tier_tag(today_target), unsafe_allow_html=True)

    if st.button("SAVE LOG"):
        upsert_daily_log(
            user["id"], log_date, calories_in if calories_in > 0 else None,
            int(tracked), calories_burned if calories_burned > 0 else None, notes
        )
        st.success(f"✅ Log saved for {log_date.strftime('%d %b %Y')}")


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT LOG
# ═══════════════════════════════════════════════════════════════════════════════

def page_weight_log(user):
    st.markdown("# WEIGHT LOG")

    c1, c2 = st.columns([2, 1])
    with c1:
        new_weight = st.number_input(
            "Today's Weight (kg)", 30.0, 300.0,
            float(user["weight_kg"]), step=0.1
        )
        weigh_date = st.date_input("Date", date.today(), max_value=date.today())
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("LOG WEIGHT"):
            upsert_weight(user["id"], weigh_date, new_weight)
            # Recalculate TDEE with new weight
            new_tdee = calculate_tdee(
                new_weight, user["height_cm"], user["age"],
                user["gender"], user["activity_level"]
            )
            update_user_profile(user["id"], weight_kg=new_weight, tdee=new_tdee)
            st.success(f"✅ Weight logged: {new_weight} kg | New TDEE: {new_tdee:.0f} kcal")
            st.session_state["user"] = get_user_by_id(user["id"])
            st.rerun()

    # ── Weight chart ──────────────────────────────────────────────────────────
    history = get_weight_history(user["id"])
    if len(history) >= 2:
        df = pd.DataFrame(history)
        df["log_date"] = pd.to_datetime(df["log_date"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["log_date"], y=df["weight_kg"],
            mode="lines+markers",
            line=dict(color="#e8ff47", width=2),
            marker=dict(size=6, color="#e8ff47"),
            name="Weight"
        ))
        fig.add_hline(
            y=user["target_weight"], line_dash="dash",
            line_color="#4ade80", annotation_text="Target",
            annotation_font_color="#4ade80"
        )
        fig.update_layout(
            title="Weight Over Time",
            yaxis_title="kg",
            **plotly_dark_layout()
        )
        st.plotly_chart(fig, use_container_width=True)

        # Stats
        start_w = history[0]["weight_kg"]
        current_w = history[-1]["weight_kg"]
        lost = start_w - current_w
        col1, col2, col3 = st.columns(3)
        col1.metric("Start Weight", f"{start_w} kg")
        col2.metric("Current Weight", f"{current_w} kg")
        col3.metric("Total Lost", f"{lost:.1f} kg", delta=f"{-lost:.1f} kg")
    else:
        st.info("Log at least 2 weigh-ins to see your progress chart.")


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

def page_history(user):
    st.markdown("# HISTORY")

    period = st.selectbox("Period", ["Last 7 days", "Last 14 days", "Last 30 days"])
    days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}
    n = days_map[period]

    end = date.today()
    start = end - timedelta(days=n)
    logs = get_logs_for_range(user["id"], start, end)

    if not logs:
        st.info("No logs found for this period.")
        return

    df = pd.DataFrame(logs)
    df["log_date"] = pd.to_datetime(df["log_date"])
    df["calories_in"] = df["calories_in"].fillna(0)
    df["calories_burned"] = df["calories_burned"].fillna(0)
    df["net"] = df["calories_in"] - user["tdee"] - df["calories_burned"]

    # ── Intake vs Burn chart ──────────────────────────────────────────────────
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=df["log_date"], y=df["calories_in"], name="Intake", marker_color="#e8ff47"))
    fig1.add_trace(go.Bar(x=df["log_date"], y=df["calories_burned"], name="Burned", marker_color="#4ade80"))
    fig1.add_hline(y=user["tdee"], line_dash="dash", line_color="#ff6b35",
                   annotation_text="TDEE", annotation_font_color="#ff6b35")
    fig1.update_layout(
        title="Intake vs Burned",
        barmode="group",
        **plotly_dark_layout()
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ── Net daily chart ───────────────────────────────────────────────────────
    fig2 = go.Figure()
    colors = ["#f87171" if v > 0 else "#4ade80" for v in df["net"]]
    fig2.add_trace(go.Bar(x=df["log_date"], y=df["net"], marker_color=colors, name="Net"))
    fig2.add_hline(y=0, line_color="#888", line_width=1)
    fig2.update_layout(title="Daily Net (Surplus / Deficit)", **plotly_dark_layout())
    st.plotly_chart(fig2, use_container_width=True)

    # ── Table ─────────────────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Raw Log</p>', unsafe_allow_html=True)
    display = df[["log_date", "calories_in", "calories_burned", "net", "tracked"]].copy()
    display.columns = ["Date", "Intake", "Burned", "Net", "Tracked"]
    display["Date"] = display["Date"].dt.strftime("%d %b")
    display["Tracked"] = display["Tracked"].map({1: "✅", 0: "⚠️"})
    st.dataframe(display, use_container_width=True, hide_index=True)

    # ── Audit summary ─────────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Period Audit</p>', unsafe_allow_html=True)
    audit = weekly_audit(logs, user["tdee"], user["weekly_target"], user.get("kcal_per_kg", 7700))
    a1, a2, a3 = st.columns(3)
    a1.metric("Total Consumed", f"{audit['total_in']:.0f} kcal")
    a2.metric("Total Burned", f"{audit['total_burned']:.0f} kcal")
    a3.metric("Net Deficit", f"{audit['deficit_achieved']:.0f} kcal")


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

def page_settings(user):
    st.markdown("# SETTINGS")

    st.markdown('<p class="section-title">Body Stats</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        height  = st.number_input("Height (cm)", 140.0, 220.0, float(user["height_cm"]))
        weight  = st.number_input("Current Weight (kg)", 40.0, 300.0, float(user["weight_kg"]))
        age     = st.number_input("Age", 16, 90, int(user["age"]))
        gender  = st.selectbox("Gender", ["Male", "Female"], index=0 if user["gender"] == "Male" else 1)
    with c2:
        activity = st.selectbox(
            "Activity Level", list(ACTIVITY_MULTIPLIERS.keys()),
            index=list(ACTIVITY_MULTIPLIERS.keys()).index(user["activity_level"])
            if user["activity_level"] in ACTIVITY_MULTIPLIERS else 2
        )
        target_wt  = st.number_input("Target Weight (kg)", 40.0, 300.0, float(user["target_weight"]))
        weekly_tgt = st.number_input("Weekly Loss Goal (kg)", 0.1, 1.5, float(user["weekly_target"]), step=0.05)
        kcal_per_kg= st.number_input("Kcal per kg of fat", 7000.0, 8000.0, float(user.get("kcal_per_kg", 7700)), step=50.0)

    # Live TDEE preview
    new_tdee = calculate_tdee(weight, height, int(age), gender, activity)
    st.info(f"📊 Recalculated TDEE: **{new_tdee:.0f} kcal/day**")

    if st.button("SAVE SETTINGS"):
        update_user_profile(
            user["id"],
            height_cm=height, weight_kg=weight, age=int(age),
            gender=gender, activity_level=activity, tdee=new_tdee,
            target_weight=target_wt, weekly_target=weekly_tgt,
            kcal_per_kg=kcal_per_kg
        )
        st.session_state["user"] = get_user_by_id(user["id"])
        st.success("✅ Profile updated!")
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if not is_logged_in():
        page_login()
        return

    user = current_user()
    # Always refresh user from DB to get latest stats
    user = get_user_by_id(user["id"])
    st.session_state["user"] = user

    page = render_sidebar(user)

    if page == "Dashboard":
        page_dashboard(user)
    elif page == "Daily Log":
        page_daily_log(user)
    elif page == "Weight Log":
        page_weight_log(user)
    elif page == "History":
        page_history(user)
    elif page == "Settings":
        page_settings(user)


if __name__ == "__main__":
    main()
