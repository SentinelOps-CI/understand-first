"""
Understand-First Analytics and Metrics Tracking

This module implements North-Star metrics tracking for TTU and TTFSC goals:
- NS1: TTU — Minutes from first interaction to first correct reading plan
- NS2: TTFSC — Hours/days from first interaction to first PR merged with "Proof of Understanding" artifacts
- A1: Activation — % users who generate a map in ≤2 minutes from landing
- A2: Tour Completion — % sessions that finish ≥1 tour (≥80% steps viewed)
- A3: PR Coverage — % merged PRs with updated map deltas + tour notes
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import os


@dataclass
class TTUMetric:
    """Time-to-Understanding metric tracking"""

    session_id: str
    user_id: Optional[str]
    event_type: str  # 'demo_opened', 'code_pasted', 'map_rendered', 'tour_completed', etc.
    timestamp: float
    duration_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TTFSCMetric:
    """Time-to-First-Safe-Change metric tracking"""

    session_id: str
    user_id: Optional[str]
    event_type: str  # 'first_interaction', 'tour_generated', 'pr_created', 'pr_merged'
    timestamp: float
    pr_number: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ActivationMetric:
    """User activation tracking"""

    session_id: str
    user_id: Optional[str]
    event_type: str  # 'landing', 'map_generated'
    timestamp: float
    time_to_map_seconds: Optional[float] = None
    success: bool = False


@dataclass
class TourCompletionMetric:
    """Tour completion tracking"""

    session_id: str
    user_id: Optional[str]
    tour_id: str
    steps_total: int
    steps_viewed: int
    completion_percentage: float
    timestamp: float
    completed: bool = False


@dataclass
class PRCoverageMetric:
    """PR coverage tracking"""

    pr_number: str
    repository: str
    has_map_delta: bool
    has_tour_notes: bool
    has_understanding_artifacts: bool
    timestamp: float
    merged: bool = False


class MetricsTracker:
    """Central metrics tracking system"""

    def __init__(self, data_dir: Path = Path("metrics")):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)

        # Metrics files
        self.ttu_file = self.data_dir / "ttu_metrics.jsonl"
        self.ttfsc_file = self.data_dir / "ttfsc_metrics.jsonl"
        self.activation_file = self.data_dir / "activation_metrics.jsonl"
        self.tour_completion_file = self.data_dir / "tour_completion_metrics.jsonl"
        self.pr_coverage_file = self.data_dir / "pr_coverage_metrics.jsonl"

        # Session tracking
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _write_metric(self, metric: Any, file_path: Path):
        """Write metric to JSONL file"""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(metric)) + "\n")

    def start_session(self, user_id: Optional[str] = None) -> str:
        """Start a new tracking session"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "start_time": time.time(),
            "events": [],
            "first_interaction": None,
            "map_generated": False,
            "tour_completed": False,
        }
        return session_id

    def track_ttu_event(
        self,
        session_id: str,
        event_type: str,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track TTU-related event"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        metric = TTUMetric(
            session_id=session_id,
            user_id=self.sessions[session_id]["user_id"],
            event_type=event_type,
            timestamp=time.time(),
            duration_seconds=duration_seconds,
            metadata=metadata,
        )

        self._write_metric(metric, self.ttu_file)
        self.sessions[session_id]["events"].append(event_type)

        # Track first interaction
        if not self.sessions[session_id]["first_interaction"]:
            self.sessions[session_id]["first_interaction"] = time.time()

        # Track map generation
        if event_type == "map_rendered":
            self.sessions[session_id]["map_generated"] = True

        # Track tour completion
        if event_type == "tour_completed":
            self.sessions[session_id]["tour_completed"] = True

    def track_ttfsc_event(
        self,
        session_id: str,
        event_type: str,
        pr_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track TTFSC-related event"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        metric = TTFSCMetric(
            session_id=session_id,
            user_id=self.sessions[session_id]["user_id"],
            event_type=event_type,
            timestamp=time.time(),
            pr_number=pr_number,
            metadata=metadata,
        )

        self._write_metric(metric, self.ttfsc_file)

    def track_activation(self, session_id: str, event_type: str, success: bool = False):
        """Track user activation"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        time_to_map = None
        if event_type == "map_generated" and self.sessions[session_id]["first_interaction"]:
            time_to_map = time.time() - self.sessions[session_id]["first_interaction"]

        metric = ActivationMetric(
            session_id=session_id,
            user_id=self.sessions[session_id]["user_id"],
            event_type=event_type,
            timestamp=time.time(),
            time_to_map_seconds=time_to_map,
            success=success,
        )

        self._write_metric(metric, self.activation_file)

    def track_tour_completion(
        self, session_id: str, tour_id: str, steps_total: int, steps_viewed: int
    ):
        """Track tour completion"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        completion_percentage = (steps_viewed / steps_total) * 100 if steps_total > 0 else 0
        completed = completion_percentage >= 80  # 80% threshold for completion

        metric = TourCompletionMetric(
            session_id=session_id,
            user_id=self.sessions[session_id]["user_id"],
            tour_id=tour_id,
            steps_total=steps_total,
            steps_viewed=steps_viewed,
            completion_percentage=completion_percentage,
            timestamp=time.time(),
            completed=completed,
        )

        self._write_metric(metric, self.tour_completion_file)

    def track_pr_coverage(
        self,
        pr_number: str,
        repository: str,
        has_map_delta: bool,
        has_tour_notes: bool,
        has_understanding_artifacts: bool,
        merged: bool = False,
    ):
        """Track PR coverage with understanding artifacts"""
        metric = PRCoverageMetric(
            pr_number=pr_number,
            repository=repository,
            has_map_delta=has_map_delta,
            has_tour_notes=has_tour_notes,
            has_understanding_artifacts=has_understanding_artifacts,
            timestamp=time.time(),
            merged=merged,
        )

        self._write_metric(metric, self.pr_coverage_file)

    def get_ttu_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Calculate TTU metrics for the last N days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        ttu_events = []
        with open(self.ttu_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event["timestamp"] >= cutoff_time:
                        ttu_events.append(event)
                except json.JSONDecodeError:
                    continue

        # Calculate TTU metrics
        sessions = {}
        for event in ttu_events:
            session_id = event["session_id"]
            if session_id not in sessions:
                sessions[session_id] = {
                    "events": [],
                    "first_interaction": None,
                    "tour_completed": None,
                }

            sessions[session_id]["events"].append(event)

            if (
                event["event_type"] == "demo_opened"
                and not sessions[session_id]["first_interaction"]
            ):
                sessions[session_id]["first_interaction"] = event["timestamp"]

            if event["event_type"] == "tour_completed":
                sessions[session_id]["tour_completed"] = event["timestamp"]

        # Calculate average TTU
        ttu_times = []
        for session in sessions.values():
            if session["first_interaction"] and session["tour_completed"]:
                ttu_seconds = session["tour_completed"] - session["first_interaction"]
                ttu_times.append(ttu_seconds / 60)  # Convert to minutes

        avg_ttu = sum(ttu_times) / len(ttu_times) if ttu_times else None
        ttu_under_10_min = (
            len([t for t in ttu_times if t <= 10]) / len(ttu_times) if ttu_times else 0
        )

        return {
            "total_sessions": len(sessions),
            "sessions_with_tour_completion": len(
                [s for s in sessions.values() if s["tour_completed"]]
            ),
            "average_ttu_minutes": avg_ttu,
            "ttu_under_10_min_percentage": ttu_under_10_min * 100,
            "ttu_times": ttu_times,
        }

    def get_activation_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Calculate activation metrics for the last N days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        activation_events = []
        with open(self.activation_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event["timestamp"] >= cutoff_time:
                        activation_events.append(event)
                except json.JSONDecodeError:
                    continue

        # Group by session
        sessions = {}
        for event in activation_events:
            session_id = event["session_id"]
            if session_id not in sessions:
                sessions[session_id] = {"landing": None, "map_generated": None}

            if event["event_type"] == "landing":
                sessions[session_id]["landing"] = event
            elif event["event_type"] == "map_generated":
                sessions[session_id]["map_generated"] = event

        # Calculate activation rate
        total_sessions = len(sessions)
        activated_sessions = len(
            [s for s in sessions.values() if s["map_generated"] and s["landing"]]
        )
        activation_rate = (activated_sessions / total_sessions * 100) if total_sessions > 0 else 0

        # Calculate average time to map generation
        times_to_map = []
        for session in sessions.values():
            if session["landing"] and session["map_generated"]:
                time_to_map = session["map_generated"]["time_to_map_seconds"]
                if time_to_map and time_to_map <= 120:  # 2 minutes
                    times_to_map.append(time_to_map)

        avg_time_to_map = sum(times_to_map) / len(times_to_map) if times_to_map else None
        under_2_min_rate = len(times_to_map) / total_sessions * 100 if total_sessions > 0 else 0

        return {
            "total_sessions": total_sessions,
            "activated_sessions": activated_sessions,
            "activation_rate_percentage": activation_rate,
            "average_time_to_map_seconds": avg_time_to_map,
            "under_2_min_percentage": under_2_min_rate,
        }

    def get_tour_completion_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Calculate tour completion metrics for the last N days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        tour_events = []
        with open(self.tour_completion_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event["timestamp"] >= cutoff_time:
                        tour_events.append(event)
                except json.JSONDecodeError:
                    continue

        total_tours = len(tour_events)
        completed_tours = len([e for e in tour_events if e["completed"]])
        completion_rate = (completed_tours / total_tours * 100) if total_tours > 0 else 0

        avg_completion_percentage = (
            sum(e["completion_percentage"] for e in tour_events) / total_tours
            if total_tours > 0
            else 0
        )

        return {
            "total_tours": total_tours,
            "completed_tours": completed_tours,
            "completion_rate_percentage": completion_rate,
            "average_completion_percentage": avg_completion_percentage,
        }

    def get_pr_coverage_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Calculate PR coverage metrics for the last N days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        pr_events = []
        with open(self.pr_coverage_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event["timestamp"] >= cutoff_time:
                        pr_events.append(event)
                except json.JSONDecodeError:
                    continue

        total_prs = len(pr_events)
        prs_with_artifacts = len([e for e in pr_events if e["has_understanding_artifacts"]])
        coverage_rate = (prs_with_artifacts / total_prs * 100) if total_prs > 0 else 0

        return {
            "total_prs": total_prs,
            "prs_with_artifacts": prs_with_artifacts,
            "coverage_rate_percentage": coverage_rate,
        }

    def generate_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive dashboard data"""
        return {
            "period_days": days,
            "timestamp": time.time(),
            "ttu_metrics": self.get_ttu_metrics(days),
            "activation_metrics": self.get_activation_metrics(days),
            "tour_completion_metrics": self.get_tour_completion_metrics(days),
            "pr_coverage_metrics": self.get_pr_coverage_metrics(days),
            "north_star_goals": {
                "ttu_target": 10,  # minutes
                "ttfsc_target": 24,  # hours
                "activation_target": 80,  # percentage
                "tour_completion_target": 80,  # percentage
                "pr_coverage_target": 90,  # percentage
            },
        }


# Global tracker instance
_tracker: Optional[MetricsTracker] = None


def get_tracker() -> MetricsTracker:
    """Get global metrics tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = MetricsTracker()
    return _tracker


def track_event(event_type: str, session_id: Optional[str] = None, **kwargs):
    """Convenience function to track events"""
    tracker = get_tracker()

    # Create session if not provided
    if session_id is None:
        session_id = tracker.start_session()

    # Route to appropriate tracking method
    if event_type in ["demo_opened", "code_pasted", "map_rendered", "tour_completed"]:
        tracker.track_ttu_event(session_id, event_type, **kwargs)
    elif event_type in ["first_interaction", "pr_created", "pr_merged"]:
        tracker.track_ttfsc_event(session_id, event_type, **kwargs)
    elif event_type in ["landing", "map_generated"]:
        tracker.track_activation(session_id, event_type, **kwargs)
    else:
        # Default to TTU tracking
        tracker.track_ttu_event(session_id, event_type, **kwargs)


def track_ttu(event_type: str, session_id: str, **kwargs):
    """Track TTU-specific event"""
    get_tracker().track_ttu_event(session_id, event_type, **kwargs)


def track_ttfsc(event_type: str, session_id: str, **kwargs):
    """Track TTFSC-specific event"""
    get_tracker().track_ttfsc_event(session_id, event_type, **kwargs)


def track_activation(event_type: str, session_id: str, **kwargs):
    """Track activation event"""
    get_tracker().track_activation(session_id, event_type, **kwargs)


def track_tour_completion(session_id: str, tour_id: str, steps_total: int, steps_viewed: int):
    """Track tour completion"""
    get_tracker().track_tour_completion(session_id, tour_id, steps_total, steps_viewed)


def track_pr_coverage(pr_number: str, repository: str, **kwargs):
    """Track PR coverage"""
    get_tracker().track_pr_coverage(pr_number, repository, **kwargs)


def get_dashboard_data(days: int = 30) -> Dict[str, Any]:
    """Get dashboard data"""
    return get_tracker().generate_dashboard_data(days)


def generate_metrics_report(days: int = 30) -> str:
    """Generate a human-readable metrics report"""
    data = get_dashboard_data(days)

    report = f"""# Understand-First Metrics Report

## Period: Last {days} days
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## North-Star Metrics

### NS1: Time-to-Understanding (TTU)
- **Target**: ≤ 10 minutes
- **Current Average**: {data['ttu_metrics']['average_ttu_minutes']:.1f} minutes
- **Under 10 min**: {data['ttu_metrics']['ttu_under_10_min_percentage']:.1f}%
- **Status**: {'✅ MEETING TARGET' if data['ttu_metrics']['average_ttu_minutes'] and data['ttu_metrics']['average_ttu_minutes'] <= 10 else '❌ NEEDS IMPROVEMENT'}

### NS2: Time-to-First-Safe-Change (TTFSC)
- **Target**: ≤ 24 hours
- **Status**: {'✅ TRACKING' if data['pr_coverage_metrics']['total_prs'] > 0 else '⚠️ NO DATA'}

## Activation Metrics (A1)

- **Target**: 80% of users generate map in ≤2 minutes
- **Current Rate**: {data['activation_metrics']['activation_rate_percentage']:.1f}%
- **Under 2 min**: {data['activation_metrics']['under_2_min_percentage']:.1f}%
- **Status**: {'✅ MEETING TARGET' if data['activation_metrics']['activation_rate_percentage'] >= 80 else '❌ NEEDS IMPROVEMENT'}

## Tour Completion (A2)

- **Target**: 80% of sessions complete ≥1 tour
- **Current Rate**: {data['tour_completion_metrics']['completion_rate_percentage']:.1f}%
- **Average Completion**: {data['tour_completion_metrics']['average_completion_percentage']:.1f}%
- **Status**: {'✅ MEETING TARGET' if data['tour_completion_metrics']['completion_rate_percentage'] >= 80 else '❌ NEEDS IMPROVEMENT'}

## PR Coverage (A3)

- **Target**: 90% of PRs have understanding artifacts
- **Current Rate**: {data['pr_coverage_metrics']['coverage_rate_percentage']:.1f}%
- **Total PRs**: {data['pr_coverage_metrics']['total_prs']}
- **With Artifacts**: {data['pr_coverage_metrics']['prs_with_artifacts']}
- **Status**: {'✅ MEETING TARGET' if data['pr_coverage_metrics']['coverage_rate_percentage'] >= 90 else '❌ NEEDS IMPROVEMENT'}

## Recommendations

"""

    # Add recommendations based on metrics
    if (
        data["ttu_metrics"]["average_ttu_minutes"]
        and data["ttu_metrics"]["average_ttu_minutes"] > 10
    ):
        report += "- **TTU**: Focus on improving onboarding flow and reducing time to first map generation\n"

    if data["activation_metrics"]["activation_rate_percentage"] < 80:
        report += (
            "- **Activation**: Improve demo experience and make map generation more intuitive\n"
        )

    if data["tour_completion_metrics"]["completion_rate_percentage"] < 80:
        report += "- **Tour Completion**: Make tours more engaging and reduce friction\n"

    if data["pr_coverage_metrics"]["coverage_rate_percentage"] < 90:
        report += "- **PR Coverage**: Integrate understanding artifacts into PR workflow\n"

    if not any(
        [
            data["ttu_metrics"]["average_ttu_minutes"]
            and data["ttu_metrics"]["average_ttu_minutes"] > 10,
            data["activation_metrics"]["activation_rate_percentage"] < 80,
            data["tour_completion_metrics"]["completion_rate_percentage"] < 80,
            data["pr_coverage_metrics"]["coverage_rate_percentage"] < 90,
        ]
    ):
        report += "- **Overall**: All metrics are meeting targets! Keep up the excellent work.\n"

    report += f"""
## Data Summary

- **Total Sessions**: {data['ttu_metrics']['total_sessions']}
- **Sessions with Tour Completion**: {data['ttu_metrics']['sessions_with_tour_completion']}
- **Activated Sessions**: {data['activation_metrics']['activated_sessions']}
- **Total Tours**: {data['tour_completion_metrics']['total_tours']}
- **Total PRs**: {data['pr_coverage_metrics']['total_prs']}

---
*Report generated by Understand-First Analytics*
"""

    return report


def export_metrics_csv(days: int = 30, output_file: str = "metrics_export.csv"):
    """Export metrics data to CSV format"""
    import csv

    data = get_dashboard_data(days)

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(["Metric_Type", "Metric_Name", "Value", "Target", "Status", "Period_Days"])

        # Write TTU metrics
        ttu_avg = data["ttu_metrics"]["average_ttu_minutes"]
        writer.writerow(
            [
                "TTU",
                "Average_TTU_Minutes",
                f"{ttu_avg:.1f}" if ttu_avg else "N/A",
                "10",
                "MEETING" if ttu_avg and ttu_avg <= 10 else "NEEDS_IMPROVEMENT",
                days,
            ]
        )

        writer.writerow(
            [
                "TTU",
                "Under_10_Min_Percentage",
                f"{data['ttu_metrics']['ttu_under_10_min_percentage']:.1f}",
                "80",
                (
                    "MEETING"
                    if data["ttu_metrics"]["ttu_under_10_min_percentage"] >= 80
                    else "NEEDS_IMPROVEMENT"
                ),
                days,
            ]
        )

        # Write activation metrics
        writer.writerow(
            [
                "Activation",
                "Activation_Rate_Percentage",
                f"{data['activation_metrics']['activation_rate_percentage']:.1f}",
                "80",
                (
                    "MEETING"
                    if data["activation_metrics"]["activation_rate_percentage"] >= 80
                    else "NEEDS_IMPROVEMENT"
                ),
                days,
            ]
        )

        # Write tour completion metrics
        writer.writerow(
            [
                "Tour_Completion",
                "Completion_Rate_Percentage",
                f"{data['tour_completion_metrics']['completion_rate_percentage']:.1f}",
                "80",
                (
                    "MEETING"
                    if data["tour_completion_metrics"]["completion_rate_percentage"] >= 80
                    else "NEEDS_IMPROVEMENT"
                ),
                days,
            ]
        )

        # Write PR coverage metrics
        writer.writerow(
            [
                "PR_Coverage",
                "Coverage_Rate_Percentage",
                f"{data['pr_coverage_metrics']['coverage_rate_percentage']:.1f}",
                "90",
                (
                    "MEETING"
                    if data["pr_coverage_metrics"]["coverage_rate_percentage"] >= 90
                    else "NEEDS_IMPROVEMENT"
                ),
                days,
            ]
        )

    return output_file
