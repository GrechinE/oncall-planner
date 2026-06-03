"""
UI theme definitions for OnCall Planner.

Theme is selected via:
  1. URL query param:   ?theme=philips
  2. Environment var:   ONCALL_THEME=philips
  3. Default:           no CSS injection — Streamlit's native dark theme

Adding a new theme: add an entry to THEMES and write its inject_ function.
"""

from __future__ import annotations
import os


THEMES: dict[str, dict] = {
    "default": {
        "name": "Default (Dark)",
        "emoji": "🌙",
    },
    "philips": {
        "name": "Philips Blue",
        "emoji": "🔵",
    },
}


def detect_theme() -> str:
    """Resolve theme from URL param → env var → default."""
    import streamlit as st
    params = st.query_params
    if hasattr(params, "get"):
        url_theme = params.get("theme", None)
        if isinstance(url_theme, list):
            url_theme = url_theme[0] if url_theme else None
        if url_theme and url_theme in THEMES:
            return url_theme
    env_theme = os.environ.get("ONCALL_THEME", "").lower().strip()
    if env_theme and env_theme in THEMES:
        return env_theme
    return "default"


def inject_theme(theme_name: str) -> None:
    import streamlit as st
    if theme_name == "default":
        # No injection — preserve Streamlit's native dark theme exactly as-is
        return
    if theme_name == "philips":
        _inject_philips(st)


def _inject_philips(st) -> None:
    """
    Philips corporate light theme.
    Philips brand: Shield Blue #0B5ED7, Dark Blue #003087, Light Blue #00A3E0.
    All text is explicitly set to dark (#1A1A1A / #2D3748) for contrast on white/grey.
    Sidebar uses dark blue background with white text.
    """
    css = """
    <style>
    /* ── Base app background ─────────────────────── */
    .stApp, .stApp > div {
        background-color: #F4F6F9 !important;
    }
    .main .block-container {
        background-color: #F4F6F9 !important;
    }

    /* ── ALL text → dark by default ─────────────── */
    .stApp, .stApp p, .stApp span, .stApp div,
    .stApp label, .stApp li, .stApp td, .stApp th,
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    .stMarkdown strong, .stMarkdown em,
    [data-testid="stText"], [data-testid="stMarkdownContainer"] p {
        color: #1A1A1A !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #003087 !important;
    }

    /* ── Sidebar: dark blue + white text ─────────── */
    [data-testid="stSidebar"] {
        background-color: #003087 !important;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #00A3E0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
    }

    /* ── Tabs ─────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #FFFFFF !important;
        border-bottom: 2px solid #0B5ED7 !important;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #4A5568 !important;
        background-color: transparent !important;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        color: #0B5ED7 !important;
        border-bottom: 3px solid #0B5ED7 !important;
        font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        background-color: #F4F6F9 !important;
        border: 1px solid #CBD5E0 !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px;
        padding: 1rem !important;
    }

    /* ── Buttons ──────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background-color: #0B5ED7 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #0A4FB5 !important;
    }
    .stButton > button[kind="secondary"] {
        border: 2px solid #0B5ED7 !important;
        color: #0B5ED7 !important;
        background-color: #FFFFFF !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #EBF4FF !important;
    }

    /* ── Download buttons ─────────────────────────── */
    .stDownloadButton > button {
        background-color: #FFFFFF !important;
        color: #0B5ED7 !important;
        border: 2px solid #0B5ED7 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stDownloadButton > button:hover {
        background-color: #0B5ED7 !important;
        color: #FFFFFF !important;
    }

    /* ── Inputs (main area) ───────────────────────── */
    .main input[type="text"],
    .main input[type="number"],
    .main textarea {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 6px !important;
    }
    .main input:focus,
    .main textarea:focus {
        border-color: #0B5ED7 !important;
        box-shadow: 0 0 0 2px rgba(11,94,215,0.15) !important;
    }

    /* ── Selectbox (main area) ────────────────────── */
    .main [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #CBD5E0 !important;
    }

    /* ── Expanders ────────────────────────────────── */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 6px !important;
    }
    .streamlit-expanderContent {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E0 !important;
        border-top: none !important;
        color: #1A1A1A !important;
    }

    /* ── Dataframe ────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid #CBD5E0 !important;
        border-radius: 8px !important;
        background-color: #FFFFFF !important;
    }
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] th {
        color: #1A1A1A !important;
        background-color: #FFFFFF !important;
    }

    /* ── Alerts ───────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: 6px !important;
    }
    .stSuccess {
        background-color: #F0FFF8 !important;
        border-left: 4px solid #00875A !important;
        color: #1A5C3A !important;
    }
    .stSuccess p, .stSuccess span { color: #1A5C3A !important; }

    .stInfo {
        background-color: #EBF4FF !important;
        border-left: 4px solid #0B5ED7 !important;
        color: #1A3C6A !important;
    }
    .stInfo p, .stInfo span { color: #1A3C6A !important; }

    .stWarning {
        background-color: #FFFBEB !important;
        border-left: 4px solid #D97706 !important;
        color: #7C4A00 !important;
    }
    .stWarning p, .stWarning span { color: #7C4A00 !important; }

    .stError {
        background-color: #FFF0F0 !important;
        border-left: 4px solid #DC2626 !important;
        color: #7C1A1A !important;
    }
    .stError p, .stError span { color: #7C1A1A !important; }

    /* ── Metric containers ────────────────────────── */
    [data-testid="metric-container"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
    }
    [data-testid="metric-container"] label,
    [data-testid="metric-container"] div {
        color: #2D3748 !important;
    }

    /* ── Caption / muted ──────────────────────────── */
    .stCaption, .stCaption p, small {
        color: #718096 !important;
    }

    /* ── Title accent ─────────────────────────────── */
    .stApp h1 {
        color: #003087 !important;
    }

    /* ── Top header bar ───────────────────────────── */
    header[data-testid="stHeader"] {
        background-color: #003087 !important;
        border-bottom: 3px solid #00A3E0 !important;
    }

    /* ── Toggle / checkbox ────────────────────────── */
    [data-testid="stCheckbox"] label,
    [data-baseweb="checkbox"] label {
        color: #1A1A1A !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
