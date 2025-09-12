#!/usr/bin/env python3
"""
Understand-First Metrics Dashboard

A web dashboard for visualizing collected metrics and KPIs.
"""

import os
import json
from flask import Flask, render_template, jsonify, request
from understand_first_metrics import EventTracker
import logging
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize tracker
tracker = EventTracker(db_path=os.environ.get("DB_PATH", "metrics.db"), opt_in=True)


@app.route("/")
def index():
    """Main metrics dashboard page."""
    return render_template("metrics_dashboard.html")


@app.route("/api/metrics")
def api_metrics():
    """API endpoint for metrics data."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis)
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/ttu")
def api_ttu():
    """API endpoint for TTU metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["ttu"])
    except Exception as e:
        logger.error(f"Error getting TTU metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/ttfsc")
def api_ttfsc():
    """API endpoint for TTFSC metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["ttfsc"])
    except Exception as e:
        logger.error(f"Error getting TTFSC metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/funnels")
def api_funnels():
    """API endpoint for funnel metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["funnels"])
    except Exception as e:
        logger.error(f"Error getting funnel metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/performance")
def api_performance():
    """API endpoint for performance metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["performance"])
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/retries")
def api_retries():
    """API endpoint for retry metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["retries"])
    except Exception as e:
        logger.error(f"Error getting retry metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rage-clicks")
def api_rage_clicks():
    """API endpoint for rage click metrics."""
    days = int(request.args.get("days", 30))

    try:
        kpis = tracker.get_kpis(days)
        return jsonify(kpis["rage_clicks"])
    except Exception as e:
        logger.error(f"Error getting rage click metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
