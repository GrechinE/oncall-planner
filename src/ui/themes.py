"""
UI theme definitions for OnCall Planner.

Theme selected via: ?theme=philips  →  ONCALL_THEME env var  →  "default"
Default = zero injection, native Streamlit dark theme untouched.
"""

from __future__ import annotations
import os
import base64

# Philips shield logo as inline SVG (base64) — no external request needed
_PHILIPS_LOGO_SVG = base64.b64encode(b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60">
  <text x="4" y="44" font-family="Arial,sans-serif" font-size="42" font-weight="bold" fill="#FFFFFF">philips</text>
  <circle cx="172" cy="12" r="7" fill="#FFFFFF"/>
  <circle cx="188" cy="12" r="7" fill="#FFFFFF"/>
  <circle cx="180" cy="26" r="7" fill="#FFFFFF"/>
</svg>""").decode()

THEMES: dict[str, dict] = {
    "default": {"name": "Default (Dark)",  "emoji": "🌙"},
    "philips": {"name": "Philips Blue",    "emoji": "🔵"},
}


def detect_theme() -> str:
    import streamlit as st
    params = st.query_params
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
        return
    if theme_name == "philips":
        _inject_philips(st)


def _inject_philips(st) -> None:
    """
    Philips corporate light theme.
    Strategy:
      - Sidebar + header: dark blue (#003087) background, all text/icons forced WHITE
      - Main area: light grey (#F4F6F9) background, all text forced DARK (#1A1A1A)
      - We use universal * selectors scoped to sidebar/header to catch every
        Streamlit internal element regardless of version-specific class names.
    """
    logo_html = f'<img src="data:image/svg+xml;base64,{_PHILIPS_LOGO_SVG}" style="width:140px;margin-bottom:8px;display:block;">'

    css = """
    <style>

    /* ═══ MAIN BACKGROUND ═══════════════════════════════════════════════════ */
    .stApp { background-color: #F4F6F9 !important; }
    .main .block-container { background-color: #F4F6F9 !important; padding-top: 1.2rem; }

    /* ═══ MAIN AREA — ALL TEXT DARK ════════════════════════════════════════ */
    /* Nuclear selector: every element in main that isn't sidebar/header */
    .main *, .main *::before, .main *::after {
        color: #1A1A1A !important;
    }
    /* Headings in Philips blue */
    .main h1, .main h2, .main h3, .main h4 { color: #003087 !important; }
    .main h1 { color: #003087 !important; }

    /* ═══ SIDEBAR — ALL WHITE ON DARK BLUE ═════════════════════════════════ */
    [data-testid="stSidebar"] {
        background-color: #003087 !important;
    }
    /* Force EVERY element inside sidebar to white — catches all Streamlit internals */
    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] *::before,
    [data-testid="stSidebar"] *::after {
        color: #FFFFFF !important;
        border-color: rgba(255,255,255,0.25) !important;
    }
    /* Sidebar inputs / selects: white bg, dark text */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="input"] input,
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] [role="listbox"] {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #00A3E0 !important;
    }
    /* Sidebar buttons: white outline */
    [data-testid="stSidebar"] button {
        border: 1px solid rgba(255,255,255,0.6) !important;
        background-color: rgba(255,255,255,0.1) !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: rgba(255,255,255,0.2) !important;
    }
    /* Primary button in sidebar */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #00A3E0 !important;
        border: none !important;
        color: #FFFFFF !important;
    }
    /* File uploader in sidebar */
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {
        background-color: rgba(255,255,255,0.1) !important;
        border: 1px dashed rgba(255,255,255,0.5) !important;
        border-radius: 6px !important;
    }
    /* Expanders in sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 6px !important;
    }
    /* Number input +/- buttons in sidebar */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {
        background-color: rgba(255,255,255,0.15) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
    }

    /* ═══ TOP HEADER BAR ════════════════════════════════════════════════════ */
    header[data-testid="stHeader"] {
        background-color: #003087 !important;
        border-bottom: 3px solid #00A3E0 !important;
    }
    header[data-testid="stHeader"] * {
        color: #FFFFFF !important;
    }
    /* Toolbar buttons (deploy, share, etc.) */
    header[data-testid="stHeader"] button {
        color: #FFFFFF !important;
        background: transparent !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
    }

    /* ═══ MAIN AREA BUTTONS ═════════════════════════════════════════════════ */
    .main button[kind="primary"],
    .main .stButton > button[kind="primary"] {
        background-color: #0B5ED7 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .main button[kind="primary"]:hover {
        background-color: #0A4FB5 !important;
    }
    .main .stButton > button[kind="secondary"] {
        border: 2px solid #0B5ED7 !important;
        color: #0B5ED7 !important;
        background-color: #FFFFFF !important;
        border-radius: 6px !important;
    }
    .main .stDownloadButton > button {
        background-color: #FFFFFF !important;
        color: #0B5ED7 !important;
        border: 2px solid #0B5ED7 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .main .stDownloadButton > button:hover {
        background-color: #0B5ED7 !important;
        color: #FFFFFF !important;
    }

    /* ═══ TABS ══════════════════════════════════════════════════════════════ */
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

    /* ═══ ALERTS ════════════════════════════════════════════════════════════ */
    .stSuccess, [data-testid="stAlert"][kind="success"] {
        background-color: #F0FFF8 !important;
        border-left: 4px solid #00875A !important;
    }
    .stSuccess *, [data-testid="stAlert"][kind="success"] * { color: #1A5C3A !important; }

    .stInfo, [data-testid="stAlert"][kind="info"] {
        background-color: #EBF4FF !important;
        border-left: 4px solid #0B5ED7 !important;
    }
    .stInfo *, [data-testid="stAlert"][kind="info"] * { color: #1A3C6A !important; }

    .stWarning, [data-testid="stAlert"][kind="warning"] {
        background-color: #FFFBEB !important;
        border-left: 4px solid #D97706 !important;
    }
    .stWarning *, [data-testid="stAlert"][kind="warning"] * { color: #7C4A00 !important; }

    .stError, [data-testid="stAlert"][kind="error"] {
        background-color: #FFF0F0 !important;
        border-left: 4px solid #DC2626 !important;
    }
    .stError *, [data-testid="stAlert"][kind="error"] * { color: #7C1A1A !important; }

    /* ═══ EXPANDERS (MAIN) ══════════════════════════════════════════════════ */
    .main [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 8px !important;
    }

    /* ═══ INPUTS (MAIN) ═════════════════════════════════════════════════════ */
    .main input, .main textarea {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 6px !important;
    }
    .main [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #CBD5E0 !important;
    }

    /* ═══ DATAFRAME ════════════════════════════════════════════════════════ */
    [data-testid="stDataFrame"] { background-color: #FFFFFF !important; }

    /* ═══ CAPTIONS ══════════════════════════════════════════════════════════ */
    .main .stCaption, .main small { color: #718096 !important; }

    </style>
    """

    # Logo injected as HTML above the sidebar content
    logo_css = f"""
    <style>
    [data-testid="stSidebar"] > div:first-child {{
        padding-top: 0.5rem;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(logo_css, unsafe_allow_html=True)

    # Inject Philips logo at top of sidebar using st.sidebar
    import streamlit as _st
    with _st.sidebar:
        _st.markdown(
            f'<div style="padding:12px 8px 4px 8px;">'
            f'<img src="data:image/svg+xml;base64,{_PHILIPS_LOGO_SVG}" '
            f'style="width:130px;display:block;margin-bottom:4px;">'
            f'<div style="color:rgba(255,255,255,0.55);font-size:10px;letter-spacing:1px;'
            f'text-transform:uppercase;padding-left:2px;">OnCall Planner</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
