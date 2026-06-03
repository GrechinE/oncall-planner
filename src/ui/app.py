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

from src.scheduler.exporter import export_to_csv, export_to_excel, build_schedule_dataframe
from src.scheduler.fairness import compute_fairness
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.holidays import get_public_holidays, get_public_holidays_with_names
from src.scheduler.models import (
    Person,
    ScheduleConfig,
    ShiftStartDay,
    TeamConfig,
)
from src.scheduler.validator import validate, violations_summary_text


# ─────────────────────────────────────────────
# Cached helpers — only recompute when inputs change
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_holidays(country: str, year: int):
    return get_public_holidays_with_names(country.upper(), year)


@st.cache_data(show_spinner=False)
def _cached_schedule_df(result_json: str, people_json: str) -> pd.DataFrame:
    """Build the schedule dataframe from JSON-serialised inputs so st.cache_data can hash them."""
    import json as _json
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    return build_schedule_dataframe(result, team)


@st.cache_data(show_spinner=False)
def _cached_fairness(result_json: str, people_json: str):
    import json as _json
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    return compute_fairness(result, team)


@st.cache_data(show_spinner=False)
def _cached_export_excel(result_json: str, people_json: str) -> bytes:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    return export_to_excel(result, team)


@st.cache_data(show_spinner=False)
def _cached_export_csv(result_json: str, people_json: str) -> str:
    from src.scheduler.models import ScheduleResult, TeamConfig
    result = ScheduleResult.model_validate_json(result_json)
    team   = TeamConfig.model_validate_json(people_json)
    return export_to_csv(result, team)

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="OnCall Planner",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📅 OnCall Planner")
st.caption("Fair, holiday-aware on-call scheduling for any global team — engineering, ops, support, and more.")

# ─────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────
if "people" not in st.session_state:
    st.session_state.people = []
if "result" not in st.session_state:
    st.session_state.result = None
if "team" not in st.session_state:
    st.session_state.team = None

# ─────────────────────────────────────────────
# Sidebar — Schedule configuration
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Schedule Settings")

    start_date = st.date_input("Start Date", value=date(2026, 1, 4))
    end_date = st.date_input("End Date", value=date(2026, 12, 27))
    shift_duration = st.number_input("Shift Duration (days)", min_value=1, max_value=28, value=7)
    shift_start = st.selectbox("Shift Start Day", ["sunday", "monday"])
    min_gap = st.number_input("Min Gap Between Shifts (weeks)", min_value=1, max_value=12, value=4)

    st.subheader("Regions")
    regions_input = st.text_input(
        "Required regions (comma-separated)",
        value="",
        help="Leave blank for a single global rotation (everyone in one pool). "
             "Fill in e.g. 'americas, emea, apac' only if different groups cover different customers.",
    )
    required_regions = [r.strip() for r in regions_input.split(",") if r.strip()]

    st.subheader("Backup On-Call")
    generate_backup = st.toggle(
        "Generate backup during schedule generation",
        value=False,
        help="Off = primary-only schedule. Use the 'Generate Backup' button in the Schedule tab to add backup on demand.",
    )

    st.markdown("---")
    st.header("📥 Load Sample Team")
    if st.button("Load sample dataset"):
        sample_path = Path(__file__).parent.parent.parent / "data" / "samples" / "team_config.json"
        if sample_path.exists():
            import json as _json
            data = _json.loads(sample_path.read_text())
            people_data = data.get("people", [])
            st.session_state.people = people_data
            st.success(f"Loaded {len(people_data)} people from sample dataset.")
        else:
            st.error("Sample file not found.")

    st.markdown("---")
    st.header("📤 Upload Team JSON")
    uploaded = st.file_uploader("Upload team_config.json", type=["json"])
    if uploaded:
        data = json.loads(uploaded.read())
        if "people" in data:
            st.session_state.people = data["people"]
            st.success(f"Loaded {len(st.session_state.people)} people.")

# ─────────────────────────────────────────────
# Tab layout
# ─────────────────────────────────────────────
tab_team, tab_holidays, tab_generate, tab_schedule, tab_fairness, tab_violations, tab_export = st.tabs([
    "👥 Team", "🗓 Holidays", "⚡ Generate", "📋 Schedule", "⚖️ Fairness", "⚠️ Violations", "📤 Export"
])

# ─────────────────────────────────────────────
# TAB: Team
# ─────────────────────────────────────────────
with tab_team:
    st.subheader("Team Members")

    col_add, col_csv = st.columns([1, 1])

    with col_add:
        with st.expander("➕ Add Person", expanded=len(st.session_state.people) == 0):
            p_name = st.text_input("Full Name", key="new_name")
            p_country = st.text_input("Country (ISO code, e.g. US, IL, IN)", key="new_country", max_chars=3)
            p_tz = st.text_input("Timezone (IANA, e.g. America/New_York)", key="new_tz")

            # Regions: multiselect from the configured regions + optional free-text extras
            region_options = required_regions if required_regions else []
            p_regions_selected = st.multiselect(
                "Regions",
                options=region_options,
                help="Select all regions this person can cover.",
                key="new_regions_multi",
            )
            p_regions_extra = st.text_input(
                "Additional regions not listed above (comma-separated)",
                key="new_regions_extra",
                help="Leave blank if all regions are already selected above.",
            )

            p_skills = st.text_input("Skills (comma-separated)", key="new_skills")
            p_blackouts = st.text_input("Blackout Dates (YYYY-MM-DD, comma-separated)", key="new_blackouts")
            p_max = st.number_input("Max Shifts/Year (0 = unlimited)", min_value=0, value=12, key="new_max")

            if st.button("Add Person"):
                if not p_name or not p_country or not p_tz:
                    st.error("Name, Country and Timezone are required.")
                else:
                    # Auto-generate ID from name slug; append suffix if collision
                    import re as _re
                    base_id = _re.sub(r"[^a-z0-9]+", "-", p_name.strip().lower()).strip("-")
                    existing_ids = {p["id"] for p in st.session_state.people}
                    new_id = base_id
                    counter = 2
                    while new_id in existing_ids:
                        new_id = f"{base_id}-{counter}"
                        counter += 1

                    extra_regions = [r.strip() for r in p_regions_extra.split(",") if r.strip()]
                    all_regions = list(dict.fromkeys(p_regions_selected + extra_regions))

                    st.session_state.people.append({
                        "id": new_id,
                        "name": p_name,
                        "country": p_country.upper(),
                        "timezone": p_tz,
                        "regions": all_regions,
                        "skills": [s.strip() for s in p_skills.split(",") if s.strip()],
                        "blackout_dates": [b.strip() for b in p_blackouts.split(",") if b.strip()],
                        "max_shifts_per_year": int(p_max) if p_max > 0 else None,
                    })
                    st.success(f"Added {p_name} (ID: `{new_id}`).")
                    st.rerun()

    with col_csv:
        csv_upload = st.file_uploader("Upload people.csv", type=["csv"], key="people_csv")
        if csv_upload is not None:
            try:
                df_preview = pd.read_csv(csv_upload, dtype=str).fillna("")
                st.caption(f"{len(df_preview)} rows found in **{csv_upload.name}**")
                st.dataframe(df_preview[["id", "name", "country", "regions"]].head(10), use_container_width=True)
                if len(df_preview) > 10:
                    st.caption(f"... and {len(df_preview) - 10} more rows")

                if st.button(f"✅ Import {len(df_preview)} people", type="primary", key="btn_import_csv"):
                    added = 0
                    skipped = []
                    existing_ids = {p["id"] for p in st.session_state.people}
                    for _, row in df_preview.iterrows():
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
                    st.success(f"Imported {added} people.")
                    for msg in skipped:
                        st.warning(msg)
                    st.rerun()
            except Exception as exc:
                st.error(f"Failed to read CSV: {exc}")

    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if st.session_state.people:
        for i, p in enumerate(st.session_state.people):
            col_data, col_del = st.columns([12, 1])
            with col_data:
                st.write(
                    f"**{p['name']}** ({p['id']}) — {p['country']} · {p['timezone']} · "
                    f"regions: {', '.join(p.get('regions', [])) or '—'} · "
                    f"skills: {', '.join(p.get('skills', [])) or '—'} · "
                    f"max shifts: {p.get('max_shifts_per_year') or '∞'}"
                )
            with col_del:
                if st.button("✕", key=f"del_{i}", help=f"Remove {p['name']}"):
                    st.session_state.people.pop(i)
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
                    st.rerun()
            with col_no:
                if st.button("Cancel"):
                    st.session_state.confirm_clear = False
                    st.rerun()
    else:
        st.session_state.confirm_clear = False
        st.info("No team members yet. Add people above or load the sample dataset from the sidebar.")

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
        h_year = st.number_input("Year", value=2026, min_value=2020, max_value=2035)

    if st.button("Fetch Holidays"):
        country_upper = h_country.strip().upper()
        with st.spinner(f"Fetching holidays for {country_upper} {int(h_year)}..."):
            from src.scheduler.holidays import (
                _HOLIDAYS_LIB_COUNTRIES, _HOLIDAYS_LIB_AVAILABLE,
                _fetch_from_lib_with_names, _fetch_from_nager_with_names,
            )
            source = None
            hdays = _fetch_from_lib_with_names(country_upper, int(h_year))
            if hdays is not None:
                source = "offline library"
            else:
                hdays = _fetch_from_nager_with_names(country_upper, int(h_year))
                if hdays is not None:
                    source = "Nager.Date API"

            if hdays:
                rows = sorted(hdays.items())
                df_h = pd.DataFrame(rows, columns=["Date", "Holiday Name"])
                df_h["Day"] = df_h["Date"].apply(lambda d: d.strftime("%A"))
                df_h = df_h[["Date", "Day", "Holiday Name"]]
                st.success(f"{len(hdays)} holidays for {country_upper} {int(h_year)} (source: {source}).")
                st.dataframe(df_h, use_container_width=True)
            else:
                # Give actionable diagnostics
                if not _HOLIDAYS_LIB_AVAILABLE:
                    st.warning("The `holidays` Python library is not installed.")
                elif country_upper not in _HOLIDAYS_LIB_COUNTRIES:
                    st.warning(
                        f"**{country_upper}** is not in the offline holidays library. "
                        f"Tried Nager.Date API — no data returned. "
                        f"Check: correct ISO 3166-1 alpha-2 code? (e.g. GB not UK, MX not MEX). "
                        f"Network accessible?"
                    )
                else:
                    st.warning(
                        f"No holiday data returned for **{country_upper}** {int(h_year)}. "
                        f"The offline library returned nothing — this country may have no public holidays defined."
                    )

    if st.session_state.people:
        st.markdown("---")
        st.subheader("Team Holiday Summary")
        countries = list({p["country"] for p in st.session_state.people})
        year = start_date.year
        for c in sorted(countries):
            hnamed = _cached_holidays(c.upper(), year)
            count = len(hnamed) if hnamed else 0
            with st.expander(f"**{c}** — {count} holidays in {year}"):
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
        st.write(f"**Team size:** {len(st.session_state.people)} people")
        st.write(f"**Period:** {start_date} → {end_date}")
        st.write(f"**Regions:** {', '.join(required_regions) if required_regions else 'global'}")
        st.write(f"**Shift:** {shift_duration} days, starting {shift_start}, min gap {min_gap} weeks")

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

                with st.spinner("Generating..."):
                    generator = ScheduleGenerator(team)
                    result = generator.generate()
                    result.violations = validate(result, team)

                st.session_state.result = result
                st.session_state.team = team

                errors = sum(1 for v in result.violations if v.severity == "error")
                warnings = sum(1 for v in result.violations if v.severity == "warning")
                total_weeks = len(result.schedule.assignments)

                if errors == 0:
                    st.success(
                        f"Schedule generated: {total_weeks} assignments, "
                        f"0 errors, {warnings} warnings."
                    )
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
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()

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
                        # Re-run generation with backup enabled and graft backup_ids
                        # onto the existing primary assignments
                        from src.scheduler.generator import ScheduleGenerator as _SG
                        full_result = _SG(backup_team).generate()
                        # Map week_start+region -> backup_id from the full run
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

        df_sched = _cached_schedule_df(_result_json, _team_json)

        # Replace "UNASSIGNED" with a more visible marker for the UI
        if "Primary" in df_sched.columns:
            df_sched["Primary"] = df_sched["Primary"].replace("UNASSIGNED", "⚠️ UNASSIGNED")

        # Filter by region only when regions are configured
        active_regions = result.schedule.config.required_regions
        if active_regions and "Region" in df_sched.columns:
            filter_region = st.selectbox("Filter by region", ["all"] + active_regions)
            if filter_region != "all":
                df_sched = df_sched[df_sched["Region"] == filter_region]

        # Show all rows — height = 35px per row + 38px header
        row_height = 35 * len(df_sched) + 38
        col_cfg = {
            "Week Start":      st.column_config.TextColumn(width="small"),
            "Week End":        st.column_config.TextColumn(width="small"),
            "Primary":         st.column_config.TextColumn(width="medium"),
            "Primary Country": st.column_config.TextColumn("Country", width="small"),
            "Backup":          st.column_config.TextColumn(width="medium"),
            "Backup Country":  st.column_config.TextColumn("B.Country", width="small"),
            "Team Holidays":   st.column_config.TextColumn(width="large"),
            "Notes":           st.column_config.TextColumn(width="small"),
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
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()
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
            st.warning(
                f"Distribution has notable imbalance (max deviation: {max_dev:.1f} shifts). "
                f"Check the table for outliers."
            )

        st.bar_chart(df_fair.set_index("Name")["Primary Shifts"])

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

        col_e, col_w = st.columns(2)
        col_e.metric("Errors", len(errors), delta=None)
        col_w.metric("Warnings", len(warnings), delta=None)

        if errors:
            st.error("**Errors** (must fix):")
            for v in errors:
                st.write(f"- `[{v.code}]` {v.message}")
        if warnings:
            st.warning("**Warnings** (review recommended):")
            for v in warnings:
                st.write(f"- `[{v.code}]` {v.message}")
        if not violations:
            st.success("No violations found! Schedule is constraint-clean.")

# ─────────────────────────────────────────────
# TAB: Export
# ─────────────────────────────────────────────
with tab_export:
    st.subheader("Export Schedule")

    if st.session_state.result is None:
        st.info("Generate a schedule first.")
    else:
        result = st.session_state.result
        team = st.session_state.team
        _result_json = result.model_dump_json()
        _team_json   = team.model_dump_json()

        col_xl, col_csv_btn = st.columns(2)

        with col_xl:
            xlsx_bytes = _cached_export_excel(_result_json, _team_json)
            st.download_button(
                label="⬇️ Download Excel (.xlsx)",
                data=xlsx_bytes,
                file_name="oncall_schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        with col_csv_btn:
            csv_str = _cached_export_csv(_result_json, _team_json)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_str,
                file_name="oncall_schedule.csv",
                mime="text/csv",
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
