"""
All business logic and formulas for the Accountability Tax Protocol.
"""

ACTIVITY_MULTIPLIERS = {
    "Sedentary (desk job, little exercise)":        1.2,
    "Lightly active (1–3 days/week)":               1.375,
    "Moderately active (3–5 days/week)":            1.55,
    "Very active (6–7 days/week)":                  1.725,
    "Extremely active (athlete / physical job)":    1.9,
}

DEBT_SPLIT_THRESHOLD = 800   # kcal — above this, we carry forward
DEFAULT_UNTRACKED_INTAKE = 2700
MIN_WORKOUT_KCAL = 200       # floor (~15-20 mins)
MAX_SINGLE_WORKOUT_KCAL = 800  # ceiling before debt split


# ── TDEE ──────────────────────────────────────────────────────────────────────
def mifflin_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Mifflin-St Jeor BMR."""
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    return base + 5 if gender.lower() == "male" else base - 161


def calculate_tdee(weight_kg: float, height_cm: float, age: int,
                   gender: str, activity_level: str) -> float:
    bmr = mifflin_bmr(weight_kg, height_cm, age, gender)
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    return round(bmr * multiplier, 1)


# ── CORE FORMULA ──────────────────────────────────────────────────────────────
def calculate_exercise_target(
    calories_in: float,
    tdee: float,
    weekly_target_kg: float,
    kcal_per_kg: float = 7700,
    tracked: bool = True,
) -> float:
    """
    ET = (Intake - TDEE) + (weekly_target_kg × kcal_per_kg / 7)

    If untracked, intake defaults to DEFAULT_UNTRACKED_INTAKE.
    Result is floored at MIN_WORKOUT_KCAL.
    """
    effective_intake = calories_in if tracked else DEFAULT_UNTRACKED_INTAKE
    over_intake_tax = max(0, effective_intake - tdee)
    loss_driver = (weekly_target_kg * kcal_per_kg) / 7
    raw_target = over_intake_tax + loss_driver
    return max(MIN_WORKOUT_KCAL, round(raw_target, 1))


# ── DEBT LOGIC ────────────────────────────────────────────────────────────────
def split_target_if_needed(exercise_target: float) -> tuple[float, float]:
    """
    If ET > DEBT_SPLIT_THRESHOLD, return (today_target, carry_forward_debt).
    Otherwise return (exercise_target, 0).
    """
    if exercise_target > DEBT_SPLIT_THRESHOLD:
        carry = round(exercise_target - DEBT_SPLIT_THRESHOLD, 1)
        return DEBT_SPLIT_THRESHOLD, carry
    return exercise_target, 0.0


def effective_target_with_debt(base_target: float, active_debt: float) -> float:
    """Add outstanding debt to today's target, then re-apply split cap."""
    total = base_target + active_debt
    today, new_debt = split_target_if_needed(total)
    return today, new_debt


# ── WEEKLY AUDIT ──────────────────────────────────────────────────────────────
def weekly_audit(logs: list[dict], tdee: float,
                 weekly_target_kg: float, kcal_per_kg: float = 7700) -> dict:
    """
    Given a list of daily_log dicts for a 7-day window, return a summary dict.
    """
    total_in = sum(r["calories_in"] or DEFAULT_UNTRACKED_INTAKE for r in logs)
    total_burned = sum((r["calories_burned"] or 0) for r in logs)
    total_tdee = tdee * 7
    weekly_goal_deficit = weekly_target_kg * kcal_per_kg

    net = total_in - total_tdee - total_burned
    deficit_achieved = -net  # positive = deficit
    on_track = deficit_achieved >= weekly_goal_deficit * 0.8  # 80% counts

    return {
        "total_in": round(total_in, 1),
        "total_burned": round(total_burned, 1),
        "total_tdee": round(total_tdee, 1),
        "net": round(net, 1),
        "deficit_achieved": round(deficit_achieved, 1),
        "weekly_goal_deficit": round(weekly_goal_deficit, 1),
        "on_track": on_track,
        "days_logged": len(logs),
    }


# ── WEIGHT HELPERS ────────────────────────────────────────────────────────────
def kg_to_goal(current_weight: float, target_weight: float) -> float:
    return round(current_weight - target_weight, 2)


def estimated_weeks_to_goal(current_weight: float, target_weight: float,
                             weekly_target_kg: float) -> float:
    gap = kg_to_goal(current_weight, target_weight)
    if gap <= 0 or weekly_target_kg <= 0:
        return 0
    return round(gap / weekly_target_kg, 1)


# ── BIKE CONVERSION ───────────────────────────────────────────────────────────
def kcal_to_minutes(kcal: float, kcal_per_minute: float = 12.7) -> int:
    """Rough conversion based on 140-150 BPM cycling rate."""
    return max(1, round(kcal / kcal_per_minute))
