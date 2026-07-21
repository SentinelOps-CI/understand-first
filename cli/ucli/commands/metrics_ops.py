"""Metrics display helpers and `u metrics` body (extracted from main.py)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ucli.metrics.analytics import get_dashboard_data, get_tracker, track_event


def show_metrics_dashboard(console: Console, data: dict[str, Any]):
    """Display comprehensive metrics dashboard"""

    # Header
    console.print(
        Panel(
            "[bold blue]📊 Understand-First Metrics Dashboard[/bold blue]\n"
            f"Period: Last {data['period_days']} days\n"
            f"Generated: {datetime.fromtimestamp(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}",
            title="Dashboard",
            border_style="blue",
        )
    )

    # North Star Goals Status
    goals_table = Table(title="North Star Goals Status", show_header=True)
    goals_table.add_column("Goal", style="cyan")
    goals_table.add_column("Target", style="yellow")
    goals_table.add_column("Current", style="white")
    goals_table.add_column("Status", style="green")

    # TTU Goal
    ttu_metrics = data["ttu_metrics"]
    ttu_current = ttu_metrics["average_ttu_minutes"]
    ttu_target = data["north_star_goals"]["ttu_target"]
    ttu_status = "✅" if ttu_current and ttu_current <= ttu_target else "❌"
    goals_table.add_row(
        "TTU (minutes)",
        f"≤{ttu_target}",
        f"{ttu_current:.1f}" if ttu_current else "N/A",
        ttu_status,
    )

    # Activation Goal
    activation_metrics = data["activation_metrics"]
    activation_current = activation_metrics["activation_rate_percentage"]
    activation_target = data["north_star_goals"]["activation_target"]
    activation_status = "✅" if activation_current >= activation_target else "❌"
    goals_table.add_row(
        "Activation Rate (%)",
        f"≥{activation_target}",
        f"{activation_current:.1f}",
        activation_status,
    )

    # Tour Completion Goal
    tour_metrics = data["tour_completion_metrics"]
    tour_current = tour_metrics["completion_rate_percentage"]
    tour_target = data["north_star_goals"]["tour_completion_target"]
    tour_status = "✅" if tour_current >= tour_target else "❌"
    goals_table.add_row(
        "Tour Completion (%)", f"≥{tour_target}", f"{tour_current:.1f}", tour_status
    )

    # PR Coverage Goal
    pr_metrics = data["pr_coverage_metrics"]
    pr_current = pr_metrics["coverage_rate_percentage"]
    pr_target = data["north_star_goals"]["pr_coverage_target"]
    pr_status = "✅" if pr_current >= pr_target else "❌"
    goals_table.add_row("PR Coverage (%)", f"≥{pr_target}", f"{pr_current:.1f}", pr_status)

    console.print(goals_table)
    console.print()

    # Detailed Metrics
    # TTU Metrics
    ttu_panel = Panel(
        f"📈 **TTU Metrics**\n"
        f"• Total sessions: {ttu_metrics['total_sessions']}\n"
        f"• Sessions with tour completion: {ttu_metrics['sessions_with_tour_completion']}\n"
        f"• Average TTU: {ttu_metrics['average_ttu_minutes']:.1f} minutes\n"
        f"• Under 10 minutes: {ttu_metrics['ttu_under_10_min_percentage']:.1f}%",
        title="Time-to-Understanding",
        border_style="blue",
    )
    console.print(ttu_panel)

    # Activation Metrics
    activation_panel = Panel(
        f"🚀 **Activation Metrics**\n"
        f"• Total sessions: {activation_metrics['total_sessions']}\n"
        f"• Activated sessions: {activation_metrics['activated_sessions']}\n"
        f"• Activation rate: {activation_metrics['activation_rate_percentage']:.1f}%\n"
        f"• Under 2 minutes: {activation_metrics['under_2_min_percentage']:.1f}%",
        title="User Activation",
        border_style="green",
    )
    console.print(activation_panel)

    # Tour Completion Metrics
    tour_panel = Panel(
        f"📚 **Tour Completion Metrics**\n"
        f"• Total tours: {tour_metrics['total_tours']}\n"
        f"• Completed tours: {tour_metrics['completed_tours']}\n"
        f"• Completion rate: {tour_metrics['completion_rate_percentage']:.1f}%\n"
        f"• Average completion: {tour_metrics['average_completion_percentage']:.1f}%",
        title="Tour Completion",
        border_style="yellow",
    )
    console.print(tour_panel)

    # PR Coverage Metrics
    pr_panel = Panel(
        f"🔀 **PR Coverage Metrics**\n"
        f"• Total PRs: {pr_metrics['total_prs']}\n"
        f"• PRs with artifacts: {pr_metrics['prs_with_artifacts']}\n"
        f"• Coverage rate: {pr_metrics['coverage_rate_percentage']:.1f}%",
        title="PR Coverage",
        border_style="red",
    )
    console.print(pr_panel)


def run_metrics(
    *,
    dashboard: bool = False,
    days: int = 30,
    export: str | None = None,
    track: str | None = None,
) -> None:
    """View and manage Understand-First metrics for TTU/TTFSC goals."""
    console = Console()
    try:
        if track:
            session_id = get_tracker().start_session()
            track_event(track, session_id)
            console.print(f"[green]Tracked event: {track}[/green]")
            return

        dashboard_data = get_dashboard_data(days)

        if dashboard:
            show_metrics_dashboard(console, dashboard_data)
        else:
            show_metrics_summary(console, dashboard_data)

        if export:
            with open(export, "w", encoding="utf-8") as f:
                json.dump(dashboard_data, f, indent=2)
            console.print(f"[green]Metrics exported to {export}[/green]")
    except Exception as e:
        console.print(f"[red]Error with metrics:[/red] {str(e)}")
        raise typer.Exit(1) from None


def show_metrics_summary(console: Console, data: dict[str, Any]):
    """Display metrics summary"""

    # Quick summary table
    summary_table = Table(
        title=f"Metrics Summary (Last {data['period_days']} days)", show_header=True
    )
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    summary_table.add_column("Target", style="yellow")

    # Add key metrics
    ttu_metrics = data["ttu_metrics"]
    activation_metrics = data["activation_metrics"]
    tour_metrics = data["tour_completion_metrics"]
    pr_metrics = data["pr_coverage_metrics"]

    summary_table.add_row(
        "Average TTU (minutes)",
        (
            f"{ttu_metrics['average_ttu_minutes']:.1f}"
            if ttu_metrics["average_ttu_minutes"]
            else "N/A"
        ),
        "≤10",
    )

    summary_table.add_row(
        "Activation Rate (%)", f"{activation_metrics['activation_rate_percentage']:.1f}", "≥80"
    )

    summary_table.add_row(
        "Tour Completion (%)", f"{tour_metrics['completion_rate_percentage']:.1f}", "≥80"
    )

    summary_table.add_row("PR Coverage (%)", f"{pr_metrics['coverage_rate_percentage']:.1f}", "≥90")

    console.print(summary_table)
    console.print()

    # Recommendations
    recommendations = []

    if not ttu_metrics["average_ttu_minutes"] or ttu_metrics["average_ttu_minutes"] > 10:
        recommendations.append(
            "🎯 Focus on reducing TTU: improve onboarding and tutorial experience"
        )

    if activation_metrics["activation_rate_percentage"] < 80:
        recommendations.append(
            "🚀 Improve activation: make map generation faster and more intuitive"
        )

    if tour_metrics["completion_rate_percentage"] < 80:
        recommendations.append("📚 Enhance tour experience: make tours more engaging and shorter")

    if pr_metrics["coverage_rate_percentage"] < 90:
        recommendations.append(
            "🔀 Increase PR coverage: automate understanding artifact generation"
        )

    if recommendations:
        console.print(
            Panel("\n".join(recommendations), title="Recommendations", border_style="yellow")
        )
