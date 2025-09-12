#!/usr/bin/env python3
"""
Understand-First GitHub PR Commenter Service

A standalone service that analyzes PRs and posts comprehensive comments
with delta analysis, mini-maps, and policy compliance checks.
"""

import os
import json
import base64
import requests
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import argparse
import sys


@dataclass
class CommenterConfig:
    """Configuration for the commenter service."""

    github_token: str
    repository: str
    pr_number: int
    base_commit: Optional[str] = None
    head_commit: Optional[str] = None
    policy_rules: List[Dict[str, Any]] = None
    output_format: str = "markdown"
    include_minimap: bool = True
    include_artifacts: bool = True


class UnderstandFirstCommenter:
    """Main commenter service class."""

    def __init__(self, config: CommenterConfig):
        self.config = config
        self.github_headers = {
            "Authorization": f"token {config.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Understand-First-Commenter/1.0",
        }
        self.temp_dir = tempfile.mkdtemp(prefix="uf-commenter-")

    def run_analysis(self, commit_sha: str, output_file: str) -> bool:
        """Run understand-first analysis on a specific commit."""
        try:
            cmd = [
                "u",
                "analyze",
                "--output",
                output_file,
                "--format",
                "json",
                "--commit",
                commit_sha,
                "--verbose",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)
            if result.returncode != 0:
                print(f"Analysis failed for {commit_sha}: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"Error running analysis: {e}")
            return False

    def generate_delta_analysis(self, base_file: str, head_file: str, output_file: str) -> bool:
        """Generate delta analysis between two analysis results."""
        try:
            cmd = [
                "u",
                "diff",
                base_file,
                head_file,
                "--output",
                output_file,
                "--format",
                "json",
                "--policy-check",
                "--verbose",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)
            if result.returncode != 0:
                print(f"Delta analysis failed: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"Error generating delta analysis: {e}")
            return False

    def generate_minimap(self, base_file: str, head_file: str, output_file: str) -> bool:
        """Generate mini-map visualization."""
        try:
            cmd = ["u", "diff", base_file, head_file, "--output", output_file, "--format", "svg"]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)
            return result.returncode == 0
        except Exception as e:
            print(f"Error generating mini-map: {e}")
            return False

    def get_pr_details(self) -> Optional[Dict[str, Any]]:
        """Get PR details from GitHub API."""
        try:
            url = f"https://api.github.com/repos/{self.config.repository}/pulls/{self.config.pr_number}"
            response = requests.get(url, headers=self.github_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching PR details: {e}")
            return None

    def load_analysis_data(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load analysis data from JSON file."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading analysis data: {e}")
            return None

    def create_enhanced_comment(
        self, delta_data: Dict[str, Any], comment_content: str, minimap_svg: str = None
    ) -> str:
        """Create enhanced PR comment with all features."""

        violations = delta_data.get("violations", [])
        policy_passed = len(violations) == 0

        # Convert SVG to data URL if provided
        minimap_html = ""
        if minimap_svg and self.config.include_minimap:
            minimap_base64 = base64.b64encode(minimap_svg.encode()).decode()
            minimap_data_url = f"data:image/svg+xml;base64,{minimap_base64}"
            minimap_html = f"""
### 📊 Mini-Map Visualization
<img src="{minimap_data_url}" alt="Code Map Delta" width="100%" />
"""

        # Policy compliance section
        policy_section = (
            "✅ **All policies passed!** No violations detected."
            if policy_passed
            else "\n".join([f'❌ **{v["rule"]}**: {v["description"]}' for v in violations])
        )

        # Action items
        action_items = (
            "✅ Ready to merge!"
            if policy_passed
            else "\n".join(
                [f'- [ ] Fix: {v["description"]} in `{v["function_name"]}`' for v in violations]
            )
        )

        # Key metrics
        metrics = {
            "functions_added": len(delta_data.get("functions_added", [])),
            "functions_removed": len(delta_data.get("functions_removed", [])),
            "functions_modified": len(delta_data.get("functions_modified", [])),
            "complexity_change": delta_data.get("complexity_change", 0),
            "side_effects_added": len(delta_data.get("side_effects_added", [])),
            "side_effects_removed": len(delta_data.get("side_effects_removed", [])),
        }

        enhanced_comment = f"""
## 🔍 Understand-First PR Analysis

{comment_content}

{minimap_html}
### ✅ Policy Compliance Checklist
{policy_section}

### 📈 Key Metrics
- **Functions Added**: {metrics['functions_added']}
- **Functions Removed**: {metrics['functions_removed']}
- **Functions Modified**: {metrics['functions_modified']}
- **Complexity Change**: {metrics['complexity_change']:+d}
- **Side Effects**: {metrics['side_effects_added']} added, {metrics['side_effects_removed']} removed

### 🎯 Action Items
{action_items}

### 📊 Analysis Summary
- **Total Functions**: {delta_data.get('total_functions', 0)}
- **Hot Paths**: {len(delta_data.get('hot_paths', []))}
- **Critical Functions**: {len(delta_data.get('critical_functions', []))}
- **Risk Score**: {delta_data.get('risk_score', 0):.2f}/10

---
*Generated by [Understand-First](https://github.com/your-org/understand-first) • [View full analysis](https://github.com/{self.config.repository}/pull/{self.config.pr_number}/checks)*
"""

        return enhanced_comment

    def post_comment(self, comment_body: str) -> bool:
        """Post or update PR comment."""
        try:
            # Get existing comments
            comments_url = f"https://api.github.com/repos/{self.config.repository}/issues/{self.config.pr_number}/comments"
            response = requests.get(comments_url, headers=self.github_headers)
            response.raise_for_status()
            comments = response.json()

            # Find existing understand-first comment
            existing_comment = next(
                (c for c in comments if "Understand-First PR Analysis" in c["body"]), None
            )

            if existing_comment:
                # Update existing comment
                update_url = f'https://api.github.com/repos/{self.config.repository}/issues/comments/{existing_comment["id"]}'
                response = requests.patch(
                    update_url, headers=self.github_headers, json={"body": comment_body}
                )
                response.raise_for_status()
                print("Updated existing comment")
            else:
                # Create new comment
                response = requests.post(
                    comments_url, headers=self.github_headers, json={"body": comment_body}
                )
                response.raise_for_status()
                print("Created new comment")

            return True
        except Exception as e:
            print(f"Error posting comment: {e}")
            return False

    def create_check_run(self, delta_data: Dict[str, Any], head_sha: str) -> bool:
        """Create GitHub Check Run."""
        try:
            violations = delta_data.get("violations", [])
            policy_passed = len(violations) == 0

            check_run_data = {
                "name": "Understand-First Analysis",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success" if policy_passed else "failure",
                "output": {
                    "title": (
                        "✅ Understand-First Policy Check Passed"
                        if policy_passed
                        else "❌ Understand-First Policy Check Failed"
                    ),
                    "summary": (
                        "All code quality policies passed. The PR is safe to merge."
                        if policy_passed
                        else f"{len(violations)} policy violations detected. Please review before merging."
                    ),
                    "text": (
                        "\n\n".join(
                            [
                                f'**{v["rule"]}**: {v["description"]}\n'
                                f'- Function: {v["function_name"]}\n'
                                f'- Severity: {v["severity"]}\n'
                                f'- File: {v["file_path"]}:{v["line_number"]}'
                                for v in violations
                            ]
                        )
                        if violations
                        else "No violations found."
                    ),
                },
                "actions": [
                    {
                        "label": "View Full Report",
                        "description": "Open detailed analysis report",
                        "identifier": "view-report",
                    },
                    {
                        "label": "Download Artifacts",
                        "description": "Download analysis artifacts",
                        "identifier": "download-artifacts",
                    },
                ],
            }

            checks_url = f"https://api.github.com/repos/{self.config.repository}/check-runs"
            response = requests.post(checks_url, headers=self.github_headers, json=check_run_data)
            response.raise_for_status()
            print("Created Check Run")
            return True
        except Exception as e:
            print(f"Error creating check run: {e}")
            return False

    def set_commit_status(self, head_sha: str, policy_passed: bool) -> bool:
        """Set commit status."""
        try:
            status_data = {
                "state": "success" if policy_passed else "failure",
                "description": (
                    "Understand-First: All policies passed"
                    if policy_passed
                    else "Understand-First: Policy violations detected"
                ),
                "context": "understand-first/policy-check",
            }

            status_url = (
                f"https://api.github.com/repos/{self.config.repository}/statuses/{head_sha}"
            )
            response = requests.post(status_url, headers=self.github_headers, json=status_data)
            response.raise_for_status()
            print("Set commit status")
            return True
        except Exception as e:
            print(f"Error setting commit status: {e}")
            return False

    def run_analysis_pipeline(self) -> bool:
        """Run the complete analysis pipeline."""
        try:
            # Get PR details
            pr_data = self.get_pr_details()
            if not pr_data:
                return False

            base_sha = self.config.base_commit or pr_data["base"]["sha"]
            head_sha = self.config.head_commit or pr_data["head"]["sha"]

            print(f"Analyzing PR #{self.config.pr_number}: {pr_data['title']}")
            print(f"Base: {base_sha[:8]} -> Head: {head_sha[:8]}")

            # Run analysis on both commits
            base_file = os.path.join(self.temp_dir, "base-analysis.json")
            head_file = os.path.join(self.temp_dir, "head-analysis.json")

            if not self.run_analysis(base_sha, base_file):
                return False
            if not self.run_analysis(head_sha, head_file):
                return False

            # Generate delta analysis
            delta_file = os.path.join(self.temp_dir, "pr-delta.json")
            if not self.generate_delta_analysis(base_file, head_file, delta_file):
                return False

            # Load delta data
            delta_data = self.load_analysis_data(delta_file)
            if not delta_data:
                return False

            # Generate mini-map
            minimap_file = os.path.join(self.temp_dir, "pr-minimap.svg")
            minimap_svg = None
            if self.config.include_minimap:
                if self.generate_minimap(base_file, head_file, minimap_file):
                    with open(minimap_file, "r") as f:
                        minimap_svg = f.read()

            # Generate comment content
            comment_file = os.path.join(self.temp_dir, "pr-comment.md")
            cmd = [
                "u",
                "diff",
                base_file,
                head_file,
                "--output",
                comment_file,
                "--format",
                "markdown",
                "--policy-check",
            ]
            subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)

            with open(comment_file, "r") as f:
                comment_content = f.read()

            # Create enhanced comment
            enhanced_comment = self.create_enhanced_comment(
                delta_data, comment_content, minimap_svg
            )

            # Post comment
            if not self.post_comment(enhanced_comment):
                return False

            # Create check run
            if not self.create_check_run(delta_data, head_sha):
                return False

            # Set commit status
            violations = delta_data.get("violations", [])
            policy_passed = len(violations) == 0
            if not self.set_commit_status(head_sha, policy_passed):
                return False

            print(f"Analysis complete. Policy check: {'PASSED' if policy_passed else 'FAILED'}")
            return True

        except Exception as e:
            print(f"Error in analysis pipeline: {e}")
            return False
        finally:
            # Cleanup
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Understand-First GitHub PR Commenter")
    parser.add_argument("--github-token", required=True, help="GitHub token")
    parser.add_argument("--repository", required=True, help="Repository (owner/repo)")
    parser.add_argument("--pr-number", type=int, required=True, help="PR number")
    parser.add_argument("--base-commit", help="Base commit SHA")
    parser.add_argument("--head-commit", help="Head commit SHA")
    parser.add_argument("--no-minimap", action="store_true", help="Skip mini-map generation")
    parser.add_argument("--no-artifacts", action="store_true", help="Skip artifact upload")

    args = parser.parse_args()

    config = CommenterConfig(
        github_token=args.github_token,
        repository=args.repository,
        pr_number=args.pr_number,
        base_commit=args.base_commit,
        head_commit=args.head_commit,
        include_minimap=not args.no_minimap,
        include_artifacts=not args.no_artifacts,
    )

    commenter = UnderstandFirstCommenter(config)
    success = commenter.run_analysis_pipeline()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
