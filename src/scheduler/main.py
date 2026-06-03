"""
CLI entry point for the OnCall Planner scheduler engine.

Usage:
    python -m src.scheduler.main --config data/samples/team_config.json
    python -m src.scheduler.main --people data/samples/people.csv --schedule data/samples/schedule.json
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .exporter import export_to_csv, export_to_excel
from .fairness import compute_fairness, fairness_summary_text
from .generator import ScheduleGenerator
from .loader import load_from_csv, load_from_json
from .validator import validate, violations_summary_text

app = typer.Typer(help="OnCall Planner — global on-call schedule generator")
console = Console()


@app.command()
def generate(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="JSON config file (people + schedule)"),
    people: Optional[Path] = typer.Option(None, "--people", help="People CSV file"),
    schedule: Optional[Path] = typer.Option(None, "--schedule", help="Schedule config JSON"),
    output_dir: Path = typer.Option(Path("."), "--output", "-o", help="Output directory"),
    excel: bool = typer.Option(True, help="Write Excel output"),
    csv: bool = typer.Option(True, help="Write CSV output"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)

    # Load team config
    if config:
        team = load_from_json(config)
    elif people and schedule:
        team = load_from_csv(people, schedule)
    else:
        console.print("[red]Provide --config or both --people and --schedule[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Loaded {len(team.people)} people[/bold]")
    console.print(
        f"Planning period: {team.schedule.start_date} → {team.schedule.end_date}"
    )

    # Generate
    console.print("Generating schedule...")
    generator = ScheduleGenerator(team)
    result = generator.generate()

    # Validate (adds post-hoc violations)
    result.violations = validate(result, team)

    # Print schedule table
    _print_schedule_table(result, team)

    # Print fairness
    fairness_rows = compute_fairness(result, team)
    console.print("\n[bold]Fairness Report[/bold]")
    console.print(fairness_summary_text(fairness_rows))

    # Print violations
    console.print("\n[bold]Violations[/bold]")
    console.print(violations_summary_text(result.violations))

    # Export
    output_dir.mkdir(parents=True, exist_ok=True)
    if excel:
        out = output_dir / "schedule.xlsx"
        export_to_excel(result, team, out)
        console.print(f"[green]Excel written to {out}[/green]")
    if csv:
        out = output_dir / "schedule.csv"
        export_to_csv(result, team, out)
        console.print(f"[green]CSV written to {out}[/green]")

    if result.has_errors:
        console.print("[red bold]Schedule has errors — review violations above[/red bold]")
        raise typer.Exit(2)
    else:
        console.print("[green bold]Schedule generated successfully.[/green bold]")


def _print_schedule_table(result, team) -> None:
    person_map = {p.id: p for p in team.people}
    table = Table(title="Generated Schedule", show_lines=True)
    table.add_column("Week Start", style="cyan")
    table.add_column("Region")
    table.add_column("Primary", style="green")
    table.add_column("Backup", style="yellow")

    for a in result.schedule.assignments:
        primary = person_map.get(a.primary_id)
        backup = person_map.get(a.backup_id)
        table.add_row(
            str(a.week_start),
            a.region or "all",
            primary.name if primary else "[red]UNASSIGNED[/red]",
            backup.name if backup else "",
        )

    console.print(table)


if __name__ == "__main__":
    app()
