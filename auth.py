import bcrypt
import streamlit as st
from database import get_user_by_email, create_user, init_db


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def login_user(email: str, password: str):
    """Returns user dict on success, None on failure."""
    user = get_user_by_email(email.lower().strip())
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def register_user(email, password, name, height_cm, weight_kg, age,
                  gender, activity_level, tdee, target_weight, weekly_target):
    """Returns (True, None) on success or (False, error_msg) on failure."""
    if get_user_by_email(email.lower().strip()):
        return False, "An account with that email already exists."
    try:
        create_user(
            email=email.lower().strip(),
            password_hash=hash_password(password),
            name=name,
            height_cm=height_cm,
            weight_kg=weight_kg,
            age=age,
            gender=gender,
            activity_level=activity_level,
            tdee=tdee,
            target_weight=target_weight,
            weekly_target=weekly_target,
        )
        return True, None
    except Exception as e:
        return False, str(e)


def set_session(user: dict):
    st.session_state["user"] = user
    st.session_state["user_id"] = user["id"]


def clear_session():
    for key in ["user", "user_id"]:
        st.session_state.pop(key, None)


def current_user():
    return st.session_state.get("user")


def is_logged_in():
    return "user" in st.session_state
