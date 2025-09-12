#!/usr/bin/env python3
"""
Context Debt Dashboard Web Server

A Flask-based web server for the Context Debt Dashboard.
"""

import os
import json
from flask import Flask, render_template, jsonify, request
from context_debt_dashboard import ContextDebtAnalyzer, ContextDebtDashboard
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize analyzer
analyzer = ContextDebtAnalyzer(os.environ.get("DB_PATH", "context_debt.db"))
dashboard = ContextDebtDashboard(analyzer)


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/dashboard")
def api_dashboard():
    """API endpoint for dashboard data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/metrics")
def api_metrics():
    """API endpoint for metrics data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify({"metrics": data.get("metrics", []), "timestamp": data.get("timestamp")})
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/hotspots")
def api_hotspots():
    """API endpoint for hotspots data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify({"hotspots": data.get("hotspots", []), "timestamp": data.get("timestamp")})
    except Exception as e:
        logger.error(f"Error getting hotspots: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/documentation-gaps")
def api_documentation_gaps():
    """API endpoint for documentation gaps data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify(
            {"gaps": data.get("documentation_gaps", []), "timestamp": data.get("timestamp")}
        )
    except Exception as e:
        logger.error(f"Error getting documentation gaps: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/call-chains")
def api_call_chains():
    """API endpoint for call chains data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify(
            {"call_chains": data.get("call_chains", []), "timestamp": data.get("timestamp")}
        )
    except Exception as e:
        logger.error(f"Error getting call chains: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/trends")
def api_trends():
    """API endpoint for trends data."""
    repository = request.args.get("repository")
    days = int(request.args.get("days", 30))

    try:
        data = analyzer.get_dashboard_data(repository, days)
        return jsonify({"trends": data.get("trends", []), "timestamp": data.get("timestamp")})
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """API endpoint for uploading analysis data."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        repository = data.get("repository", "unknown")
        run_id = analyzer.analyze_codebase(data, repository)

        return jsonify({"message": "Analysis uploaded successfully", "run_id": run_id})
    except Exception as e:
        logger.error(f"Error uploading analysis: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
