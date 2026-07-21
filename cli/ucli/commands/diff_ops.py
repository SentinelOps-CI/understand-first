"""Map/lens delta computation and `u diff` presentation (extracted from main).

Complexity is McCabe cyclomatic from Python AST maps. JS/TS maps contribute
keyword-heuristic complexity only — deltas label fidelity so totals are not
misread as uniform McCabe. Side-effect diffs use heuristic `side_effects`
lists when present (Python analyzer); JS maps typically leave them empty.
"""

from __future__ import annotations

import json
import os
import pathlib
import traceback
from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from ucli.analyzers.map_meta import complexity_semantics_note, map_fidelity_label
from ucli.metrics.ttu import record as ttu_record
from ucli.visual.delta import lens_delta_svg


def _maps_complexity_note(old_data: dict[str, Any], new_data: dict[str, Any]) -> str:
    notes = {
        complexity_semantics_note(old_data),
        complexity_semantics_note(new_data),
    }
    labels = {map_fidelity_label(old_data), map_fidelity_label(new_data)}
    kinds = {old_data.get("complexity_kind"), new_data.get("complexity_kind")}
    if labels <= {"ast"} and kinds <= {"mccabe", None}:
        return "Complexity = McCabe cyclomatic on Python AST maps."
    if labels <= {"ast"} and "ast-cyclomatic" in kinds:
        return (
            "Complexity = AST decision-point cyclomatic (JS/TS ast-cyclomatic and/or "
            "Python McCabe); check analyzer ids — not interchangeable totals."
        )
    if labels <= {"best-effort"}:
        return "Complexity = keyword-heuristic on JS/TS best-effort maps (not McCabe)."
    if "mixed" in labels or labels == {"ast", "best-effort"}:
        return (
            "Complexity mixes AST cyclomatic and keyword-heuristic paths; "
            "net totals are not uniform McCabe."
        )
    return " ".join(sorted(notes))


def compute_map_delta(
    old_data: dict[str, Any],
    new_data: dict[str, Any],
    *,
    policy_threshold: int = 5,
    old_label: str = "",
    new_label: str = "",
) -> dict[str, Any]:
    """Compare two map/lens JSON documents and return a structured delta."""
    old_functions = set(old_data.get("functions", {}).keys())
    new_functions = set(new_data.get("functions", {}).keys())
    added_functions = sorted(new_functions - old_functions)
    removed_functions = sorted(old_functions - new_functions)
    modified_functions: list[str] = []
    policy_breaches: list[dict[str, Any]] = []
    complexity_increased: list[dict[str, Any]] = []
    complexity_decreased: list[dict[str, Any]] = []
    side_effects_added: list[dict[str, Any]] = []
    side_effects_removed: list[dict[str, Any]] = []

    def _cc(meta: dict[str, Any]) -> int:
        c = meta.get("complexity", 0)
        if isinstance(c, dict):
            return int(c.get("cyclomatic", 0) or 0)
        return int(c or 0)

    def _se(meta: dict[str, Any]) -> list[str]:
        raw = meta.get("side_effects")
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if isinstance(raw, (int, float)):
            return []
        return []

    total_old = sum(_cc(old_data["functions"][f]) for f in old_functions)
    total_new = sum(_cc(new_data["functions"][f]) for f in new_functions)
    for func in sorted(old_functions & new_functions):
        old_func = old_data["functions"][func]
        new_func = new_data["functions"][func]
        old_c, new_c = _cc(old_func), _cc(new_func)
        old_se, new_se = _se(old_func), _se(new_func)
        changed = (
            old_c != new_c
            or old_se != new_se
            or old_func.get("lines", 0) != new_func.get("lines", 0)
        )
        if not changed:
            continue
        modified_functions.append(func)
        if new_c > old_c:
            complexity_increased.append(
                {"function": func, "old_complexity": old_c, "new_complexity": new_c}
            )
        elif new_c < old_c:
            complexity_decreased.append(
                {"function": func, "old_complexity": old_c, "new_complexity": new_c}
            )
        se_add = sorted(set(new_se) - set(old_se))
        se_rem = sorted(set(old_se) - set(new_se))
        if se_add:
            side_effects_added.append({"function": func, "tags": se_add})
        if se_rem:
            side_effects_removed.append({"function": func, "tags": se_rem})
        if new_c > policy_threshold:
            policy_breaches.append(
                {
                    "function": func,
                    "old_complexity": old_c,
                    "new_complexity": new_c,
                    "threshold": policy_threshold,
                }
            )
    for func in added_functions:
        func_data = new_data["functions"][func]
        new_c = _cc(func_data)
        if new_c > 0:
            complexity_increased.append(
                {"function": func, "old_complexity": 0, "new_complexity": new_c}
            )
        se = _se(func_data)
        if se:
            side_effects_added.append({"function": func, "tags": se})
        if new_c > policy_threshold:
            policy_breaches.append(
                {
                    "function": func,
                    "old_complexity": 0,
                    "new_complexity": new_c,
                    "threshold": policy_threshold,
                }
            )
    for func in removed_functions:
        old_c = _cc(old_data["functions"][func])
        if old_c > 0:
            complexity_decreased.append(
                {"function": func, "old_complexity": old_c, "new_complexity": 0}
            )
        se = _se(old_data["functions"][func])
        if se:
            side_effects_removed.append({"function": func, "tags": se})
    net_change = total_new - total_old
    return {
        "summary": {
            "added": len(added_functions),
            "removed": len(removed_functions),
            "modified": len(modified_functions),
            "total_changes": len(added_functions)
            + len(removed_functions)
            + len(modified_functions),
            "policy_breaches": len(policy_breaches),
            "policy_threshold": policy_threshold,
            "complexity_net_change": net_change,
            "complexity_total_old": total_old,
            "complexity_total_new": total_new,
            "side_effects_added": len(side_effects_added),
            "side_effects_removed": len(side_effects_removed),
            "complexity_note": _maps_complexity_note(old_data, new_data),
            "old_fidelity": map_fidelity_label(old_data),
            "new_fidelity": map_fidelity_label(new_data),
        },
        "added_functions": added_functions,
        "removed_functions": removed_functions,
        "modified_functions": modified_functions,
        "policy_breaches": policy_breaches,
        "complexity_delta": {
            "net_change": net_change,
            "total_old": total_old,
            "total_new": total_new,
            "increased": complexity_increased,
            "decreased": complexity_decreased,
            "note": _maps_complexity_note(old_data, new_data),
        },
        "side_effects_added": side_effects_added,
        "side_effects_removed": side_effects_removed,
        "old_lens": old_label,
        "new_lens": new_label,
        "timestamp": datetime.now().isoformat(),
    }


def generate_enhanced_diff_markdown(
    added_functions,
    removed_functions,
    modified_functions,
    policy_breaches,
    changes_count,
    policy_threshold,
) -> str:
    """Generate enhanced Markdown summary of diff analysis with policy breach information."""
    content = "# Delta Analysis Summary\n\n"
    content += f"**Total Changes:** {changes_count}\n"
    content += f"**Policy Breaches:** {len(policy_breaches)}\n"
    content += f"**Policy Threshold:** {policy_threshold}\n\n"
    if policy_breaches:
        content += "## Policy Breaches Detected\n\n"
        content += (
            f"The following functions exceed the complexity threshold of {policy_threshold}:\n\n"
        )
        for breach in policy_breaches:
            content += (
                f"- **{breach['function']}**: {breach['old_complexity']} → "
                f"{breach['new_complexity']} (threshold: {breach['threshold']})\n"
            )
        content += "\n"
    elif changes_count > 0:
        content += "## Changes Detected\n\n"
        content += "The following changes were detected in your codebase:\n\n"
    else:
        content += "## No Changes Detected\n\n"
        content += "Your codebase has no changes since the last analysis.\n\n"
    if added_functions:
        content += f"## Added Functions ({len(added_functions)})\n\n"
        for func in sorted(added_functions):
            content += f"- `{func}`\n"
        content += "\n"
    if removed_functions:
        content += f"## Removed Functions ({len(removed_functions)})\n\n"
        for func in sorted(removed_functions):
            content += f"- `{func}`\n"
        content += "\n"
    if modified_functions:
        content += f"## Modified Functions ({len(modified_functions)})\n\n"
        for func in sorted(modified_functions):
            content += f"- `{func}`\n"
        content += "\n"
    content += "## Review Checklist\n\n"
    content += "- [ ] Review added functions for new side effects\n"
    content += "- [ ] Verify removed functions don't break dependencies\n"
    content += "- [ ] Check modified functions for complexity changes\n"
    if policy_breaches:
        content += f"- [ ] **Address policy breaches (complexity > {policy_threshold})**\n"
    content += "- [ ] Update documentation if needed\n"
    content += "- [ ] Update understanding tours if needed\n"
    content += "- [ ] Update CI/CD policies if needed\n\n"
    content += "## Exit Codes\n\n"
    content += "The following exit codes are used for CI integration:\n\n"
    content += "- **0**: No changes detected\n"
    content += "- **2**: Changes detected (update tours/documentation)\n"
    content += "- **3**: Policy breaches detected (address complexity issues)\n\n"
    content += "*Generated by Understand-First*"
    return content


def run_diff(
    old_lens: str,
    new_lens: str,
    o: str,
    *,
    verbose: bool = False,
    json_output: bool = False,
    markdown: bool = False,
    ci_gate: bool = False,
    policy_threshold: int = 5,
) -> None:
    """Compare two lens files and generate delta visualization with enhanced analysis."""
    console = Console()
    try:
        if not pathlib.Path(old_lens).exists():
            console.print(
                Panel.fit(
                    f"[red]Error: Old lens file '{old_lens}' does not exist[/red]\n\n"
                    "This could mean:\n"
                    "• The file path is incorrect\n"
                    "• The file hasn't been generated yet\n"
                    "• There's a typo in the filename",
                    title="File Not Found",
                    border_style="red",
                )
            )
            raise typer.Exit(1) from None
        if not pathlib.Path(new_lens).exists():
            console.print(
                Panel.fit(
                    f"[red]Error: New lens file '{new_lens}' does not exist[/red]\n\n"
                    "This could mean:\n"
                    "• The file path is incorrect\n"
                    "• The file hasn't been generated yet\n"
                    "• There's a typo in the filename",
                    title="File Not Found",
                    border_style="red",
                )
            )
            raise typer.Exit(1) from None
        try:
            with open(old_lens, encoding="utf-8") as f:
                old_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing old lens file:[/red] {str(e)}")
            raise typer.Exit(1) from None
        try:
            with open(new_lens, encoding="utf-8") as f:
                new_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing new lens file:[/red] {str(e)}")
            raise typer.Exit(1) from None
        config_table = Table(title="Delta Analysis Configuration", show_header=False)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        config_table.add_row("Old Lens", old_lens)
        config_table.add_row("New Lens", new_lens)
        config_table.add_row("Output Format", "JSON" if json_output else "SVG")
        config_table.add_row("Output File", o)
        config_table.add_row("Policy Threshold", str(policy_threshold))
        config_table.add_row("CI Gate", "Enabled" if ci_gate else "Disabled")
        console.print(config_table)
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            diff_task = progress.add_task("Analyzing differences...", total=100)
            progress.update(diff_task, advance=10)
            progress.update(diff_task, advance=20)
            delta_data = compute_map_delta(
                old_data,
                new_data,
                policy_threshold=policy_threshold,
                old_label=old_lens,
                new_label=new_lens,
            )
            added_functions = set(delta_data["added_functions"])
            removed_functions = set(delta_data["removed_functions"])
            modified_functions = list(delta_data["modified_functions"])
            policy_breaches = list(delta_data["policy_breaches"])
            progress.update(diff_task, advance=50)
            if json_output:
                os.makedirs(pathlib.Path(o).parent, exist_ok=True)
                with open(o, "w", encoding="utf-8") as f:
                    json.dump(delta_data, f, indent=2)
            else:
                svg = lens_delta_svg(old_lens, new_lens)
                with open(o, "w", encoding="utf-8") as df:
                    df.write(svg)
            progress.update(diff_task, advance=20)
        changes_count = len(added_functions) + len(removed_functions) + len(modified_functions)
        if policy_breaches:
            border_style = "red"
            status_icon = "!"
            status_text = "Policy breaches detected!"
        elif changes_count > 0:
            border_style = "yellow"
            status_icon = "~"
            status_text = "Changes detected"
        else:
            border_style = "green"
            status_icon = "OK"
            status_text = "No changes detected"
        net_cc = delta_data.get("summary", {}).get("complexity_net_change", 0)
        results_panel = Panel(
            f"[green]Delta analysis completed![/green]\n\n"
            f"[bold]Changes Summary:[/bold]\n"
            f"   • Functions added: {len(added_functions)}\n"
            f"   • Functions removed: {len(removed_functions)}\n"
            f"   • Functions modified: {len(modified_functions)}\n"
            f"   • Total changes: {changes_count}\n"
            f"   • Complexity net change: {net_cc:+d}\n"
            f"   • Policy breaches: {len(policy_breaches)}\n"
            f"   • Output file: {o}\n\n"
            f"[bold]Review Impact:[/bold]\n"
            f"   • Check added functions for new side effects\n"
            f"   • Verify removed functions don't break dependencies\n"
            f"   • Review modified functions for complexity changes\n"
            f"   • Address policy breaches (complexity > {policy_threshold})",
            title=f"{status_icon} Delta Analysis Results - {status_text}",
            border_style=border_style,
        )
        console.print(results_panel)
        if policy_breaches:
            console.print("\n[bold red]Policy Breaches Detected:[/bold red]")
            breach_table = Table(title="Functions Exceeding Complexity Threshold")
            breach_table.add_column("Function", style="cyan")
            breach_table.add_column("Old Complexity", justify="center", style="yellow")
            breach_table.add_column("New Complexity", justify="center", style="red")
            breach_table.add_column("Threshold", justify="center", style="magenta")
            for breach in policy_breaches:
                breach_table.add_row(
                    breach["function"],
                    str(breach["old_complexity"]),
                    str(breach["new_complexity"]),
                    str(breach["threshold"]),
                )
            console.print(breach_table)
        if verbose and changes_count > 0:
            if added_functions:
                console.print("\n[bold green]Added Functions:[/bold green]")
                for func in sorted(added_functions):
                    func_data = new_data["functions"][func]
                    complexity = func_data.get("complexity", 0)
                    side_effects = func_data.get("side_effects", [])
                    effects_str = (
                        f" (side effects: {', '.join(side_effects)})" if side_effects else ""
                    )
                    console.print(f"  + {func} (complexity: {complexity}){effects_str}")
            if removed_functions:
                console.print("\n[bold red]Removed Functions:[/bold red]")
                for func in sorted(removed_functions):
                    console.print(f"  - {func}")
            if modified_functions:
                console.print("\n[bold yellow]Modified Functions:[/bold yellow]")
                for func in sorted(modified_functions):
                    old_func = old_data["functions"][func]
                    new_func = new_data["functions"][func]
                    old_complexity = old_func.get("complexity", 0)
                    new_complexity = new_func.get("complexity", 0)
                    console.print(f"  ~ {func} (complexity: {old_complexity} → {new_complexity})")
        ttu_record(
            "diff_analyzed",
            {
                "changes_count": changes_count,
                "added": len(added_functions),
                "removed": len(removed_functions),
                "modified": len(modified_functions),
                "policy_breaches": len(policy_breaches),
            },
        )
        if markdown:
            markdown_content = generate_enhanced_diff_markdown(
                added_functions,
                removed_functions,
                modified_functions,
                policy_breaches,
                changes_count,
                policy_threshold,
            )
            markdown_path = o.replace(".svg", ".md").replace(".json", ".md")
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            console.print(f"[green]Markdown summary written to {markdown_path}[/green]")
        if ci_gate:
            if policy_breaches:
                console.print(
                    f"\n[red]Policy breaches detected! {len(policy_breaches)} functions "
                    f"exceed complexity threshold of {policy_threshold}.[/red]"
                )
                raise typer.Exit(3)
            if changes_count > 0:
                console.print(
                    "\n[yellow]Changes detected. Consider updating tours and documentation.[/yellow]"
                )
                raise typer.Exit(2)
            console.print("\n[green]No changes detected.[/green]")
            raise typer.Exit(0)
        if policy_breaches:
            console.print(
                f"\n[red]Policy breaches detected! {len(policy_breaches)} functions "
                f"exceed complexity threshold of {policy_threshold}.[/red]"
            )
        elif changes_count > 0:
            console.print(
                "\n[yellow]Changes detected. Consider updating tours and documentation.[/yellow]"
            )
        else:
            console.print("\n[green]No changes detected.[/green]")
        raise typer.Exit(0) from None
    except typer.Exit:
        raise
    except Exception as e:
        console.print(
            Panel.fit(
                f"[red]Error during diff analysis:[/red] {str(e)}\n\n"
                "This might be due to:\n"
                "• Corrupted lens files\n"
                "• File permission issues\n"
                "• Invalid JSON format\n\n"
                "Try running with --verbose for more details",
                title="Analysis Error",
                border_style="red",
            )
        )
        if verbose:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None
