"""JavaScript coverage collection and reporting for Playwright UI tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class JSCoverageCollector:
    """Collects V8 JavaScript coverage and generates reports."""

    output_dir: Path = field(default_factory=lambda: Path("htmlcov/js"))
    coverage_entries: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Create output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_coverage(self, entries: list[dict[str, Any]]) -> None:
        """Add coverage entries, filtering to app JS files only."""
        filtered = [entry for entry in entries if "/static/js/metrics/" in entry.get("url", "")]
        self.coverage_entries.extend(filtered)

    def generate_reports(self) -> None:
        """Generate coverage reports from collected data."""
        if not self.coverage_entries:
            return

        raw_path = self.output_dir / "v8-coverage.json"
        with open(raw_path, "w") as f:
            json.dump(self.coverage_entries, f, indent=2)

        summary = self._generate_summary()
        summary_path = self.output_dir / "coverage-summary.txt"
        with open(summary_path, "w") as f:
            f.write(summary)

        html = self._generate_html_report()
        html_path = self.output_dir / "index.html"
        with open(html_path, "w") as f:
            f.write(html)

    def _get_file_stats(self) -> dict[str, dict[str, Any]]:
        """Analyze coverage entries and return per-file statistics."""
        file_stats: dict[str, dict[str, Any]] = {}

        for entry in self.coverage_entries:
            url = entry.get("url", "")
            parsed = urlparse(url)
            filename = Path(parsed.path).name

            if filename not in file_stats:
                file_stats[filename] = {
                    "url": url,
                    "functions": {},
                    "total": 0,
                    "covered": 0,
                }

            for func in entry.get("functions", []):
                func_name = func.get("functionName", "(anonymous)")
                ranges = func.get("ranges", [])
                is_covered = any(r.get("count", 0) > 0 for r in ranges)

                if func_name not in file_stats[filename]["functions"]:
                    file_stats[filename]["functions"][func_name] = is_covered
                    file_stats[filename]["total"] += 1
                    if is_covered:
                        file_stats[filename]["covered"] += 1
                elif is_covered and not file_stats[filename]["functions"][func_name]:
                    file_stats[filename]["functions"][func_name] = True
                    file_stats[filename]["covered"] += 1

        return file_stats

    def _generate_summary(self) -> str:
        """Generate text summary of coverage."""
        file_stats = self._get_file_stats()

        lines = [
            "JavaScript Coverage Summary",
            "=" * 50,
            f"Generated: {datetime.now(UTC).isoformat()}",
            "",
        ]

        total_functions = 0
        total_covered = 0

        for filename, stats in sorted(file_stats.items()):
            total = stats["total"]
            covered = stats["covered"]
            total_functions += total
            total_covered += covered
            pct = (covered / total * 100) if total > 0 else 0
            lines.append(f"{filename}: {covered}/{total} functions ({pct:.1f}%)")

        overall_pct = (total_covered / total_functions * 100) if total_functions > 0 else 0
        lines.extend([
            "",
            "-" * 50,
            f"Total: {total_covered}/{total_functions} functions ({overall_pct:.1f}%)",
        ])

        return "\n".join(lines)

    def _generate_html_report(self) -> str:
        """Generate HTML coverage report with inline CSS."""
        file_stats = self._get_file_stats()

        total_functions = sum(s["total"] for s in file_stats.values())
        total_covered = sum(s["covered"] for s in file_stats.values())
        overall_pct = (total_covered / total_functions * 100) if total_functions > 0 else 0

        file_rows = []
        for filename, stats in sorted(file_stats.items()):
            total = stats["total"]
            covered = stats["covered"]
            pct = (covered / total * 100) if total > 0 else 0
            color = "#4caf50" if pct >= 80 else "#ff9800" if pct >= 50 else "#f44336"

            func_items = []
            for func_name, is_covered in sorted(stats["functions"].items()):
                status = "&#10003;" if is_covered else "&#10007;"
                func_color = "#4caf50" if is_covered else "#f44336"
                func_items.append(f'<span style="color: {func_color}">{status} {func_name}</span>')

            file_rows.append(f"""
            <div class="file">
                <div class="file-header">
                    <span class="filename">{filename}</span>
                    <span class="coverage" style="color: {color}">{covered}/{total} ({pct:.1f}%)</span>
                </div>
                <div class="functions">{" ".join(func_items)}</div>
            </div>""")

        overall_color = "#4caf50" if overall_pct >= 80 else "#ff9800" if overall_pct >= 50 else "#f44336"
        timestamp = datetime.now(UTC).isoformat()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JavaScript Coverage Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #fff; border-bottom: 2px solid #4caf50; padding-bottom: 10px; }}
        h2 {{ color: #ccc; }}
        .summary {{
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .summary-stat {{
            font-size: 2em;
            font-weight: bold;
            color: {overall_color};
        }}
        .file {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        .file-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .filename {{ font-weight: bold; font-size: 1.1em; }}
        .coverage {{ font-family: monospace; }}
        .functions {{
            font-family: monospace;
            font-size: 0.9em;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>JavaScript Coverage Report</h1>
    <div class="summary">
        <div class="summary-stat">{overall_pct:.1f}%</div>
        <div>{total_covered} of {total_functions} functions covered</div>
        <div class="timestamp">Generated: {timestamp}</div>
    </div>
    <h2>Files</h2>
    {"".join(file_rows)}
</body>
</html>"""
