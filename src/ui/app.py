"""
OnCall Planner — Streamlit UI (MVP validation prototype).

Run with:
    streamlit run src/ui/app.py
"""

from __future__ import annotations

import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Make sure src/ is importable when running from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st
from streamlit_local_storage import LocalStorage

from src.scheduler.exporter import (
    export_to_csv, export_to_excel, export_to_ical, build_schedule_dataframe,
)
from src.scheduler.fairness import compute_fairness
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.holidays import get_public_holidays_with_names
from src.scheduler.models import (
    Person,
    ScheduleConfig,
    ShiftStartDay,
    TeamConfig,
)
from src.scheduler.validator import validate
from src.ui.themes import THEMES, detect_theme, inject_theme


# ─────────────────────────────────────────────
# Cached helpers — only recompute when inputs change
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_holidays(country: str, year: int, _v: int = 3):
    return get_public_holidays_with_names(country.upper(), year)


@st.cache_data(show_spinner=False)
def _cached_schedule_df(
    result_json: str, people_json: str,
    mgr_result_json: str = "", mgr_people_json: str = "",
) -> pd.DataFrame:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    mgr_result = ScheduleResult.model_validate_json(mgr_result_json) if mgr_result_json else None
    mgr_team   = TeamConfig.model_validate_json(mgr_people_json) if mgr_people_json else None
    return build_schedule_dataframe(result, team, mgr_result, mgr_team)


@st.cache_data(show_spinner=False)
def _cached_fairness(result_json: str, people_json: str):
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    return compute_fairness(result, team)


@st.cache_data(show_spinner=False)
def _cached_export_excel(
    result_json: str, people_json: str,
    mgr_result_json: str = "", mgr_people_json: str = "",
) -> bytes:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    mgr_result = ScheduleResult.model_validate_json(mgr_result_json) if mgr_result_json else None
    mgr_team   = TeamConfig.model_validate_json(mgr_people_json) if mgr_people_json else None
    return export_to_excel(result, team, manager_result=mgr_result, manager_team=mgr_team)


@st.cache_data(show_spinner=False)
def _cached_export_csv(
    result_json: str, people_json: str,
    mgr_result_json: str = "", mgr_people_json: str = "",
) -> str:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    mgr_result = ScheduleResult.model_validate_json(mgr_result_json) if mgr_result_json else None
    mgr_team   = TeamConfig.model_validate_json(mgr_people_json) if mgr_people_json else None
    return export_to_csv(result, team, manager_result=mgr_result, manager_team=mgr_team)


@st.cache_data(show_spinner=False)
def _cached_export_ical(
    result_json: str, people_json: str,
    mgr_result_json: str = "", mgr_people_json: str = "",
) -> str:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    mgr_result = ScheduleResult.model_validate_json(mgr_result_json) if mgr_result_json else None
    mgr_team   = TeamConfig.model_validate_json(mgr_people_json) if mgr_people_json else None
    return export_to_ical(result, team, manager_result=mgr_result, manager_team=mgr_team)


def _schedule_is_stale() -> bool:
    """True if the team list has changed since the last Generate run."""
    if st.session_state.get("result") is None:
        return False
    snapshot = st.session_state.get("_gen_team_snapshot")
    if snapshot is None:
        return False
    current = json.dumps([p for p in st.session_state.people], sort_keys=True)
    return current != snapshot


def _next_monday() -> date:
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7  # weekday(): Mon=0, Sun=6
    days_ahead = days_ahead if days_ahead > 0 else 7
    return today + timedelta(days=days_ahead)


# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="OnCall Planner",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Theme — detect and inject before any other rendering
# ─────────────────────────────────────────────
if "_theme" not in st.session_state:
    st.session_state._theme = detect_theme()
inject_theme(st.session_state._theme)

st.title("📅 OnCall Planner")
st.caption("Fair, holiday-aware on-call scheduling for any global team — engineering, ops, support, and more.")

with st.expander("👋 How it works", expanded=not st.session_state.get("_ls_loaded", False)):
    st.markdown(
        """
        **Three steps to a complete on-call schedule:**

        1. **Team tab** — add your team members (or upload a CSV). Each person needs a name, country, and timezone.
        2. **Generate tab** — set your date range and click Generate. The engine assigns shifts fairly, avoiding national holidays automatically.
        3. **Export tab** — download as Excel, CSV, or iCal to import into Google Calendar / Outlook.

        **Tips:**
        - Leave *Regions* blank if your whole team shares one global rotation.
        - Use *Backup On-Call* toggle (sidebar) or the button in the Schedule tab to add a backup layer on demand.
        - The Fairness tab shows how evenly shifts are distributed across the team.
        - Your team is saved in your browser — no login needed, no data leaves your device.
        """
    )

# ─────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────
if "people" not in st.session_state:
    st.session_state.people = []
if "managers" not in st.session_state:
    st.session_state.managers = []
if "result" not in st.session_state:
    st.session_state.result = None
if "team" not in st.session_state:
    st.session_state.team = None
if "mgr_result" not in st.session_state:
    st.session_state.mgr_result = None
if "mgr_team" not in st.session_state:
    st.session_state.mgr_team = None
if "_ls_loaded" not in st.session_state:
    st.session_state._ls_loaded = False
if "edit_idx" not in st.session_state:
    st.session_state.edit_idx = None
if "edit_mgr_idx" not in st.session_state:
    st.session_state.edit_mgr_idx = None
if "_last_action_msg" not in st.session_state:
    st.session_state._last_action_msg = None
if "_gen_team_snapshot" not in st.session_state:
    st.session_state._gen_team_snapshot = None  # serialised team at last generate

# ─────────────────────────────────────────────
# Browser localStorage — persist team across sessions
# ─────────────────────────────────────────────
_ls = LocalStorage()

if not st.session_state._ls_loaded:
    _saved = _ls.getItem("oncall_people")
    if _saved and isinstance(_saved, list) and len(_saved) > 0:
        st.session_state.people = _saved
    _saved_mgr = _ls.getItem("oncall_managers")
    if _saved_mgr and isinstance(_saved_mgr, list) and len(_saved_mgr) > 0:
        st.session_state.managers = _saved_mgr
    st.session_state._ls_loaded = True
    _n_eng = len(st.session_state.people)
    _n_mgr = len(st.session_state.managers)
    if _n_eng > 0 or _n_mgr > 0:
        _restore_parts = []
        if _n_eng:
            _restore_parts.append(f"{_n_eng} engineer{'s' if _n_eng != 1 else ''}")
        if _n_mgr:
            _restore_parts.append(f"{_n_mgr} manager{'s' if _n_mgr != 1 else ''}")
        st.info(f"Team restored from your last session: {', '.join(_restore_parts)}.")

# ─────────────────────────────────────────────
# Sidebar — Schedule configuration
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Schedule Settings")

    _default_start = _next_monday()
    _default_end = date(_default_start.year, 12, 31)
    # Snap end to last Sunday/Saturday of year based on shift start day preference
    start_date = st.date_input("Start Date", value=_default_start,
                               help="First day of the first on-call week. Defaults to next Monday.")
    end_date = st.date_input("End Date", value=_default_end,
                             help="Shifts are generated up to (and including) this date.")

    with st.expander("Engineer settings", expanded=False):
        shift_duration = st.number_input("Shift Duration (days)", min_value=1, max_value=28, value=7,
                                         help="How many days each on-call shift lasts. Default: 7 (weekly).")
        shift_start = st.selectbox("Shift Start Day", ["sunday", "monday"],
                                   help="Which day of the week a new shift begins.")
        min_gap = st.number_input("Min Gap Between Shifts (weeks)", min_value=1, max_value=12, value=4,
                                  help="Minimum number of weeks between two primary shifts for the same person.")

        regions_input = st.text_input(
            "Regions (comma-separated)",
            value="",
            help="Leave blank for a single global pool. Use e.g. 'americas, emea, apac' only if different people cover different geographies.",
        )
        required_regions = [r.strip() for r in regions_input.split(",") if r.strip()]

        generate_backup = st.toggle(
            "Generate backup on-call",
            value=False,
            help="Off = primary-only. Add backup on demand from the Schedule tab.",
        )

    with st.expander("Manager settings", expanded=False):
        mgr_min_gap = st.number_input(
            "Manager Min Gap (weeks)", min_value=1, max_value=12, value=4,
            help="Minimum weeks between two duty-manager shifts for the same manager.",
        )
        mgr_shift_start = st.selectbox(
            "Manager Shift Start Day", ["sunday", "monday"],
            key="mgr_shift_start",
            help="Which day the manager duty week starts.",
        )

    st.markdown("---")
    st.header("📥 Load Sample Team")
    if st.button("Load sample dataset"):
        sample_path = Path(__file__).parent.parent.parent / "data" / "samples" / "demo_team.json"
        if sample_path.exists():
            import json as _json
            data = _json.loads(sample_path.read_text())
            people_data = data.get("people", [])
            mgr_data = data.get("managers", [])
            st.session_state.people = people_data
            st.session_state.managers = mgr_data
            _ls.setItem("oncall_people", people_data)
            _ls.setItem("oncall_managers", mgr_data)
            st.success(
                f"Loaded {len(people_data)} engineers across 3 regions + {len(mgr_data)} managers. "
                f"Go to the Generate tab to build the schedule."
            )
        else:
            st.error("Sample file not found.")

    st.markdown("---")
    st.header("📤 Upload Team JSON")
    uploaded = st.file_uploader("Upload team_config.json", type=["json"])
    if uploaded:
        data = json.loads(uploaded.read())
        if "people" in data:
            st.session_state.people = data["people"]
            _ls.setItem("oncall_people", data["people"])
            st.success(f"Loaded {len(st.session_state.people)} people.")

    st.markdown("---")
    st.header("🎨 Theme")
    _theme_options = {k: f"{v['emoji']} {v['name']}" for k, v in THEMES.items()}
    _current_idx = list(_theme_options.keys()).index(st.session_state._theme)
    _selected_theme = st.selectbox(
        "Colour theme",
        options=list(_theme_options.keys()),
        format_func=lambda k: _theme_options[k],
        index=_current_idx,
        key="theme_selector",
        label_visibility="collapsed",
    )
    if _selected_theme != st.session_state._theme:
        st.session_state._theme = _selected_theme
        st.rerun()

# ─────────────────────────────────────────────
# Tab layout
# ─────────────────────────────────────────────
tab_team, tab_managers, tab_holidays, tab_generate, tab_schedule, tab_fairness, tab_violations, tab_export = st.tabs([
    "👥 Engineers", "🧑‍💼 Managers", "🗓 Holidays", "⚡ Generate", "📋 Schedule", "⚖️ Fairness", "⚠️ Violations", "📤 Export"
])

# ─────────────────────────────────────────────
# TAB: Team
# ─────────────────────────────────────────────
with tab_team:
    st.subheader("Team Members")

    # Show flash message from previous action (survives rerun)
    if st.session_state._last_action_msg:
        _msg_type, _msg_text = st.session_state._last_action_msg
        if _msg_type == "success":
            st.success(_msg_text)
        elif _msg_type == "warning":
            st.warning(_msg_text)
        st.session_state._last_action_msg = None

    col_add, col_csv = st.columns([1, 1])

    with col_add:
        # Determine if we're editing an existing person
        _editing = st.session_state.edit_idx is not None
        _edit_person = st.session_state.people[st.session_state.edit_idx] if _editing else {}

        with st.expander(
            f"✏️ Edit: {_edit_person.get('name', '')}" if _editing else "➕ Add Person",
            expanded=_editing or len(st.session_state.people) == 0
        ):
            p_name = st.text_input("Full Name", value=_edit_person.get("name", ""), key="new_name")
            p_country = st.text_input("Country (ISO code, e.g. US, IL, IN)", value=_edit_person.get("country", ""),
                                      key="new_country", max_chars=3)
            p_tz = st.text_input("Timezone (IANA, e.g. America/New_York)", value=_edit_person.get("timezone", ""),
                                 key="new_tz")

            region_options = required_regions if required_regions else []
            _existing_regions = _edit_person.get("regions", [])
            p_regions_selected = st.multiselect(
                "Regions",
                options=region_options,
                default=[r for r in _existing_regions if r in region_options],
                help="Select all regions this person can cover.",
                key="new_regions_multi",
            )
            _extra_defaults = ", ".join(r for r in _existing_regions if r not in region_options)
            p_regions_extra = st.text_input(
                "Additional regions not listed above (comma-separated)",
                value=_extra_defaults,
                key="new_regions_extra",
                help="Leave blank if all regions are already selected above.",
            )

            p_skills = st.text_input("Skills (comma-separated)",
                                     value=", ".join(_edit_person.get("skills", [])), key="new_skills")
            p_blackouts = st.text_input("Blackout Dates (YYYY-MM-DD, comma-separated)",
                                        value=", ".join(_edit_person.get("blackout_dates", [])), key="new_blackouts")
            _max_default = _edit_person.get("max_shifts_per_year") or 12
            p_max = st.number_input("Max Shifts/Year (0 = unlimited)", min_value=0, value=int(_max_default),
                                    key="new_max")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                _btn_label = "💾 Save Changes" if _editing else "Add Person"
                if st.button(_btn_label, type="primary"):
                    _country_clean = p_country.strip().upper()
                    _country_valid = len(_country_clean) == 2 and _country_clean.isalpha()
                    if not p_name or not p_country or not p_tz:
                        st.error("Name, Country and Timezone are required.")
                    elif not _country_valid:
                        st.error("Country must be a 2-letter ISO code, e.g. US, GB, IN, IL.")
                    else:
                        import re as _re
                        base_id = _re.sub(r"[^a-z0-9]+", "-", p_name.strip().lower()).strip("-")
                        existing_ids = {p["id"] for i, p in enumerate(st.session_state.people)
                                        if not _editing or i != st.session_state.edit_idx}
                        new_id = base_id
                        counter = 2
                        while new_id in existing_ids:
                            new_id = f"{base_id}-{counter}"
                            counter += 1

                        extra_regions = [r.strip() for r in p_regions_extra.split(",") if r.strip()]
                        all_regions = list(dict.fromkeys(p_regions_selected + extra_regions))

                        person_data = {
                            "id": _edit_person.get("id", new_id) if _editing else new_id,
                            "name": p_name,
                            "country": p_country.upper(),
                            "timezone": p_tz,
                            "regions": all_regions,
                            "skills": [s.strip() for s in p_skills.split(",") if s.strip()],
                            "blackout_dates": [b.strip() for b in p_blackouts.split(",") if b.strip()],
                            "max_shifts_per_year": int(p_max) if p_max > 0 else None,
                        }

                        if _editing:
                            st.session_state.people[st.session_state.edit_idx] = person_data
                            st.session_state.edit_idx = None
                            st.session_state._last_action_msg = ("success", f"Updated {p_name}.")
                        else:
                            st.session_state.people.append(person_data)
                            st.session_state._last_action_msg = ("success", f"Added {p_name} (ID: {new_id}).")

                        _ls.setItem("oncall_people", st.session_state.people)
                        st.rerun()

            with btn_col2:
                if _editing and st.button("Cancel", type="secondary"):
                    st.session_state.edit_idx = None
                    st.rerun()

    with col_csv:
        csv_upload = st.file_uploader("Upload people.csv", type=["csv"], key="people_csv")
        if csv_upload is not None:
            try:
                _df_prev = pd.read_csv(csv_upload, dtype=str).fillna("")
                # Caption + button immediately after uploader — no table between them
                st.caption(f"{len(_df_prev)} rows · **{csv_upload.name}**")
                if st.button(f"✅ Import {len(_df_prev)} people", type="primary", key="btn_import_csv"):
                    added = 0
                    skipped = []
                    existing_ids = {p["id"] for p in st.session_state.people}
                    for _, row in _df_prev.iterrows():
                        pid = str(row.get("id", "")).strip()
                        name = str(row.get("name", "")).strip()
                        if not pid or not name:
                            skipped.append(f"Row missing id/name: {dict(row)}")
                            continue
                        if pid in existing_ids:
                            skipped.append(f"Duplicate ID '{pid}' ({name}) — skipped")
                            continue
                        regions_l = [r.strip() for r in str(row.get("regions", "")).split(",") if r.strip()]
                        skills_l = [s.strip() for s in str(row.get("skills", "")).split(",") if s.strip()]
                        blackouts_l = [b.strip() for b in str(row.get("blackout_dates", "")).split(",") if b.strip()]
                        max_raw = str(row.get("max_shifts_per_year", "")).strip()
                        st.session_state.people.append({
                            "id": pid,
                            "name": name,
                            "country": str(row.get("country", "")).strip().upper(),
                            "timezone": str(row.get("timezone", "")).strip(),
                            "regions": regions_l,
                            "skills": skills_l,
                            "blackout_dates": blackouts_l,
                            "max_shifts_per_year": int(max_raw) if max_raw.isdigit() else None,
                        })
                        existing_ids.add(pid)
                        added += 1
                    st.session_state._last_action_msg = ("success", f"Imported {added} people from {csv_upload.name}.")
                    for msg in skipped:
                        st.warning(msg)
                    _ls.setItem("oncall_people", st.session_state.people)
                    st.rerun()
                # Preview in a collapsed expander — doesn't push button out of view
                with st.expander("Preview data"):
                    _preview_cols = [c for c in ["id", "name", "country", "regions"] if c in _df_prev.columns]
                    st.dataframe(_df_prev[_preview_cols].head(10), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Failed to read CSV: {exc}")

    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if st.session_state.people:
        st.markdown(f"**{len(st.session_state.people)} team members**")
        for i, p in enumerate(st.session_state.people):
            col_data, col_edit, col_del = st.columns([11, 1, 1])
            with col_data:
                st.write(
                    f"**{p['name']}** ({p['id']}) — {p['country']} · {p['timezone']} · "
                    f"regions: {', '.join(p.get('regions', [])) or '—'} · "
                    f"max shifts: {p.get('max_shifts_per_year') or '∞'}"
                )
            with col_edit:
                if st.button("✏️", key=f"edit_{i}", help=f"Edit {p['name']}"):
                    st.session_state.edit_idx = i
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"del_{i}", help=f"Remove {p['name']}"):
                    st.session_state.people.pop(i)
                    if st.session_state.edit_idx is not None:
                        if st.session_state.edit_idx == i:
                            st.session_state.edit_idx = None
                        elif st.session_state.edit_idx > i:
                            st.session_state.edit_idx -= 1
                    _ls.setItem("oncall_people", st.session_state.people)
                    st.rerun()

        st.markdown("---")

        if not st.session_state.confirm_clear:
            if st.button("🗑 Clear All People", type="secondary"):
                st.session_state.confirm_clear = True
                st.rerun()
        else:
            st.warning("This will remove all team members. Are you sure?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, clear all", type="primary"):
                    st.session_state.people = []
                    st.session_state.confirm_clear = False
                    st.session_state.edit_idx = None
                    _ls.setItem("oncall_people", [])
                    st.rerun()
            with col_no:
                if st.button("Cancel"):
                    st.session_state.confirm_clear = False
                    st.rerun()
    else:
        st.session_state.confirm_clear = False
        st.info("No team members yet. Add people above or load the sample dataset from the sidebar.")

# ─────────────────────────────────────────────
# TAB: Managers
# ─────────────────────────────────────────────
with tab_managers:
    st.subheader("Duty Managers")
    st.caption("Managers rotate independently from engineers. Add your manager pool here.")

    _editing_mgr = st.session_state.edit_mgr_idx is not None
    _edit_mgr = st.session_state.managers[st.session_state.edit_mgr_idx] if _editing_mgr else {}

    with st.expander(
        f"✏️ Edit: {_edit_mgr.get('name', '')}" if _editing_mgr else "➕ Add Manager",
        expanded=_editing_mgr or len(st.session_state.managers) == 0,
    ):
        m_name = st.text_input("Full Name", value=_edit_mgr.get("name", ""), key="new_mgr_name")
        m_country = st.text_input("Country (ISO code)", value=_edit_mgr.get("country", ""),
                                  key="new_mgr_country", max_chars=3)
        m_tz = st.text_input("Timezone (IANA)", value=_edit_mgr.get("timezone", ""), key="new_mgr_tz")
        m_blackouts = st.text_input("Blackout Dates (YYYY-MM-DD, comma-separated)",
                                    value=", ".join(_edit_mgr.get("blackout_dates", [])), key="new_mgr_blackouts")
        _mgr_max_default = _edit_mgr.get("max_shifts_per_year") or 12
        m_max = st.number_input("Max Duty Weeks/Year (0 = unlimited)", min_value=0,
                                value=int(_mgr_max_default), key="new_mgr_max")

        mbtn1, mbtn2 = st.columns(2)
        with mbtn1:
            _mlabel = "💾 Save Changes" if _editing_mgr else "Add Manager"
            if st.button(_mlabel, type="primary", key="btn_add_mgr"):
                if not m_name or not m_country or not m_tz:
                    st.error("Name, Country and Timezone are required.")
                else:
                    import re as _re
                    base_id = _re.sub(r"[^a-z0-9]+", "-", m_name.strip().lower()).strip("-")
                    existing_ids = {p["id"] for i, p in enumerate(st.session_state.managers)
                                    if not _editing_mgr or i != st.session_state.edit_mgr_idx}
                    new_id = base_id
                    counter = 2
                    while new_id in existing_ids:
                        new_id = f"{base_id}-{counter}"
                        counter += 1

                    mgr_data = {
                        "id": _edit_mgr.get("id", new_id) if _editing_mgr else new_id,
                        "name": m_name,
                        "country": m_country.upper(),
                        "timezone": m_tz,
                        "regions": [],
                        "skills": [],
                        "blackout_dates": [b.strip() for b in m_blackouts.split(",") if b.strip()],
                        "max_shifts_per_year": int(m_max) if m_max > 0 else None,
                    }
                    if _editing_mgr:
                        st.session_state.managers[st.session_state.edit_mgr_idx] = mgr_data
                        st.session_state.edit_mgr_idx = None
                        st.session_state._last_action_msg = ("success", f"Updated {m_name}.")
                    else:
                        st.session_state.managers.append(mgr_data)
                        st.session_state._last_action_msg = ("success", f"Added manager {m_name}.")
                    _ls.setItem("oncall_managers", st.session_state.managers)
                    st.rerun()
        with mbtn2:
            if _editing_mgr and st.button("Cancel", type="secondary", key="btn_cancel_mgr"):
                st.session_state.edit_mgr_idx = None
                st.rerun()

    # CSV upload for managers
    mgr_csv = st.file_uploader("Upload managers.csv", type=["csv"], key="mgr_csv")
    if mgr_csv is not None:
        try:
            df_mgr = pd.read_csv(mgr_csv, dtype=str).fillna("")
            st.caption(f"{len(df_mgr)} rows found in **{mgr_csv.name}**")
            st.dataframe(df_mgr[["id", "name", "country"]].head(10), use_container_width=True)
            if st.button(f"✅ Import {len(df_mgr)} managers", type="primary", key="btn_import_mgr_csv"):
                added = 0
                skipped = []
                existing_ids = {p["id"] for p in st.session_state.managers}
                for _, row in df_mgr.iterrows():
                    pid = str(row.get("id", "")).strip()
                    name = str(row.get("name", "")).strip()
                    if not pid or not name:
                        skipped.append(f"Row missing id/name — skipped")
                        continue
                    if pid in existing_ids:
                        skipped.append(f"Duplicate ID '{pid}' ({name}) — skipped")
                        continue
                    blackouts_l = [b.strip() for b in str(row.get("blackout_dates", "")).split(",") if b.strip()]
                    max_raw = str(row.get("max_shifts_per_year", "")).strip()
                    st.session_state.managers.append({
                        "id": pid,
                        "name": name,
                        "country": str(row.get("country", "")).strip().upper(),
                        "timezone": str(row.get("timezone", "")).strip(),
                        "regions": [],
                        "skills": [],
                        "blackout_dates": blackouts_l,
                        "max_shifts_per_year": int(max_raw) if max_raw.isdigit() else None,
                    })
                    existing_ids.add(pid)
                    added += 1
                st.success(f"Imported {added} managers.")
                for msg in skipped:
                    st.warning(msg)
                _ls.setItem("oncall_managers", st.session_state.managers)
                st.rerun()
        except Exception as exc:
            st.error(f"Failed to read CSV: {exc}")

    if st.session_state.managers:
        st.markdown(f"**{len(st.session_state.managers)} managers**")
        for i, m in enumerate(st.session_state.managers):
            col_data, col_edit, col_del = st.columns([11, 1, 1])
            with col_data:
                st.write(
                    f"**{m['name']}** ({m['id']}) — {m['country']} · {m['timezone']} · "
                    f"max duty weeks: {m.get('max_shifts_per_year') or '∞'}"
                )
            with col_edit:
                if st.button("✏️", key=f"edit_mgr_{i}", help=f"Edit {m['name']}"):
                    st.session_state.edit_mgr_idx = i
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"del_mgr_{i}", help=f"Remove {m['name']}"):
                    st.session_state.managers.pop(i)
                    if st.session_state.edit_mgr_idx is not None:
                        if st.session_state.edit_mgr_idx == i:
                            st.session_state.edit_mgr_idx = None
                        elif st.session_state.edit_mgr_idx > i:
                            st.session_state.edit_mgr_idx -= 1
                    _ls.setItem("oncall_managers", st.session_state.managers)
                    st.rerun()

        if "confirm_clear_mgrs" not in st.session_state:
            st.session_state.confirm_clear_mgrs = False

        if not st.session_state.confirm_clear_mgrs:
            if st.button("🗑 Clear All Managers", type="secondary", key="btn_clear_mgrs"):
                st.session_state.confirm_clear_mgrs = True
                st.rerun()
        else:
            st.warning("This will remove all managers. Are you sure?")
            _mc_yes, _mc_no = st.columns(2)
            with _mc_yes:
                if st.button("Yes, clear all", type="primary", key="btn_clear_mgrs_yes"):
                    st.session_state.managers = []
                    st.session_state.edit_mgr_idx = None
                    st.session_state.confirm_clear_mgrs = False
                    _ls.setItem("oncall_managers", [])
                    st.rerun()
            with _mc_no:
                if st.button("Cancel", key="btn_clear_mgrs_no"):
                    st.session_state.confirm_clear_mgrs = False
                    st.rerun()
    else:
        st.session_state.confirm_clear_mgrs = False if "confirm_clear_mgrs" in st.session_state else None
        st.info("No managers yet. Add managers above or upload a CSV.")


# ─────────────────────────────────────────────
# TAB: Holidays Preview
# ─────────────────────────────────────────────
with tab_holidays:
    st.subheader("Public Holiday Preview")
    st.caption("Preview national holidays for any country and year.")

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        h_country = st.text_input("Country code", value="US", max_chars=3)
    with col_h2:
        h_year = st.number_input("Year", value=start_date.year, min_value=2020, max_value=2035)

    if st.button("Fetch Holidays"):
        country_upper = h_country.strip().upper()
        with st.spinner(f"Fetching holidays for {country_upper} {int(h_year)}..."):
            from datetime import timedelta as _td
            hdays = get_public_holidays_with_names(country_upper, int(h_year))
            # Apply holiday eves inline — countries where the eve is also non-working.
            # Done here so it works even if the holidays module is cached at an old version.
            _EVE_COUNTRIES = {"IL"}
            if hdays is not None and country_upper in _EVE_COUNTRIES:
                _eves = {}
                for _d, _name in hdays.items():
                    _eve = _d - _td(days=1)
                    if _eve not in hdays and _eve not in _eves:
                        _eves[_eve] = f"{_name} (Eve)"
                hdays = {**hdays, **_eves}

            if hdays:
                rows = sorted(hdays.items())
                df_h = pd.DataFrame(rows, columns=["Date", "Holiday Name"])
                df_h["Day"] = df_h["Date"].apply(lambda d: d.strftime("%A"))
                df_h = df_h[["Date", "Day", "Holiday Name"]]
                st.success(f"{len(hdays)} non-working days for {country_upper} {int(h_year)}.")
                st.dataframe(df_h, use_container_width=True)
            else:
                st.warning(
                    f"No holiday data found for **{country_upper}** {int(h_year)}. "
                    f"Check the country code is a valid ISO 3166-1 alpha-2 code (e.g. IL, GB, US, DE)."
                )

    if st.session_state.people:
        st.markdown("---")
        st.subheader("Team Holiday Summary")
        countries = list({p["country"] for p in st.session_state.people})
        year = start_date.year
        from datetime import timedelta as _td2
        _EVE_COUNTRIES2 = {"IL"}
        for c in sorted(countries):
            hnamed = _cached_holidays(c.upper(), year)
            if hnamed is not None and c.upper() in _EVE_COUNTRIES2:
                _eves2 = {}
                for _d2, _n2 in hnamed.items():
                    _eve2 = _d2 - _td2(days=1)
                    if _eve2 not in hnamed and _eve2 not in _eves2:
                        _eves2[_eve2] = f"{_n2} (Eve)"
                hnamed = {**hnamed, **_eves2}
            count = len(hnamed) if hnamed else 0
            with st.expander(f"**{c}** — {count} non-working days in {year}"):
                if hnamed:
                    rows = sorted(hnamed.items())
                    df_c = pd.DataFrame(rows, columns=["Date", "Holiday Name"])
                    df_c["Day"] = df_c["Date"].apply(lambda d: d.strftime("%A"))
                    df_c = df_c[["Date", "Day", "Holiday Name"]]
                    st.dataframe(df_c, use_container_width=True, hide_index=True)
                else:
                    st.write("No holiday data available.")

# ─────────────────────────────────────────────
# TAB: Generate
# ─────────────────────────────────────────────
with tab_generate:
    st.subheader("Generate Schedule")

    if not st.session_state.people:
        st.warning("Add team members first (Team tab or load sample from sidebar).")
    elif start_date >= end_date:
        st.error("End date must be after start date.")
    else:
        total_weeks = ((end_date - start_date).days // 7) + 1
        st.write(f"**Team size:** {len(st.session_state.people)} people")
        st.write(f"**Period:** {start_date} → {end_date} (~{total_weeks} weeks)")
        st.write(f"**Regions:** {', '.join(required_regions) if required_regions else 'global (single pool)'}")
        st.write(f"**Shift:** {shift_duration} days, starting {shift_start}, min gap {min_gap} weeks")

        if st.session_state.managers:
            st.write(f"**Managers:** {len(st.session_state.managers)} people in duty rotation")
        else:
            st.info("No managers added yet — only engineer schedule will be generated. Add managers in the Managers tab.")

        if st.button("⚡ Generate Schedule", type="primary"):
            try:
                config = ScheduleConfig(
                    start_date=start_date,
                    end_date=end_date,
                    shift_duration_days=shift_duration,
                    shift_start_day=ShiftStartDay(shift_start),
                    min_gap_between_shifts_weeks=min_gap,
                    required_regions=required_regions,
                    generate_backup=generate_backup,
                )
                people = [Person.model_validate(p) for p in st.session_state.people]
                team = TeamConfig(schedule=config, people=people)

                with st.spinner("Generating engineer schedule..."):
                    generator = ScheduleGenerator(team)
                    result = generator.generate()
                    result.violations = validate(result, team)

                st.session_state.result = result
                st.session_state.team = team
                st.session_state._gen_team_snapshot = json.dumps(
                    [p for p in st.session_state.people], sort_keys=True
                )

                # Generate manager rotation if managers are configured
                if st.session_state.managers:
                    with st.spinner("Generating manager rotation..."):
                        mgr_config = ScheduleConfig(
                            start_date=start_date,
                            end_date=end_date,
                            shift_duration_days=shift_duration,
                            shift_start_day=ShiftStartDay(mgr_shift_start),
                            min_gap_between_shifts_weeks=mgr_min_gap,
                            required_regions=[],
                            generate_backup=False,
                        )
                        managers = [Person.model_validate(m) for m in st.session_state.managers]
                        mgr_team = TeamConfig(schedule=mgr_config, people=managers)
                        mgr_result = ScheduleGenerator(mgr_team).generate()
                        mgr_result.violations = validate(mgr_result, mgr_team)
                    st.session_state.mgr_result = mgr_result
                    st.session_state.mgr_team = mgr_team
                else:
                    st.session_state.mgr_result = None
                    st.session_state.mgr_team = None

                errors = sum(1 for v in result.violations if v.severity == "error")
                warnings = sum(1 for v in result.violations if v.severity == "warning")
                n_weeks = len(result.schedule.assignments)

                if errors == 0:
                    msg = (f"Schedule generated: {n_weeks} weeks ({start_date} → {end_date}), "
                           f"0 errors, {warnings} warnings.")
                    if st.session_state.mgr_result:
                        mgr_errors = sum(1 for v in st.session_state.mgr_result.violations if v.severity == "error")
                        msg += f" Manager rotation: {mgr_errors} errors."
                    st.success(msg + " Head to the Schedule tab to review.")
                else:
                    st.error(
                        f"Schedule generated with {errors} errors and {warnings} warnings. "
                        f"Review the Violations tab."
                    )
            except Exception as exc:
                st.exception(exc)

# ─────────────────────────────────────────────
# TAB: Schedule View
# ─────────────────────────────────────────────
with tab_schedule:
    st.subheader("Schedule")

    if st.session_state.result is None:
        st.info("Generate a schedule first.")
    else:
        if _schedule_is_stale():
            st.warning("Your team has changed since the last Generate — re-generate to update the schedule.")
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()
        _mgr_result_json = st.session_state.mgr_result.model_dump_json() if st.session_state.mgr_result else ""
        _mgr_team_json   = st.session_state.mgr_team.model_dump_json() if st.session_state.mgr_team else ""

        # "This week" on-call callout
        _today = date.today()
        _this_week_assignments = [
            a for a in result.schedule.assignments
            if a.week_start <= _today <= a.week_end
        ]
        _next_week_assignments = [
            a for a in result.schedule.assignments
            if a.week_start > _today
        ]
        _current_assignments = _this_week_assignments or (
            _next_week_assignments[:len(set(a.region for a in result.schedule.assignments if a.region) or {"global"})]
            if _next_week_assignments else []
        )
        if _current_assignments:
            _person_map_cw = {p.id: p for p in team.people}
            _label = "This week" if _this_week_assignments else f"Next up from {_next_week_assignments[0].week_start}"
            _callout_parts = []
            for _ca in _current_assignments:
                _primary_cw = _person_map_cw.get(_ca.primary_id)
                _part = f"**{_primary_cw.name if _primary_cw else 'Unassigned'}**"
                if _ca.region:
                    _part += f" ({_ca.region})"
                _callout_parts.append(_part)
            _callout = f"📋 {_label}: {' · '.join(_callout_parts)}"
            if st.session_state.mgr_result:
                _mgr_map_cw = {p.id: p for p in st.session_state.mgr_team.people}
                _mgr_assignments_cw = [
                    a for a in st.session_state.mgr_result.schedule.assignments
                    if a.week_start <= _today <= a.week_end
                ] or st.session_state.mgr_result.schedule.assignments[:1]
                if _mgr_assignments_cw:
                    _mgr_person = _mgr_map_cw.get(_mgr_assignments_cw[0].primary_id)
                    _callout += f" · Manager: **{_mgr_person.name if _mgr_person else 'Unassigned'}**"
            st.info(_callout)

        # Summary line
        n_weeks = len(result.schedule.assignments)
        cfg = result.schedule.config
        st.caption(
            f"{n_weeks} weeks · {cfg.start_date} → {cfg.end_date} · "
            f"{len(team.people)} people · "
            f"{'regions: ' + ', '.join(cfg.required_regions) if cfg.required_regions else 'global rotation'}"
        )

        has_backup = any(a.backup_id for a in result.schedule.assignments)
        if not has_backup:
            if st.button("➕ Generate Backup On-Call", type="secondary"):
                try:
                    backup_config = result.schedule.config.model_copy(
                        update={"generate_backup": True}
                    )
                    backup_team = TeamConfig(
                        schedule=backup_config,
                        people=team.people,
                    )
                    with st.spinner("Assigning backup on-call..."):
                        from src.scheduler.generator import ScheduleGenerator as _SG
                        full_result = _SG(backup_team).generate()
                        backup_map = {
                            (a.week_start, a.region): a.backup_id
                            for a in full_result.schedule.assignments
                        }
                        for a in result.schedule.assignments:
                            a.backup_id = backup_map.get((a.week_start, a.region))
                        result.violations = validate(result, team)
                    st.session_state.result = result
                    st.success("Backup on-call added.")
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
        else:
            if st.button("🗑 Remove Backup On-Call", type="secondary"):
                for a in result.schedule.assignments:
                    a.backup_id = None
                result.violations = validate(result, team)
                st.session_state.result = result
                st.rerun()

        df_sched = _cached_schedule_df(_result_json, _team_json, _mgr_result_json, _mgr_team_json)

        if "Primary Engineer" in df_sched.columns:
            df_sched["Primary Engineer"] = df_sched["Primary Engineer"].replace("UNASSIGNED", "⚠️ UNASSIGNED")

        active_regions = result.schedule.config.required_regions
        if active_regions and "Region" in df_sched.columns:
            filter_region = st.selectbox("Filter by region", ["all"] + active_regions)
            if filter_region != "all":
                df_sched = df_sched[df_sched["Region"] == filter_region]

        row_height = 35 * len(df_sched) + 38
        col_cfg = {
            "Week Start":        st.column_config.TextColumn(width="small"),
            "Week End":          st.column_config.TextColumn(width="small"),
            "Primary Engineer":  st.column_config.TextColumn(width="medium"),
            "Engineer Country":  st.column_config.TextColumn("Country", width="small"),
            "Backup Engineer":   st.column_config.TextColumn(width="medium"),
            "Backup Country":    st.column_config.TextColumn("B.Country", width="small"),
            "Duty Manager":      st.column_config.TextColumn(width="medium"),
            "Team Holidays":     st.column_config.TextColumn(width="large"),
            "Notes":             st.column_config.TextColumn(width="small"),
        }
        st.dataframe(
            df_sched,
            use_container_width=True,
            height=min(row_height, 800),
            column_config=col_cfg,
        )

# ─────────────────────────────────────────────
# TAB: Fairness
# ─────────────────────────────────────────────
with tab_fairness:
    st.subheader("Fairness Report")

    if st.session_state.result is None:
        st.info("Generate a schedule first.")
    else:
        if _schedule_is_stale():
            st.warning("Your team has changed since the last Generate — re-generate to update the schedule.")
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()

        st.markdown("#### Engineer Fairness")
        fairness_rows = _cached_fairness(_result_json, _team_json)
        df_fair = pd.DataFrame([
            {
                "Name": r.name,
                "Country": r.country,
                "Primary Shifts": r.primary_shifts,
                "Backup Shifts": r.backup_shifts,
                "Expected Primary": r.expected_primary,
                "Deviation": r.deviation,
                "Holiday Weeks": r.holiday_weeks,
            }
            for r in fairness_rows
        ])
        st.dataframe(df_fair, use_container_width=True)
        max_dev = max(abs(r.deviation) for r in fairness_rows) if fairness_rows else 0
        if max_dev <= 1:
            st.success(f"Distribution is very fair (max deviation: {max_dev:.1f} shifts).")
        elif max_dev <= 2:
            st.info(f"Distribution is acceptable (max deviation: {max_dev:.1f} shifts).")
        else:
            st.warning(f"Distribution has notable imbalance (max deviation: {max_dev:.1f} shifts).")
        st.bar_chart(df_fair.set_index("Name")["Primary Shifts"])

        if st.session_state.mgr_result and st.session_state.mgr_team:
            st.markdown("#### Manager Fairness")
            _mgr_result_json = st.session_state.mgr_result.model_dump_json()
            _mgr_team_json   = st.session_state.mgr_team.model_dump_json()
            mgr_fairness_rows = _cached_fairness(_mgr_result_json, _mgr_team_json)
            df_mgr_fair = pd.DataFrame([
                {
                    "Name": r.name,
                    "Country": r.country,
                    "Duty Weeks": r.primary_shifts,
                    "Expected": r.expected_primary,
                    "Deviation": r.deviation,
                    "Holiday Weeks": r.holiday_weeks,
                }
                for r in mgr_fairness_rows
            ])
            st.dataframe(df_mgr_fair, use_container_width=True)
            mgr_max_dev = max(abs(r.deviation) for r in mgr_fairness_rows) if mgr_fairness_rows else 0
            if mgr_max_dev <= 1:
                st.success(f"Manager distribution is very fair (max deviation: {mgr_max_dev:.1f} weeks).")
            elif mgr_max_dev <= 2:
                st.info(f"Manager distribution is acceptable (max deviation: {mgr_max_dev:.1f} weeks).")
            else:
                st.warning(f"Manager distribution has notable imbalance (max deviation: {mgr_max_dev:.1f} weeks).")
            st.bar_chart(df_mgr_fair.set_index("Name")["Duty Weeks"])

# ─────────────────────────────────────────────
# TAB: Violations
# ─────────────────────────────────────────────
with tab_violations:
    st.subheader("Violations & Constraint Checks")

    if st.session_state.result is None:
        st.info("Generate a schedule first.")
    else:
        result = st.session_state.result
        violations = result.violations

        errors = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]

        _VIOLATION_LABELS = {
            "NO_PRIMARY_CANDIDATE": "No one available for primary on-call",
            "NO_BACKUP_CANDIDATE": "No one available for backup on-call",
            "BLACKOUT_VIOLATION": "Person assigned during their blackout period",
            "PRIMARY_EQUALS_BACKUP": "Primary and backup are the same person",
            "UNKNOWN_PERSON": "Unknown person ID in assignment",
            "REGION_MISMATCH": "Assigned person cannot cover this region",
            "GAP_TOO_SHORT": "On-call gap too short — minimum rest period not met",
            "HOLIDAY_ON_DUTY": "Person has a national holiday during their on-call week",
            "MAX_SHIFTS_EXCEEDED": "Person exceeds their maximum shifts per year",
        }

        col_e, col_w = st.columns(2)
        with col_e:
            if errors:
                st.error(f"**{len(errors)} error{'s' if len(errors) != 1 else ''}** (schedule needs attention)")
            else:
                st.success("0 errors")
        with col_w:
            if warnings:
                st.warning(f"**{len(warnings)} warning{'s' if len(warnings) != 1 else ''}** (review recommended)")
            else:
                st.success("0 warnings")

        if errors:
            st.error("**Errors** — these weeks may not have coverage:")
            for v in errors:
                _label = _VIOLATION_LABELS.get(v.code, v.code)
                st.write(f"- **{_label}**: {v.message}")
        if warnings:
            st.warning("**Warnings** — review recommended:")
            for v in warnings:
                _label = _VIOLATION_LABELS.get(v.code, v.code)
                st.write(f"- **{_label}**: {v.message}")
        if not violations:
            st.success("No violations found. Schedule is constraint-clean.")

# ─────────────────────────────────────────────
# TAB: Export
# ─────────────────────────────────────────────
with tab_export:
    st.subheader("Export Schedule")

    if st.session_state.result is None:
        st.info("Generate a schedule first.")
    else:
        if _schedule_is_stale():
            st.warning("Your team has changed since the last Generate — re-generate to update the schedule.")
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()
        _mgr_result_json = st.session_state.mgr_result.model_dump_json() if st.session_state.mgr_result else ""
        _mgr_team_json   = st.session_state.mgr_team.model_dump_json() if st.session_state.mgr_team else ""

        col_xl, col_csv_btn, col_ical = st.columns(3)

        with col_xl:
            xlsx_bytes = _cached_export_excel(_result_json, _team_json, _mgr_result_json, _mgr_team_json)
            st.download_button(
                label="⬇️ Download Excel (.xlsx)",
                data=xlsx_bytes,
                file_name="oncall_schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        with col_csv_btn:
            csv_str = _cached_export_csv(_result_json, _team_json, _mgr_result_json, _mgr_team_json)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_str,
                file_name="oncall_schedule.csv",
                mime="text/csv",
            )

        with col_ical:
            ical_str = _cached_export_ical(_result_json, _team_json, _mgr_result_json, _mgr_team_json)
            st.download_button(
                label="⬇️ Download iCal (.ics)",
                data=ical_str,
                file_name="oncall_schedule.ics",
                mime="text/calendar",
            )

        st.markdown("---")
        st.subheader("Export JSON (team config)")
        config_dict = {
            "schedule": {
                "start_date": str(team.schedule.start_date),
                "end_date": str(team.schedule.end_date),
                "shift_duration_days": team.schedule.shift_duration_days,
                "shift_start_day": team.schedule.shift_start_day.value,
                "min_gap_between_shifts_weeks": team.schedule.min_gap_between_shifts_weeks,
                "required_regions": team.schedule.required_regions,
            },
            "people": [
                {
                    "id": p.id,
                    "name": p.name,
                    "country": p.country,
                    "timezone": p.timezone,
                    "regions": p.regions,
                    "skills": p.skills,
                    "blackout_dates": [str(d) for d in p.blackout_dates],
                    "max_shifts_per_year": p.max_shifts_per_year,
                }
                for p in team.people
            ],
        }
        st.download_button(
            label="⬇️ Download team_config.json",
            data=json.dumps(config_dict, indent=2),
            file_name="team_config.json",
            mime="application/json",
        )
