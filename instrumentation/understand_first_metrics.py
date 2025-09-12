#!/usr/bin/env python3
"""
Understand-First Instrumentation & Metrics

Anonymous opt-in event tracking, derived KPIs, TTU/TTFSC measurement,
and performance monitoring for the Understand-First platform.
"""

import os
import json
import time
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import sys
from collections import defaultdict, Counter
import hashlib
import platform
import psutil
import threading
import queue
import logging
from contextlib import contextmanager


@dataclass
class Event:
    """Represents a tracked event."""

    event_id: str
    event_type: str
    timestamp: datetime
    user_id: str
    session_id: str
    properties: Dict[str, Any]
    platform: str
    version: str


@dataclass
class KPIMetric:
    """Represents a KPI metric."""

    name: str
    value: float
    unit: str
    timestamp: datetime
    dimensions: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class PerformanceMetric:
    """Represents a performance metric."""

    operation: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


class EventTracker:
    """Tracks user events and interactions."""

    def __init__(self, db_path: str = "metrics.db", opt_in: bool = True):
        self.db_path = db_path
        self.opt_in = opt_in
        self.user_id = self._get_or_create_user_id()
        self.session_id = str(uuid.uuid4())
        self.platform = platform.system()
        self.version = "1.0.0"
        self.event_queue = queue.Queue()
        self.worker_thread = None
        self.logger = logging.getLogger(__name__)

        if self.opt_in:
            self.init_database()
            self.start_worker()

    def _get_or_create_user_id(self) -> str:
        """Get or create anonymous user ID."""
        config_dir = Path.home() / ".understand-first"
        config_dir.mkdir(exist_ok=True)

        user_id_file = config_dir / "user_id"
        if user_id_file.exists():
            return user_id_file.read_text().strip()
        else:
            user_id = str(uuid.uuid4())
            user_id_file.write_text(user_id)
            return user_id

    def init_database(self):
        """Initialize the SQLite database for metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                event_type TEXT,
                timestamp DATETIME,
                user_id TEXT,
                session_id TEXT,
                properties TEXT,  -- JSON
                platform TEXT,
                version TEXT
            )
        """
        )

        # Create KPI metrics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kpi_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT,
                value REAL,
                unit TEXT,
                timestamp DATETIME,
                dimensions TEXT,  -- JSON
                metadata TEXT     -- JSON
            )
        """
        )

        # Create performance metrics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT,
                duration_ms REAL,
                memory_mb REAL,
                cpu_percent REAL,
                timestamp DATETIME,
                success BOOLEAN,
                error_message TEXT
            )
        """
        )

        # Create user sessions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                user_id TEXT,
                start_time DATETIME,
                end_time DATETIME,
                platform TEXT,
                version TEXT,
                properties TEXT  -- JSON
            )
        """
        )

        conn.commit()
        conn.close()

    def start_worker(self):
        """Start background worker for processing events."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._process_events, daemon=True)
            self.worker_thread.start()

    def _process_events(self):
        """Process events from the queue."""
        while True:
            try:
                event = self.event_queue.get(timeout=1)
                self._store_event(event)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")

    def _store_event(self, event: Event):
        """Store event in database."""
        if not self.opt_in:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO events 
                (event_id, event_type, timestamp, user_id, session_id, properties, platform, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.event_type,
                    event.timestamp,
                    event.user_id,
                    event.session_id,
                    json.dumps(event.properties),
                    event.platform,
                    event.version,
                ),
            )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error storing event: {e}")
        finally:
            conn.close()

    def track_event(self, event_type: str, properties: Dict[str, Any] = None):
        """Track a user event."""
        if not self.opt_in:
            return

        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=self.user_id,
            session_id=self.session_id,
            properties=properties or {},
            platform=self.platform,
            version=self.version,
        )

        self.event_queue.put(event)

    def track_ttu(self, feature: str, duration_seconds: float, success: bool = True):
        """Track Time-to-Understanding (TTU) for a feature."""
        self.track_event(
            "ttu_measurement",
            {
                "feature": feature,
                "duration_seconds": duration_seconds,
                "success": success,
                "ttu_category": self._categorize_ttu(duration_seconds),
            },
        )

    def track_ttfsc(self, change_type: str, duration_seconds: float, success: bool = True):
        """Track Time-to-First-Safe-Change (TTFSC) for a change type."""
        self.track_event(
            "ttfsc_measurement",
            {
                "change_type": change_type,
                "duration_seconds": duration_seconds,
                "success": success,
                "ttfsc_category": self._categorize_ttfsc(duration_seconds),
            },
        )

    def track_rage_click(self, element: str, count: int):
        """Track rage clicks on UI elements."""
        self.track_event(
            "rage_click",
            {
                "element": element,
                "click_count": count,
                "severity": "high" if count > 5 else "medium" if count > 3 else "low",
            },
        )

    def track_retry(self, operation: str, attempt: int, reason: str = None):
        """Track operation retries."""
        self.track_event(
            "retry",
            {
                "operation": operation,
                "attempt": attempt,
                "reason": reason,
                "retry_category": "excessive" if attempt > 3 else "normal",
            },
        )

    def track_funnel_step(self, funnel_name: str, step: str, success: bool = True):
        """Track funnel conversion steps."""
        self.track_event(
            "funnel_step",
            {
                "funnel_name": funnel_name,
                "step": step,
                "success": success,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def track_performance(
        self,
        operation: str,
        duration_ms: float,
        memory_mb: float = None,
        cpu_percent: float = None,
        success: bool = True,
        error_message: str = None,
    ):
        """Track performance metrics."""
        if not self.opt_in:
            return

        # Get current system metrics if not provided
        if memory_mb is None:
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        if cpu_percent is None:
            cpu_percent = psutil.cpu_percent()

        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            timestamp=datetime.now(),
            success=success,
            error_message=error_message,
        )

        # Store performance metric
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO performance_metrics 
                (operation, duration_ms, memory_mb, cpu_percent, timestamp, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metric.operation,
                    metric.duration_ms,
                    metric.memory_mb,
                    metric.cpu_percent,
                    metric.timestamp,
                    metric.success,
                    metric.error_message,
                ),
            )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error storing performance metric: {e}")
        finally:
            conn.close()

    def _categorize_ttu(self, duration_seconds: float) -> str:
        """Categorize TTU duration."""
        if duration_seconds <= 10:
            return "excellent"
        elif duration_seconds <= 30:
            return "good"
        elif duration_seconds <= 60:
            return "acceptable"
        else:
            return "poor"

    def _categorize_ttfsc(self, duration_seconds: float) -> str:
        """Categorize TTFSC duration."""
        if duration_seconds <= 3600:  # 1 hour
            return "excellent"
        elif duration_seconds <= 86400:  # 1 day
            return "good"
        elif duration_seconds <= 259200:  # 3 days
            return "acceptable"
        else:
            return "poor"

    @contextmanager
    def measure_performance(self, operation: str):
        """Context manager for measuring performance."""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        start_cpu = psutil.cpu_percent()

        success = True
        error_message = None

        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            self.track_performance(
                operation=operation,
                duration_ms=duration_ms,
                memory_mb=psutil.Process().memory_info().rss / 1024 / 1024,
                cpu_percent=psutil.cpu_percent(),
                success=success,
                error_message=error_message,
            )

    def get_kpis(self, days: int = 30) -> Dict[str, Any]:
        """Get derived KPIs from events."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate TTU metrics
        cursor.execute(
            """
            SELECT 
                AVG(CAST(JSON_EXTRACT(properties, '$.duration_seconds') AS REAL)) as avg_ttu,
                COUNT(*) as ttu_count,
                SUM(CASE WHEN JSON_EXTRACT(properties, '$.success') = 1 THEN 1 ELSE 0 END) as ttu_success_count
            FROM events 
            WHERE event_type = 'ttu_measurement' 
            AND timestamp >= datetime('now', '-{} days')
        """.format(
                days
            )
        )

        ttu_result = cursor.fetchone()
        avg_ttu = ttu_result[0] if ttu_result[0] else 0
        ttu_count = ttu_result[1] if ttu_result[1] else 0
        ttu_success_rate = (ttu_result[2] / ttu_count * 100) if ttu_count > 0 else 0

        # Calculate TTFSC metrics
        cursor.execute(
            """
            SELECT 
                AVG(CAST(JSON_EXTRACT(properties, '$.duration_seconds') AS REAL)) as avg_ttfsc,
                COUNT(*) as ttfsc_count,
                SUM(CASE WHEN JSON_EXTRACT(properties, '$.success') = 1 THEN 1 ELSE 0 END) as ttfsc_success_count
            FROM events 
            WHERE event_type = 'ttfsc_measurement' 
            AND timestamp >= datetime('now', '-{} days')
        """.format(
                days
            )
        )

        ttfsc_result = cursor.fetchone()
        avg_ttfsc = ttfsc_result[0] if ttfsc_result[0] else 0
        ttfsc_count = ttfsc_result[1] if ttfsc_result[1] else 0
        ttfsc_success_rate = (ttfsc_result[2] / ttfsc_count * 100) if ttfsc_count > 0 else 0

        # Calculate funnel metrics
        cursor.execute(
            """
            SELECT 
                JSON_EXTRACT(properties, '$.funnel_name') as funnel_name,
                JSON_EXTRACT(properties, '$.step') as step,
                COUNT(*) as count,
                SUM(CASE WHEN JSON_EXTRACT(properties, '$.success') = 1 THEN 1 ELSE 0 END) as success_count
            FROM events 
            WHERE event_type = 'funnel_step' 
            AND timestamp >= datetime('now', '-{} days')
            GROUP BY funnel_name, step
            ORDER BY funnel_name, step
        """.format(
                days
            )
        )

        funnel_data = cursor.fetchall()
        funnels = defaultdict(list)
        for row in funnel_data:
            funnel_name = row[0]
            step = row[1]
            count = row[2]
            success_count = row[3]
            conversion_rate = (success_count / count * 100) if count > 0 else 0

            funnels[funnel_name].append(
                {
                    "step": step,
                    "count": count,
                    "success_count": success_count,
                    "conversion_rate": conversion_rate,
                }
            )

        # Calculate retry metrics
        cursor.execute(
            """
            SELECT 
                JSON_EXTRACT(properties, '$.operation') as operation,
                AVG(CAST(JSON_EXTRACT(properties, '$.attempt') AS REAL)) as avg_attempts,
                COUNT(*) as retry_count
            FROM events 
            WHERE event_type = 'retry' 
            AND timestamp >= datetime('now', '-{} days')
            GROUP BY operation
        """.format(
                days
            )
        )

        retry_data = cursor.fetchall()
        retries = {row[0]: {"avg_attempts": row[1], "count": row[2]} for row in retry_data}

        # Calculate rage click metrics
        cursor.execute(
            """
            SELECT 
                JSON_EXTRACT(properties, '$.element') as element,
                AVG(CAST(JSON_EXTRACT(properties, '$.click_count') AS REAL)) as avg_clicks,
                COUNT(*) as rage_click_count
            FROM events 
            WHERE event_type = 'rage_click' 
            AND timestamp >= datetime('now', '-{} days')
            GROUP BY element
        """.format(
                days
            )
        )

        rage_click_data = cursor.fetchall()
        rage_clicks = {row[0]: {"avg_clicks": row[1], "count": row[2]} for row in rage_click_data}

        # Calculate performance metrics
        cursor.execute(
            """
            SELECT 
                operation,
                AVG(duration_ms) as avg_duration,
                AVG(memory_mb) as avg_memory,
                AVG(cpu_percent) as avg_cpu,
                COUNT(*) as operation_count,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
            FROM performance_metrics 
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY operation
        """.format(
                days
            )
        )

        performance_data = cursor.fetchall()
        performance = {}
        for row in performance_data:
            operation = row[0]
            avg_duration = row[1]
            avg_memory = row[2]
            avg_cpu = row[3]
            operation_count = row[4]
            success_count = row[5]
            success_rate = (success_count / operation_count * 100) if operation_count > 0 else 0

            performance[operation] = {
                "avg_duration_ms": avg_duration,
                "avg_memory_mb": avg_memory,
                "avg_cpu_percent": avg_cpu,
                "operation_count": operation_count,
                "success_rate": success_rate,
            }

        conn.close()

        return {
            "ttu": {
                "average_seconds": avg_ttu,
                "measurement_count": ttu_count,
                "success_rate": ttu_success_rate,
            },
            "ttfsc": {
                "average_seconds": avg_ttfsc,
                "measurement_count": ttfsc_count,
                "success_rate": ttfsc_success_rate,
            },
            "funnels": dict(funnels),
            "retries": retries,
            "rage_clicks": rage_clicks,
            "performance": performance,
        }

    def export_metrics(self, output_file: str, format: str = "json"):
        """Export metrics to file."""
        kpis = self.get_kpis()

        if format == "json":
            with open(output_file, "w") as f:
                json.dump(kpis, f, indent=2, default=str)
        elif format == "csv":
            import csv

            with open(output_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value", "Unit"])
                writer.writerow(["TTU Average", kpis["ttu"]["average_seconds"], "seconds"])
                writer.writerow(["TTU Success Rate", kpis["ttu"]["success_rate"], "percent"])
                writer.writerow(["TTFSC Average", kpis["ttfsc"]["average_seconds"], "seconds"])
                writer.writerow(["TTFSC Success Rate", kpis["ttfsc"]["success_rate"], "percent"])
        else:
            raise ValueError(f"Unsupported format: {format}")


def main():
    """Main entry point for metrics CLI."""
    parser = argparse.ArgumentParser(description="Understand-First Metrics")
    parser.add_argument("--db", default="metrics.db", help="Database file path")
    parser.add_argument("--export", help="Export metrics to file")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    parser.add_argument("--days", type=int, default=30, help="Number of days for metrics")
    parser.add_argument("--opt-in", action="store_true", help="Enable metrics collection")
    parser.add_argument("--opt-out", action="store_true", help="Disable metrics collection")

    args = parser.parse_args()

    if args.opt_in:
        print("Metrics collection enabled")
        return
    elif args.opt_out:
        print("Metrics collection disabled")
        return

    tracker = EventTracker(db_path=args.db, opt_in=True)

    if args.export:
        tracker.export_metrics(args.export, args.format)
        print(f"Metrics exported to {args.export}")
    else:
        kpis = tracker.get_kpis(args.days)
        print(json.dumps(kpis, indent=2, default=str))


if __name__ == "__main__":
    main()
