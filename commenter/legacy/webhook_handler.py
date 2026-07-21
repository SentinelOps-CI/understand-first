#!/usr/bin/env python3
"""
Understand-First Webhook Handler

Handles GitHub webhooks and triggers PR analysis.
"""

import os
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from understand_first_commenter import UnderstandFirstCommenter, CommenterConfig
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
DEFAULT_REPOSITORY = os.environ.get("DEFAULT_REPOSITORY", "your-org/your-repo")


def verify_webhook_signature(payload, signature):
    """Verify GitHub webhook signature."""
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("No webhook secret configured, skipping signature verification")
        return True

    expected_signature = (
        "sha256=" + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    )

    return hmac.compare_digest(signature, expected_signature)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle GitHub webhook events."""
    try:
        # Get signature
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            logger.error("No signature provided")
            return jsonify({"error": "No signature provided"}), 400

        # Verify signature
        if not verify_webhook_signature(request.data, signature):
            logger.error("Invalid signature")
            return jsonify({"error": "Invalid signature"}), 401

        # Parse payload
        payload = request.get_json()
        if not payload:
            logger.error("No payload provided")
            return jsonify({"error": "No payload provided"}), 400

        # Check event type
        event_type = request.headers.get("X-GitHub-Event")
        if event_type != "pull_request":
            logger.info(f"Ignoring event type: {event_type}")
            return jsonify({"message": "Event ignored"}), 200

        # Check action
        action = payload.get("action")
        if action not in ["opened", "synchronize", "reopened"]:
            logger.info(f"Ignoring action: {action}")
            return jsonify({"message": "Action ignored"}), 200

        # Extract PR information
        pr_data = payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        repository = payload.get("repository", {}).get("full_name")

        if not pr_number or not repository:
            logger.error("Missing PR number or repository")
            return jsonify({"error": "Missing PR information"}), 400

        # Create commenter config
        config = CommenterConfig(
            github_token=GITHUB_TOKEN,
            repository=repository,
            pr_number=pr_number,
            base_commit=pr_data.get("base", {}).get("sha"),
            head_commit=pr_data.get("head", {}).get("sha"),
        )

        # Run analysis
        commenter = UnderstandFirstCommenter(config)
        success = commenter.run_analysis_pipeline()

        if success:
            logger.info(f"Successfully analyzed PR #{pr_number}")
            return jsonify({"message": "Analysis completed successfully"}), 200
        else:
            logger.error(f"Failed to analyze PR #{pr_number}")
            return jsonify({"error": "Analysis failed"}), 500

    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


@app.route("/ready", methods=["GET"])
def readiness_check():
    """Readiness check endpoint."""
    # Check if required environment variables are set
    if not GITHUB_TOKEN:
        return jsonify({"status": "not ready", "reason": "GITHUB_TOKEN not set"}), 503

    return jsonify({"status": "ready"}), 200


@app.route("/analyze", methods=["POST"])
def manual_analysis():
    """Manual analysis endpoint."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        pr_number = data.get("pr_number")
        repository = data.get("repository", DEFAULT_REPOSITORY)

        if not pr_number:
            return jsonify({"error": "PR number required"}), 400

        # Create commenter config
        config = CommenterConfig(
            github_token=GITHUB_TOKEN,
            repository=repository,
            pr_number=pr_number,
            base_commit=data.get("base_commit"),
            head_commit=data.get("head_commit"),
        )

        # Run analysis
        commenter = UnderstandFirstCommenter(config)
        success = commenter.run_analysis_pipeline()

        if success:
            return jsonify({"message": "Analysis completed successfully"}), 200
        else:
            return jsonify({"error": "Analysis failed"}), 500

    except Exception as e:
        logger.error(f"Error in manual analysis: {e}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
