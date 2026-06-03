"""
UI theme definitions for OnCall Planner.

Theme is selected via:
  1. URL query param:   ?theme=philips
  2. Environment var:   ONCALL_THEME=philips
  3. Default:           default (dark navy + cyan)

Each theme is a dict of CSS variable values injected via st.markdown().
"""

from __future__ import annotations
import os

THEMES: dict[str, dict] = {
    "default": {
        "name": "Default (Dark)",
        "emoji": "🌙",
        # Core backgrounds
        "--bg-main":        "#0D1B2A",
        "--bg-sidebar":     "#0A1628",
        "--bg-card":        "#1B2B45",
        "--bg-input":       "#1B2B45",
        "--bg-header":      "#0A1628",
        # Text
        "--text-primary":   "#FFFFFF",
        "--text-secondary": "#B0C4DE",
        "--text-muted":     "#607080",
        # Accents
        "--accent":         "#00C2FF",
        "--accent-2":       "#7B2FFF",
        "--accent-hover":   "#33CFFF",
        # Status
        "--color-success":  "#00E596",
        "--color-warning":  "#FFD600",
        "--color-error":    "#FF4D4D",
        # Borders
        "--border":         "#1E3A5F",
        # Button primary
        "--btn-bg":         "#00C2FF",
        "--btn-text":       "#0D1B2A",
        "--btn-hover":      "#33CFFF",
    },

    "philips": {
        "name": "Philips Blue",
        "emoji": "🔵",
        # Core backgrounds
        "--bg-main":        "#F4F6F9",
        "--bg-sidebar":     "#003087",
        "--bg-card":        "#FFFFFF",
        "--bg-input":       "#FFFFFF",
        "--bg-header":      "#003087",
        # Text
        "--text-primary":   "#1A1A1A",
        "--text-secondary": "#4A5568",
        "--text-muted":     "#718096",
        # Accents
        "--accent":         "#0B5ED7",
        "--accent-2":       "#00A3E0",
        "--accent-hover":   "#0A4FB5",
        # Status
        "--color-success":  "#00875A",
        "--color-warning":  "#D97706",
        "--color-error":    "#DC2626",
        # Borders
        "--border":         "#CBD5E0",
        # Button primary
        "--btn-bg":         "#0B5ED7",
        "--btn-text":       "#FFFFFF",
        "--btn-hover":      "#0A4FB5",
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["default"])


def detect_theme() -> str:
    """Resolve theme from URL param → env var → default."""
    import streamlit as st
    # 1. URL query param: ?theme=philips
    params = st.query_params
    if hasattr(params, "get"):
        url_theme = params.get("theme", None)
        if isinstance(url_theme, list):
            url_theme = url_theme[0] if url_theme else None
        if url_theme and url_theme in THEMES:
            return url_theme
    # 2. Environment variable
    env_theme = os.environ.get("ONCALL_THEME", "").lower().strip()
    if env_theme and env_theme in THEMES:
        return env_theme
    return "default"


def inject_theme(theme_name: str) -> None:
    """Inject CSS variables + overrides into the Streamlit page."""
    import streamlit as st
    t = get_theme(theme_name)
    is_light = theme_name != "default"

    # Build CSS variable block
    vars_css = "\n".join(f"        {k}: {v};" for k, v in t.items() if k.startswith("--"))

    sidebar_text = "#FFFFFF" if theme_name == "philips" else t["--text-primary"]
    sidebar_text_muted = "#B0C8E8" if theme_name == "philips" else t["--text-secondary"]

    css = f"""
    <style>
    /* ── CSS Variables ─────────────────────────────── */
    :root {{
{vars_css}
    }}

    /* ── App background ────────────────────────────── */
    .stApp {{
        background-color: {t['--bg-main']} !important;
    }}

    /* ── Main content area ─────────────────────────── */
    .main .block-container {{
        background-color: {t['--bg-main']} !important;
        padding-top: 1.5rem;
    }}

    /* ── Sidebar ───────────────────────────────────── */
    [data-testid="stSidebar"] {{
        background-color: {t['--bg-sidebar']} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {sidebar_text} !important;
    }}
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label {{
        color: {sidebar_text_muted} !important;
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        color: {sidebar_text} !important;
    }}

    /* ── Typography ────────────────────────────────── */
    h1, h2, h3 {{
        color: {t['--text-primary']} !important;
    }}
    p, li, span, label {{
        color: {t['--text-secondary']} !important;
    }}
    .stMarkdown p {{
        color: {t['--text-secondary']} !important;
    }}

    /* ── Tabs ──────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {t['--bg-card']} !important;
        border-radius: 8px 8px 0 0;
        border-bottom: 2px solid {t['--accent']} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {t['--text-secondary']} !important;
        background-color: transparent !important;
        font-weight: 500;
    }}
    .stTabs [aria-selected="true"] {{
        color: {t['--accent']} !important;
        border-bottom: 2px solid {t['--accent']} !important;
        background-color: transparent !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background-color: {t['--bg-main']} !important;
        border: 1px solid {t['--border']} !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px;
        padding: 1rem !important;
    }}

    /* ── Buttons ───────────────────────────────────── */
    .stButton > button[kind="primary"] {{
        background-color: {t['--btn-bg']} !important;
        color: {t['--btn-text']} !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {t['--btn-hover']} !important;
    }}
    .stButton > button[kind="secondary"] {{
        border: 1px solid {t['--accent']} !important;
        color: {t['--accent']} !important;
        background-color: transparent !important;
        border-radius: 6px !important;
    }}

    /* ── Inputs ────────────────────────────────────── */
    .stTextInput input,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] {{
        background-color: {t['--bg-input']} !important;
        color: {t['--text-primary']} !important;
        border: 1px solid {t['--border']} !important;
        border-radius: 6px !important;
    }}

    /* ── Expanders ─────────────────────────────────── */
    .streamlit-expanderHeader {{
        background-color: {t['--bg-card']} !important;
        color: {t['--text-primary']} !important;
        border: 1px solid {t['--border']} !important;
        border-radius: 6px !important;
    }}
    .streamlit-expanderContent {{
        background-color: {t['--bg-card']} !important;
        border: 1px solid {t['--border']} !important;
        border-top: none !important;
    }}

    /* ── Dataframe ─────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        border: 1px solid {t['--border']} !important;
        border-radius: 8px !important;
    }}

    /* ── Metrics ───────────────────────────────────── */
    [data-testid="metric-container"] {{
        background-color: {t['--bg-card']} !important;
        border: 1px solid {t['--border']} !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
    }}

    /* ── Alerts ────────────────────────────────────── */
    .stSuccess {{
        background-color: {"#F0FFF8" if is_light else "#0A2A1E"} !important;
        border-left: 4px solid {t['--color-success']} !important;
        color: {"#1A5C3A" if is_light else "#00E596"} !important;
    }}
    .stInfo {{
        background-color: {"#EBF4FF" if is_light else "#0A1E35"} !important;
        border-left: 4px solid {t['--accent']} !important;
        color: {"#1A3C6A" if is_light else "#B0C4DE"} !important;
    }}
    .stWarning {{
        background-color: {"#FFFBEB" if is_light else "#2A2000"} !important;
        border-left: 4px solid {t['--color-warning']} !important;
        color: {"#7C4A00" if is_light else "#FFD600"} !important;
    }}
    .stError {{
        background-color: {"#FFF0F0" if is_light else "#2A0A0A"} !important;
        border-left: 4px solid {t['--color-error']} !important;
        color: {"#7C1A1A" if is_light else "#FF4D4D"} !important;
    }}

    /* ── Download buttons ──────────────────────────── */
    .stDownloadButton > button {{
        background-color: {t['--bg-card']} !important;
        color: {t['--accent']} !important;
        border: 1px solid {t['--accent']} !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}
    .stDownloadButton > button:hover {{
        background-color: {t['--accent']} !important;
        color: {t['--btn-text']} !important;
    }}

    /* ── Title ─────────────────────────────────────── */
    .stApp h1 {{
        color: {t['--accent']} !important;
    }}

    /* ── Caption / small text ──────────────────────── */
    .stCaption, small {{
        color: {t['--text-muted']} !important;
    }}

    /* ── Philips branding extras ───────────────────── */
    {"" if theme_name != "philips" else """
    /* Philips shield-blue top bar */
    header[data-testid="stHeader"] {
        background-color: #003087 !important;
        border-bottom: 3px solid #00A3E0 !important;
    }
    """}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
