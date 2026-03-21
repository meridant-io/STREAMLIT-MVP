from __future__ import annotations

import logging
import os

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# Silence noisy library loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)

from src.pages import create_assessment, dashboard, admin_users, assessments

st.set_page_config(page_title="Meridant Matrix", layout="wide", initial_sidebar_state="collapsed")

# ── Brand CSS ─────────────────────────────────────────────────────────────────
_brand_css_path = os.path.join(os.path.dirname(__file__), "assets", "meridant_brand.css")
_brand_css = open(_brand_css_path).read() if os.path.exists(_brand_css_path) else ""
st.markdown(f"<style>{_brand_css}</style>", unsafe_allow_html=True)

# ── App CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  /* ── Buttons ── */
  .stButton > button,
  button[data-testid^="baseButton-"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: .775rem !important; font-weight: 400 !important;
    line-height: 1.5 !important; padding: .25rem .6rem !important;
    border-radius: .2rem !important; min-height: unset !important; height: auto !important;
  }
  /* ── Hide sidebar and its toggle entirely ── */
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }
  /* ── Hide native Streamlit header content ── */
  [data-testid="stHeader"] > * { display: none !important; }
  [data-testid="stHeader"] {
    height: 68px !important; position: fixed !important;
    top: 0 !important; left: 0 !important; width: 100vw !important;
    background: transparent !important; z-index: 1 !important;
  }
  /* ── Brand header bar ── */
  #meridant-brand {
    position: fixed; top: 0; left: 0; width: 100vw; height: 68px;
    background: #0F2744; border-bottom: 1px solid #1e3a5f;
    display: flex; align-items: center; padding: 0 1.25rem; gap: 1rem;
    z-index: 999999; font-family: 'Inter', -apple-system, sans-serif;
  }
  #meridant-brand .m-wordmark {
    font-size: 20px; font-weight: 300; letter-spacing: 0.08em; line-height: 1.15; color: #F9FAFB;
  }
  #meridant-brand .m-tagline {
    font-size: 8px; letter-spacing: 0.20em; text-transform: uppercase; color: #93C5FD; margin-top: 3px;
  }
  /* ── Header nav — desktop, right-aligned 5rem from user area ── */
  .m-nav {
    display: flex; align-items: center; gap: .15rem;
    margin-left: auto; margin-right: 2rem;
  }
  .m-nav-link {
    color: #93C5FD !important; text-decoration: none !important;
    font-size: .78rem; font-weight: 500; letter-spacing: .02em;
    padding: .3rem .7rem; border-radius: 6px;
    transition: background .15s, color .15s; white-space: nowrap;
  }
  .m-nav-link:hover { background: rgba(255,255,255,.1); color: #F9FAFB !important; }
  .m-nav-link.active { background: rgba(37,99,235,.35); color: #F9FAFB !important; font-weight: 600; }
  /* ── Header user area ── */
  .m-user-area {
    display: flex; align-items: center; gap: .6rem; white-space: nowrap;
  }
  .m-user-info { line-height: 1.25; text-align: right; }
  .m-user-label { font-size: .6rem; color: #93C5FD; }
  .m-user-name  { font-size: .72rem; font-weight: 600; color: #F9FAFB; }
  .m-signout {
    color: #93C5FD !important; text-decoration: none !important;
    font-size: .7rem; padding: .2rem .45rem; border-radius: 4px;
    border: 1px solid rgba(147,197,253,.3); transition: background .15s, color .15s;
    white-space: nowrap;
  }
  .m-signout:hover { background: rgba(255,255,255,.1); color: #F9FAFB !important; }
  /* ── Hamburger — hidden on desktop ── */
  .m-hamburger-wrap { display: none; }
  @media (max-width: 960px) {
    .m-nav { display: none !important; }
    .m-hamburger-wrap { display: flex; align-items: center; }
  }
  #m-menu-toggle { display: none; }
  .m-hamburger-label {
    cursor: pointer; display: flex; flex-direction: column; justify-content: center;
    gap: 4px; padding: 8px 10px; border-radius: 6px; transition: background .15s;
  }
  .m-hamburger-label:hover { background: rgba(255,255,255,.1); }
  .m-hamburger-label span {
    display: block; width: 18px; height: 2px; background: #F9FAFB;
    border-radius: 1px; transition: transform .2s, opacity .2s;
  }
  #m-menu-toggle:checked + .m-hamburger-label span:nth-child(1) { transform: translateY(6px) rotate(45deg); }
  #m-menu-toggle:checked + .m-hamburger-label span:nth-child(2) { opacity: 0; transform: scaleX(0); }
  #m-menu-toggle:checked + .m-hamburger-label span:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }
  /* ── Mobile nav dropdown ── */
  .m-nav-mobile {
    display: none; position: fixed; top: 68px; right: 0; width: 100%;
    background: #0F2744; border-bottom: 2px solid #1e3a5f;
    flex-direction: column; padding: .5rem .75rem;
    z-index: 999998; box-shadow: 0 6px 16px rgba(0,0,0,.35);
  }
  #m-menu-toggle:checked ~ .m-nav-mobile { display: flex; }
  .m-nav-mobile .m-nav-link { padding: .6rem .75rem; font-size: .85rem; display: block; }
  /* ── Main content container ── */
  .stMainBlockContainer { padding: 4.75rem .5rem .5rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Authentication ─────────────────────────────────────────────────────────────
_AUTH_CONFIG_PATH = os.getenv(
    "AUTH_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "auth_config.yaml"),
)

if not os.path.exists(_AUTH_CONFIG_PATH):
    st.error(
        f"**Auth config not found:** `{_AUTH_CONFIG_PATH}`\n\n"
        "Upload `auth_config.yaml` to the Fly.io volume:\n\n"
        "```\nfly machine start --app streamlit-mvp\n"
        "fly ssh sftp shell --app streamlit-mvp\n"
        "put auth_config.yaml /data/auth_config.yaml\n"
        "exit\nfly deploy\n```"
    )
    st.stop()

with open(_AUTH_CONFIG_PATH) as f:
    _auth_config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    _auth_config["credentials"],
    _auth_config["cookie"]["name"],
    _auth_config["cookie"]["key"],
    _auth_config["cookie"]["expiry_days"],
)

# ── Brand header (login page — no nav yet) ───────────────────────────────────
_LOGO = """<svg width="48" height="36" viewBox="0 0 40 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <polyline points="0,32 11,6 20,20" fill="none" stroke="#F9FAFB" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <polyline points="20,20 29,2 40,32" fill="none" stroke="#2563EB" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="4" y1="8" x2="36" y2="0" stroke="#2563EB" stroke-width="1" stroke-dasharray="2.5,2" stroke-linecap="round"/>
  <circle cx="11" cy="6" r="2" fill="none" stroke="#F9FAFB" stroke-width="1.6"/>
  <circle cx="29" cy="2" r="2" fill="#2563EB"/>
</svg>"""

st.markdown(f"""
<div id="meridant-brand">
  {_LOGO}
  <div>
    <div class="m-wordmark">meridant</div>
    <div class="m-tagline">Map the gap.&nbsp;&nbsp;Chart the path.</div>
  </div>
</div>
""", unsafe_allow_html=True)

authenticator.login()

if st.session_state.get("authentication_status") is False:
    st.error("Incorrect username or password.")
    st.stop()

if st.session_state.get("authentication_status") is None:
    st.stop()

# ── Authenticated ──────────────────────────────────────────────────────────────

# Handle logout action from header link
if st.query_params.get("_action") == "logout":
    authenticator.logout("_", "unrendered")
    st.query_params.clear()
    st.rerun()

# Build nav pages
_admins = _auth_config.get("admins", [])
_is_admin = st.session_state.get("username", "") in _admins
_nav_pages = ["Dashboard", "Assessments", "Create Assessment"]
if _is_admin:
    _nav_pages.append("Admin")

# Handle cross-page navigation from session state (e.g. Resume Assessment)
_nav_target = st.session_state.pop("_navigate_to", None)
if _nav_target and _nav_target in _nav_pages:
    st.query_params["page"] = _nav_target
    st.rerun()

# Current page from URL
_page = st.query_params.get("page", "Dashboard")
if _page not in _nav_pages:
    _page = "Dashboard"

# Build nav HTML
_nav_items = ""
for _p in _nav_pages:
    _active = " active" if _page == _p else ""
    _url = "?page=" + _p.replace(" ", "+")
    _nav_items += f'<a href="{_url}" target="_self" class="m-nav-link{_active}">{_p}</a>'

_display_name = st.session_state.get("name", st.session_state.get("username", ""))

# Full brand header with nav + responsive hamburger
st.markdown(f"""
<div id="meridant-brand">
  {_LOGO}
  <div>
    <div class="m-wordmark">meridant</div>
    <div class="m-tagline">Map the gap.&nbsp;&nbsp;Chart the path.</div>
  </div>
  <nav class="m-nav">{_nav_items}</nav>
  <div class="m-user-area">
    <div class="m-user-info">
      <div class="m-user-label">Signed in as</div>
      <div class="m-user-name">{_display_name}</div>
    </div>
    <a href="?_action=logout" target="_self" class="m-signout">Sign out</a>
  </div>
  <div class="m-hamburger-wrap">
    <input type="checkbox" id="m-menu-toggle">
    <label for="m-menu-toggle" class="m-hamburger-label">
      <span></span><span></span><span></span>
    </label>
    <div class="m-nav-mobile">{_nav_items}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Store authenticated username for attribution ───────────────────────────────
st.session_state.setdefault(
    "authenticated_username", st.session_state.get("username", "")
)

# ── Route to page ──────────────────────────────────────────────────────────────
if _page == "Dashboard":
    dashboard.render()
elif _page == "Assessments":
    assessments.render()
elif _page == "Create Assessment":
    create_assessment.render()
elif _page == "Admin":
    admin_users.render()
