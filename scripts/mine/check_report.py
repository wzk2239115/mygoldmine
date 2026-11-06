#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import report_quality  # noqa: E402 - repository-local script import
from delivery_contract import report_project  # noqa: E402


def check_report(path, language=None, expected_project=None):
    path = Path(path)
    errors = []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        errors = report_quality.schema_errors(report)
    except (OSError, UnicodeError, ValueError) as exc:
        report = {}
        errors = [f"cannot read report: {type(exc).__name__}"]
    if expected_project is None:
        try:
            expected_project = path.resolve().relative_to(ROOT / "runs").parts[0]
        except (ValueError, IndexError):
            expected_project = None
    if expected_project and isinstance(report, dict):
        try:
            report_project(report, expected_project)
        except ValueError as exc:
            errors.append(str(exc))
    language = language or report_quality.system_language()
    findings = report_quality.findings_of(report)
    missing = Counter()
    incomplete = []
    language_mismatch = 0
    for finding in findings:
        finding = finding if isinstance(finding, dict) else {}
        quality = report_quality.quality_of(finding, language)
        for field in quality["missing"]:
            missing[field] += 1
        if quality["languageMismatch"]:
            language_mismatch += 1
        if not quality["ok"]:
            incomplete.append(
                {
                    "id": finding.get("id") or "",
                    "title": report_quality.text_value(finding.get("title"))[:160],
                    "score": quality["score"],
                    "missing": quality["missing"],
                    "titleLanguage": quality["titleLanguage"],
                }
            )
    return {
        "report": str(path),
        "valid": not errors,
        "errors": errors,
        "language": language,
        "findings": len(findings),
        "complete": len(findings) - len(incomplete),
        "incomplete": len(incomplete),
        "language_mismatch": language_mismatch,
        "missing": dict(sorted(missing.items())),
        "findings_incomplete": incomplete,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--project", default=None)
    parser.add_argument("--fail-missing", action="store_true")
    parser.add_argument("--fail-language", action="store_true")
    args = parser.parse_args()
    result = check_report(args.report, expected_project=args.project)
    output = Path(args.output) if args.output else Path(args.report).parent / "report-quality.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "report",
                    "valid",
                    "errors",
                    "language",
                    "findings",
                    "complete",
                    "incomplete",
                    "language_mismatch",
                    "missing",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not result["valid"]:
        return 2
    if args.fail_missing and result["incomplete"]:
        return 1
    if args.fail_language and result["language_mismatch"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
