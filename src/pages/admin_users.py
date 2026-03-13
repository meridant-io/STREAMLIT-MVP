"""Admin page — user management (visible to admins only)."""

from __future__ import annotations

import os
import re

import bcrypt
import streamlit as st
import yaml
from yaml.loader import SafeLoader

# AUTH_CONFIG_PATH env var allows Fly.io deployment to read from /data/auth_config.yaml
# (the persistent volume).  Falls back to project root for local Docker dev.
_AUTH_CONFIG_PATH = os.getenv(
    "AUTH_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "auth_config.yaml"),
)


def _load_config() -> dict:
    with open(_AUTH_CONFIG_PATH) as f:
        return yaml.load(f, Loader=SafeLoader)


def _save_config(cfg: dict) -> None:
    with open(_AUTH_CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def render() -> None:
    st.title("User Administration")

    cfg = _load_config()
    users: dict = cfg.get("credentials", {}).get("usernames", {})
    admins: list = cfg.get("admins", [])

    # ── Current users ──────────────────────────────────────────────────────────
    st.subheader("Current users")
    if users:
        for username, info in list(users.items()):
            col_name, col_email, col_role, col_del = st.columns([2, 3, 1.5, 1])
            col_name.markdown(
                f"**{info.get('name', username)}**  \n"
                f"<span style='font-size:.8rem;color:#6B7280'>{username}</span>",
                unsafe_allow_html=True,
            )
            col_email.markdown(
                f"<span style='font-size:.85rem'>{info.get('email', '—')}</span>",
                unsafe_allow_html=True,
            )
            col_role.markdown(
                "🔑 Admin" if username in admins else "User",
                unsafe_allow_html=True,
            )
            # Prevent the only admin from deleting themselves
            is_last_admin = username in admins and sum(1 for u in admins if u in users) <= 1
            if is_last_admin:
                col_del.markdown("<span style='font-size:.75rem;color:#6B7280'>protected</span>", unsafe_allow_html=True)
            elif col_del.button("Remove", key=f"del_{username}", type="secondary"):
                st.session_state[f"confirm_del_{username}"] = True

            if st.session_state.get(f"confirm_del_{username}"):
                st.warning(
                    f"Remove **{info.get('name', username)}** (`{username}`)? This cannot be undone."
                )
                c1, c2 = st.columns(2)
                if c1.button("Yes, remove", key=f"confirm_yes_{username}", type="primary"):
                    del users[username]
                    if username in admins:
                        admins.remove(username)
                    cfg["credentials"]["usernames"] = users
                    cfg["admins"] = admins
                    _save_config(cfg)
                    st.success(f"User `{username}` removed.")
                    st.session_state.pop(f"confirm_del_{username}", None)
                    st.rerun()
                if c2.button("Cancel", key=f"confirm_no_{username}"):
                    st.session_state.pop(f"confirm_del_{username}", None)
                    st.rerun()
    else:
        st.info("No users configured.")

    st.divider()

    # ── Add new user ────────────────────────────────────────────────────────────
    st.subheader("Add user")
    with st.form("add_user_form", clear_on_submit=True):
        col_u, col_n = st.columns(2)
        new_username = col_u.text_input(
            "Username", placeholder="jsmith",
            help="Lowercase, letters/numbers/underscores only"
        )
        new_name = col_n.text_input("Display name", placeholder="Jane Smith")

        col_e, col_p = st.columns(2)
        new_email = col_e.text_input("Email", placeholder="jsmith@example.com")
        new_password = col_p.text_input("Temporary password", type="password")

        new_is_admin = st.checkbox("Grant admin access")
        submitted = st.form_submit_button("Add user", type="primary")

    if submitted:
        errors = []
        if not new_username:
            errors.append("Username is required.")
        elif not re.match(r"^[a-z0-9_]+$", new_username):
            errors.append("Username must be lowercase letters, numbers, or underscores.")
        elif new_username in users:
            errors.append(f"Username `{new_username}` already exists.")
        if not new_name:
            errors.append("Display name is required.")
        if not new_password or len(new_password) < 8:
            errors.append("Password must be at least 8 characters.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(12)).decode()
            users[new_username] = {
                "name": new_name,
                "email": new_email or "",
                "password": hashed,
            }
            if new_is_admin and new_username not in admins:
                admins.append(new_username)
            cfg["credentials"]["usernames"] = users
            cfg["admins"] = admins
            _save_config(cfg)
            st.success(
                f"User **{new_name}** (`{new_username}`) added. "
                "They can log in immediately — no restart required."
            )
            st.rerun()

    st.divider()

    # ── Change password ─────────────────────────────────────────────────────────
    st.subheader("Change password")
    with st.form("change_pw_form", clear_on_submit=True):
        target_user = st.selectbox("User", list(users.keys()))
        new_pw = st.text_input("New password", type="password")
        confirm_pw = st.text_input("Confirm password", type="password")
        pw_submitted = st.form_submit_button("Update password", type="primary")

    if pw_submitted:
        if not new_pw or len(new_pw) < 8:
            st.error("Password must be at least 8 characters.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match.")
        else:
            hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt(12)).decode()
            users[target_user]["password"] = hashed
            cfg["credentials"]["usernames"] = users
            _save_config(cfg)
            st.success(f"Password updated for `{target_user}`. Takes effect on next login.")
