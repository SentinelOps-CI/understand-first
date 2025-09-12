#!/usr/bin/env python3
"""
Context Debt Dashboard

A comprehensive dashboard for tracking and visualizing context debt across
codebases, including missing documentation, complex call chains, and hotspots.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import sys
from collections import defaultdict, Counter
import re


@dataclass
class ContextDebtMetric:
    """Represents a context debt metric."""

    name: str
    value: float
    threshold: float
    severity: str  # low, medium, high, critical
    trend: str  # improving, stable, worsening
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CallChain:
    """Represents a function call chain."""

    functions: List[str]
    depth: int
    complexity: float
    file_path: str
    line_number: int
    is_hot_path: bool = False


@dataclass
class Hotspot:
    """Represents a code hotspot."""

    file_path: str
    function_name: str
    complexity: float
    call_frequency: int
    side_effects: int
    last_modified: datetime
    risk_score: float


@dataclass
class DocumentationGap:
    """Represents a documentation gap."""

    file_path: str
    function_name: Optional[str]
    gap_type: str  # missing_readme, missing_docstring, missing_type_hints, missing_comments
    severity: str
    impact: str
    suggested_action: str


class ContextDebtAnalyzer:
    """Analyzes context debt across codebases."""

    def __init__(self, db_path: str = "context_debt.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                repository TEXT,
                commit_hash TEXT,
                total_functions INTEGER,
                total_files INTEGER
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS context_debt_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                metric_name TEXT,
                value REAL,
                threshold REAL,
                severity TEXT,
                trend TEXT,
                description TEXT,
                file_path TEXT,
                line_number INTEGER,
                FOREIGN KEY (run_id) REFERENCES analysis_runs (id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS call_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                functions TEXT,  -- JSON array of function names
                depth INTEGER,
                complexity REAL,
                file_path TEXT,
                line_number INTEGER,
                is_hot_path BOOLEAN,
                FOREIGN KEY (run_id) REFERENCES analysis_runs (id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hotspots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                file_path TEXT,
                function_name TEXT,
                complexity REAL,
                call_frequency INTEGER,
                side_effects INTEGER,
                last_modified DATETIME,
                risk_score REAL,
                FOREIGN KEY (run_id) REFERENCES analysis_runs (id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documentation_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                file_path TEXT,
                function_name TEXT,
                gap_type TEXT,
                severity TEXT,
                impact TEXT,
                suggested_action TEXT,
                FOREIGN KEY (run_id) REFERENCES analysis_runs (id)
            )
        """
        )

        conn.commit()
        conn.close()

    def analyze_codebase(self, analysis_data: Dict[str, Any], repository: str = "unknown") -> int:
        """Analyze codebase and store results in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create analysis run record
        cursor.execute(
            """
            INSERT INTO analysis_runs (repository, commit_hash, total_functions, total_files)
            VALUES (?, ?, ?, ?)
        """,
            (
                repository,
                analysis_data.get("commit_hash", "unknown"),
                len(analysis_data.get("functions", {})),
                len(analysis_data.get("files", {})),
            ),
        )

        run_id = cursor.lastrowid

        # Analyze context debt metrics
        metrics = self._analyze_context_debt_metrics(analysis_data)
        for metric in metrics:
            cursor.execute(
                """
                INSERT INTO context_debt_metrics 
                (run_id, metric_name, value, threshold, severity, trend, description, file_path, line_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    metric.name,
                    metric.value,
                    metric.threshold,
                    metric.severity,
                    metric.trend,
                    metric.description,
                    metric.file_path,
                    metric.line_number,
                ),
            )

        # Analyze call chains
        call_chains = self._analyze_call_chains(analysis_data)
        for chain in call_chains:
            cursor.execute(
                """
                INSERT INTO call_chains 
                (run_id, functions, depth, complexity, file_path, line_number, is_hot_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    json.dumps(chain.functions),
                    chain.depth,
                    chain.complexity,
                    chain.file_path,
                    chain.line_number,
                    chain.is_hot_path,
                ),
            )

        # Analyze hotspots
        hotspots = self._analyze_hotspots(analysis_data)
        for hotspot in hotspots:
            cursor.execute(
                """
                INSERT INTO hotspots 
                (run_id, file_path, function_name, complexity, call_frequency, side_effects, last_modified, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    hotspot.file_path,
                    hotspot.function_name,
                    hotspot.complexity,
                    hotspot.call_frequency,
                    hotspot.side_effects,
                    hotspot.last_modified,
                    hotspot.risk_score,
                ),
            )

        # Analyze documentation gaps
        doc_gaps = self._analyze_documentation_gaps(analysis_data)
        for gap in doc_gaps:
            cursor.execute(
                """
                INSERT INTO documentation_gaps 
                (run_id, file_path, function_name, gap_type, severity, impact, suggested_action)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    gap.file_path,
                    gap.function_name,
                    gap.gap_type,
                    gap.severity,
                    gap.impact,
                    gap.suggested_action,
                ),
            )

        conn.commit()
        conn.close()

        return run_id

    def _analyze_context_debt_metrics(
        self, analysis_data: Dict[str, Any]
    ) -> List[ContextDebtMetric]:
        """Analyze context debt metrics."""
        metrics = []
        functions = analysis_data.get("functions", {})

        # Missing documentation metric
        total_functions = len(functions)
        documented_functions = sum(1 for f in functions.values() if f.get("has_docstring", False))
        doc_coverage = (documented_functions / total_functions * 100) if total_functions > 0 else 0

        metrics.append(
            ContextDebtMetric(
                name="Documentation Coverage",
                value=doc_coverage,
                threshold=80.0,
                severity="high" if doc_coverage < 50 else "medium" if doc_coverage < 80 else "low",
                trend="stable",  # Would need historical data to determine
                description=f"{documented_functions}/{total_functions} functions have docstrings",
            )
        )

        # High complexity functions
        high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 10)
        complexity_ratio = (high_complexity / total_functions * 100) if total_functions > 0 else 0

        metrics.append(
            ContextDebtMetric(
                name="High Complexity Functions",
                value=complexity_ratio,
                threshold=20.0,
                severity=(
                    "critical"
                    if complexity_ratio > 30
                    else "high" if complexity_ratio > 20 else "medium"
                ),
                trend="stable",
                description=f"{high_complexity} functions have complexity > 10",
            )
        )

        # Side effects without documentation
        unmanaged_side_effects = sum(
            1
            for f in functions.values()
            if f.get("side_effects", 0) > 0 and not f.get("side_effects_documented", False)
        )
        side_effects_ratio = (
            (unmanaged_side_effects / total_functions * 100) if total_functions > 0 else 0
        )

        metrics.append(
            ContextDebtMetric(
                name="Unmanaged Side Effects",
                value=side_effects_ratio,
                threshold=10.0,
                severity=(
                    "critical"
                    if side_effects_ratio > 20
                    else "high" if side_effects_ratio > 10 else "medium"
                ),
                trend="stable",
                description=f"{unmanaged_side_effects} functions have undocumented side effects",
            )
        )

        # Missing type hints
        typed_functions = sum(1 for f in functions.values() if f.get("has_type_hints", False))
        type_coverage = (typed_functions / total_functions * 100) if total_functions > 0 else 0

        metrics.append(
            ContextDebtMetric(
                name="Type Hint Coverage",
                value=type_coverage,
                threshold=70.0,
                severity=(
                    "high" if type_coverage < 50 else "medium" if type_coverage < 70 else "low"
                ),
                trend="stable",
                description=f"{typed_functions}/{total_functions} functions have type hints",
            )
        )

        return metrics

    def _analyze_call_chains(self, analysis_data: Dict[str, Any]) -> List[CallChain]:
        """Analyze function call chains."""
        chains = []
        functions = analysis_data.get("functions", {})

        for func_name, func_data in functions.items():
            # Find call chains starting from this function
            chain = self._build_call_chain(func_name, functions, set())
            if len(chain) > 1:  # Only include chains with multiple functions
                chains.append(
                    CallChain(
                        functions=chain,
                        depth=len(chain),
                        complexity=sum(functions.get(f, {}).get("complexity", 0) for f in chain),
                        file_path=func_data.get("file_path", ""),
                        line_number=func_data.get("line_number", 0),
                        is_hot_path=func_data.get("is_hot_path", False),
                    )
                )

        return chains

    def _build_call_chain(
        self, func_name: str, functions: Dict[str, Any], visited: set
    ) -> List[str]:
        """Build a call chain starting from a function."""
        if func_name in visited or func_name not in functions:
            return [func_name]

        visited.add(func_name)
        func_data = functions[func_name]
        calls = func_data.get("calls", [])

        if not calls:
            return [func_name]

        # Find the longest chain
        longest_chain = [func_name]
        for called_func in calls:
            if called_func not in visited:
                sub_chain = self._build_call_chain(called_func, functions, visited.copy())
                if len(sub_chain) > len(longest_chain):
                    longest_chain = [func_name] + sub_chain

        return longest_chain

    def _analyze_hotspots(self, analysis_data: Dict[str, Any]) -> List[Hotspot]:
        """Analyze code hotspots."""
        hotspots = []
        functions = analysis_data.get("functions", {})

        for func_name, func_data in functions.items():
            complexity = func_data.get("complexity", 0)
            call_frequency = func_data.get("call_frequency", 0)
            side_effects = func_data.get("side_effects", 0)

            # Calculate risk score
            risk_score = complexity * 0.3 + call_frequency * 0.2 + side_effects * 0.5

            hotspots.append(
                Hotspot(
                    file_path=func_data.get("file_path", ""),
                    function_name=func_name,
                    complexity=complexity,
                    call_frequency=call_frequency,
                    side_effects=side_effects,
                    last_modified=datetime.now(),  # Would need git history
                    risk_score=risk_score,
                )
            )

        return sorted(hotspots, key=lambda x: x.risk_score, reverse=True)

    def _analyze_documentation_gaps(self, analysis_data: Dict[str, Any]) -> List[DocumentationGap]:
        """Analyze documentation gaps."""
        gaps = []
        functions = analysis_data.get("functions", {})
        files = analysis_data.get("files", {})

        # Check for missing READMEs
        for file_path, file_data in files.items():
            if not file_data.get("has_readme", False):
                gaps.append(
                    DocumentationGap(
                        file_path=file_path,
                        function_name=None,
                        gap_type="missing_readme",
                        severity="medium",
                        impact="New developers may struggle to understand the module",
                        suggested_action="Add a README.md file with module description and usage examples",
                    )
                )

        # Check function documentation
        for func_name, func_data in functions.items():
            file_path = func_data.get("file_path", "")

            if not func_data.get("has_docstring", False):
                gaps.append(
                    DocumentationGap(
                        file_path=file_path,
                        function_name=func_name,
                        gap_type="missing_docstring",
                        severity="high",
                        impact="Function purpose and parameters are unclear",
                        suggested_action="Add a docstring explaining the function's purpose, parameters, and return value",
                    )
                )

            if not func_data.get("has_type_hints", False):
                gaps.append(
                    DocumentationGap(
                        file_path=file_path,
                        function_name=func_name,
                        gap_type="missing_type_hints",
                        severity="medium",
                        impact="Type information is missing, making the code harder to understand",
                        suggested_action="Add type hints for parameters and return value",
                    )
                )

            if func_data.get("side_effects", 0) > 0 and not func_data.get(
                "side_effects_documented", False
            ):
                gaps.append(
                    DocumentationGap(
                        file_path=file_path,
                        function_name=func_name,
                        gap_type="missing_side_effect_docs",
                        severity="critical",
                        impact="Side effects are not documented, leading to unexpected behavior",
                        suggested_action="Document all side effects in the function docstring",
                    )
                )

        return gaps

    def get_dashboard_data(self, repository: str = None, days: int = 30) -> Dict[str, Any]:
        """Get dashboard data for the specified repository and time period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get latest analysis run
        if repository:
            cursor.execute(
                """
                SELECT id, timestamp FROM analysis_runs 
                WHERE repository = ? 
                ORDER BY timestamp DESC LIMIT 1
            """,
                (repository,),
            )
        else:
            cursor.execute(
                """
                SELECT id, timestamp FROM analysis_runs 
                ORDER BY timestamp DESC LIMIT 1
            """
            )

        result = cursor.fetchone()
        if not result:
            conn.close()
            return {}

        run_id, timestamp = result

        # Get context debt metrics
        cursor.execute(
            """
            SELECT metric_name, value, threshold, severity, trend, description
            FROM context_debt_metrics WHERE run_id = ?
        """,
            (run_id,),
        )
        metrics = [
            dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()
        ]

        # Get call chains
        cursor.execute(
            """
            SELECT functions, depth, complexity, file_path, line_number, is_hot_path
            FROM call_chains WHERE run_id = ? ORDER BY depth DESC, complexity DESC
        """,
            (run_id,),
        )
        call_chains = []
        for row in cursor.fetchall():
            call_chains.append(
                {
                    "functions": json.loads(row[0]),
                    "depth": row[1],
                    "complexity": row[2],
                    "file_path": row[3],
                    "line_number": row[4],
                    "is_hot_path": bool(row[5]),
                }
            )

        # Get hotspots
        cursor.execute(
            """
            SELECT file_path, function_name, complexity, call_frequency, side_effects, risk_score
            FROM hotspots WHERE run_id = ? ORDER BY risk_score DESC LIMIT 20
        """,
            (run_id,),
        )
        hotspots = [
            dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()
        ]

        # Get documentation gaps
        cursor.execute(
            """
            SELECT file_path, function_name, gap_type, severity, impact, suggested_action
            FROM documentation_gaps WHERE run_id = ? ORDER BY severity DESC
        """,
            (run_id,),
        )
        doc_gaps = [
            dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()
        ]

        # Get trends over time
        cursor.execute(
            """
            SELECT DATE(timestamp) as date, 
                   AVG((SELECT COUNT(*) FROM context_debt_metrics WHERE run_id = analysis_runs.id AND severity = 'critical')) as critical_count,
                   AVG((SELECT COUNT(*) FROM context_debt_metrics WHERE run_id = analysis_runs.id AND severity = 'high')) as high_count
            FROM analysis_runs 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        """.format(
                days
            )
        )
        trends = [
            dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()
        ]

        conn.close()

        return {
            "timestamp": timestamp,
            "metrics": metrics,
            "call_chains": call_chains,
            "hotspots": hotspots,
            "documentation_gaps": doc_gaps,
            "trends": trends,
        }


class ContextDebtDashboard:
    """Main dashboard class for rendering context debt information."""

    def __init__(self, analyzer: ContextDebtAnalyzer):
        self.analyzer = analyzer

    def render_dashboard(self, repository: str = None, days: int = 30) -> str:
        """Render the dashboard as HTML."""
        data = self.analyzer.get_dashboard_data(repository, days)

        if not data:
            return "<h1>No data available</h1>"

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Context Debt Dashboard</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                }}
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .metric-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .metric-title {{
                    font-size: 14px;
                    color: #666;
                    margin-bottom: 8px;
                }}
                .metric-value {{
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 4px;
                }}
                .metric-threshold {{
                    font-size: 12px;
                    color: #999;
                }}
                .severity-critical {{ color: #dc3545; }}
                .severity-high {{ color: #fd7e14; }}
                .severity-medium {{ color: #ffc107; }}
                .severity-low {{ color: #28a745; }}
                .section {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                }}
                .section-title {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 16px;
                    color: #333;
                }}
                .hotspot-item {{
                    padding: 12px;
                    border: 1px solid #eee;
                    border-radius: 4px;
                    margin-bottom: 8px;
                }}
                .hotspot-name {{
                    font-weight: bold;
                    color: #333;
                }}
                .hotspot-details {{
                    font-size: 12px;
                    color: #666;
                    margin-top: 4px;
                }}
                .gap-item {{
                    padding: 12px;
                    border-left: 4px solid #dc3545;
                    background: #fff5f5;
                    margin-bottom: 8px;
                }}
                .gap-critical {{ border-left-color: #dc3545; }}
                .gap-high {{ border-left-color: #fd7e14; }}
                .gap-medium {{ border-left-color: #ffc107; }}
                .gap-low {{ border-left-color: #28a745; }}
                .chain-item {{
                    padding: 12px;
                    border: 1px solid #eee;
                    border-radius: 4px;
                    margin-bottom: 8px;
                }}
                .chain-functions {{
                    font-family: monospace;
                    background: #f8f9fa;
                    padding: 8px;
                    border-radius: 4px;
                    margin-top: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Context Debt Dashboard</h1>
                    <p>Last updated: {data['timestamp']}</p>
                </div>
                
                <div class="metrics-grid">
                    {self._render_metrics(data['metrics'])}
                </div>
                
                <div class="section">
                    <div class="section-title">🔥 Top Hotspots</div>
                    {self._render_hotspots(data['hotspots'])}
                </div>
                
                <div class="section">
                    <div class="section-title">📚 Documentation Gaps</div>
                    {self._render_documentation_gaps(data['documentation_gaps'])}
                </div>
                
                <div class="section">
                    <div class="section-title">🔗 Deepest Call Chains</div>
                    {self._render_call_chains(data['call_chains'])}
                </div>
                
                <div class="section">
                    <div class="section-title">📈 Trends Over Time</div>
                    {self._render_trends(data['trends'])}
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _render_metrics(self, metrics: List[Dict[str, Any]]) -> str:
        """Render metrics cards."""
        html = ""
        for metric in metrics:
            severity_class = f"severity-{metric['severity']}"
            html += f"""
            <div class="metric-card">
                <div class="metric-title">{metric['metric_name']}</div>
                <div class="metric-value {severity_class}">{metric['value']:.1f}%</div>
                <div class="metric-threshold">Threshold: {metric['threshold']}%</div>
                <div class="metric-description">{metric['description']}</div>
            </div>
            """
        return html

    def _render_hotspots(self, hotspots: List[Dict[str, Any]]) -> str:
        """Render hotspots list."""
        html = ""
        for hotspot in hotspots[:10]:  # Top 10
            html += f"""
            <div class="hotspot-item">
                <div class="hotspot-name">{hotspot['function_name']}</div>
                <div class="hotspot-details">
                    File: {hotspot['file_path']} | 
                    Complexity: {hotspot['complexity']:.1f} | 
                    Calls: {hotspot['call_frequency']} | 
                    Side Effects: {hotspot['side_effects']} | 
                    Risk Score: {hotspot['risk_score']:.1f}
                </div>
            </div>
            """
        return html

    def _render_documentation_gaps(self, gaps: List[Dict[str, Any]]) -> str:
        """Render documentation gaps list."""
        html = ""
        for gap in gaps[:20]:  # Top 20
            severity_class = f"gap-{gap['severity']}"
            html += f"""
            <div class="gap-item {severity_class}">
                <div class="gap-title">
                    {gap['gap_type'].replace('_', ' ').title()}
                    {f"in {gap['function_name']}" if gap['function_name'] else ""}
                </div>
                <div class="gap-file">{gap['file_path']}</div>
                <div class="gap-impact">{gap['impact']}</div>
                <div class="gap-action">{gap['suggested_action']}</div>
            </div>
            """
        return html

    def _render_call_chains(self, chains: List[Dict[str, Any]]) -> str:
        """Render call chains list."""
        html = ""
        for chain in chains[:10]:  # Top 10
            functions_str = " → ".join(chain["functions"])
            html += f"""
            <div class="chain-item">
                <div class="chain-details">
                    Depth: {chain['depth']} | 
                    Complexity: {chain['complexity']:.1f} | 
                    Hot Path: {'Yes' if chain['is_hot_path'] else 'No'}
                </div>
                <div class="chain-functions">{functions_str}</div>
            </div>
            """
        return html

    def _render_trends(self, trends: List[Dict[str, Any]]) -> str:
        """Render trends over time."""
        if not trends:
            return "<p>No trend data available</p>"

        html = "<div class='trends-chart'>"
        for trend in trends[-7:]:  # Last 7 days
            html += f"""
            <div class="trend-item">
                <div class="trend-date">{trend['date']}</div>
                <div class="trend-metrics">
                    Critical: {trend['critical_count']:.0f} | 
                    High: {trend['high_count']:.0f}
                </div>
            </div>
            """
        html += "</div>"
        return html


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Context Debt Dashboard")
    parser.add_argument("--analysis-file", help="Analysis JSON file to process")
    parser.add_argument("--repository", help="Repository name")
    parser.add_argument("--output", help="Output HTML file")
    parser.add_argument("--db", default="context_debt.db", help="Database file path")
    parser.add_argument("--days", type=int, default=30, help="Number of days for trends")

    args = parser.parse_args()

    analyzer = ContextDebtAnalyzer(args.db)

    if args.analysis_file:
        # Load and analyze the file
        with open(args.analysis_file, "r") as f:
            analysis_data = json.load(f)

        run_id = analyzer.analyze_codebase(analysis_data, args.repository or "unknown")
        print(f"Analysis completed, run ID: {run_id}")

    # Generate dashboard
    dashboard = ContextDebtDashboard(analyzer)
    html = dashboard.render_dashboard(args.repository, args.days)

    if args.output:
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Dashboard saved to {args.output}")
    else:
        print(html)


if __name__ == "__main__":
    main()
