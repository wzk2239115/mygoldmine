#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ui" / "data" / "report-quality.json"
MD = ROOT / "runs" / "report-quality.md"
CJK = re.compile(r"[\u4e00-\u9fff]")


def system_language():
    try:
        import json as _json

        value = str(
            _json.loads((ROOT / "config" / "system.json").read_text(encoding="utf-8")).get(
                "language"
            )
            or "zh"
        )
    except Exception:
        value = "zh"
    return value if value in {"zh", "en"} else "zh"


def text_value(value):
    if isinstance(value, list):
        return " ".join(filter(None, (text_value(item) for item in value)))
    if isinstance(value, dict):
        return text_value(
            value.get("idea")
            or value.get("steps")
            or value.get("note")
            or value.get("description")
            or ""
        )
    return value.strip() if isinstance(value, str) else ""


def evidence_value(value):
    """Require actual evidence content rather than a truthy container."""
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if (
            isinstance(item, str)
            and item.strip()
            or isinstance(item, dict)
            and (
                text_value(item.get("path") or item.get("file"))
                or text_value(item.get("description") or item.get("snippet"))
            )
        )
    ]


def schema_errors(report):
    if not isinstance(report, dict):
        return ["report must be an object"]
    keys = [key for key in ("findings", "vulnerabilities") if key in report]
    if not keys:
        return ["report must contain a findings or vulnerabilities array"]
    errors = []
    for key in keys:
        if not isinstance(report[key], list):
            errors.append(f"{key} must be an array")
        else:
            errors.extend(
                f"{key}[{index}] must be an object"
                for index, item in enumerate(report[key])
                if not isinstance(item, dict)
            )
    if len(keys) > 1 and report["findings"] != report["vulnerabilities"]:
        errors.append("findings and vulnerabilities conflict; supply one collection")
    return errors


def list_value(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def findings_of(report):
    if not isinstance(report, dict):
        return []
    if isinstance(report.get("findings"), list):
        return report["findings"]
    if isinstance(report.get("vulnerabilities"), list):
        return report["vulnerabilities"]
    return []


def quality_of(finding, language="zh"):
    finding = finding if isinstance(finding, dict) else {}
    evidence = evidence_value(finding.get("evidence"))
    verification = (
        finding.get("verification") if isinstance(finding.get("verification"), dict) else {}
    )
    values = {
        "title": text_value(finding.get("title")),
        "rootCause": text_value(
            finding.get("root_cause")
            or finding.get("rootCause")
            or finding.get("description")
            or finding.get("summary")
            or finding.get("type")
        ),
        "impact": text_value(
            finding.get("impact") or finding.get("effect") or finding.get("consequence")
        ),
        "reproduction": text_value(
            finding.get("reproduction_idea")
            or finding.get("reproduction")
            or finding.get("exploit")
            or finding.get("poc")
            or finding.get("poc_steps")
            or finding.get("test_plan")
            or finding.get("verification_idea")
            or verification.get("idea")
            or verification.get("steps")
            or verification.get("reproduction")
        ),
        "remediation": text_value(
            finding.get("remediation_items")
            or finding.get("remediation")
            or finding.get("fix")
            or finding.get("fixed_code")
            or finding.get("recommendation")
            or finding.get("remediation_note")
        ),
        "evidence": evidence,
    }
    missing = [field for field, value in values.items() if not value]
    title_language = (
        "zh"
        if CJK.search(values["title"])
        else ("en" if re.search(r"[A-Za-z]", values["title"]) else "unknown")
    )
    language_mismatch = language == "zh" and bool(values["title"]) and title_language != "zh"
    if language_mismatch:
        missing.append("titleLanguage")
    return {
        "ok": not missing,
        "score": round(((len(values) - len(missing)) / max(len(values), 1)) * 100),
        "missing": missing,
        "titleLanguage": title_language,
        "languageMismatch": language_mismatch,
    }


def latest_reports():
    by_project = defaultdict(list)
    for path in (ROOT / "runs").glob("*/*/audit-report.json"):
        if path.parent.name.startswith("."):
            continue
        by_project[path.parent.parent.name].append(path)
    return {
        project: max(paths, key=lambda item: item.parent.name)
        for project, paths in by_project.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fail", action="store_true", help="exit 1 when required fields are missing"
    )
    parser.add_argument(
        "--fail-language", action="store_true", help="exit 1 when zh titles are not localized"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    language = system_language()
    rows = []
    language_rows = []
    language_missing = 0
    invalid_reports = []
    totals = Counter()
    projects = Counter()
    missing = defaultdict(Counter)
    reports = latest_reports()
    for project, path in sorted(reports.items()):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid_reports.append(
                {"project": project, "report": str(path), "errors": [type(exc).__name__]}
            )
            continue
        errors = schema_errors(report)
        if errors:
            invalid_reports.append({"project": project, "report": str(path), "errors": errors})
        found = [item for item in findings_of(report) if isinstance(item, dict)]
        projects[project] = len(found)
        for finding in found:
            quality = quality_of(finding, language)
            totals["findings"] += 1
            if quality["ok"]:
                totals["ok"] += 1
            for field in quality["missing"]:
                missing[project][field] += 1
            if quality["languageMismatch"]:
                language_missing += 1
                language_rows.append(
                    {
                        "project": project,
                        "id": finding.get("id") or "",
                        "title": text_value(finding.get("title")),
                        "report": str(path),
                    }
                )
            if not quality["ok"]:
                rows.append(
                    {
                        "project": project,
                        "id": finding.get("id") or "",
                        "title": text_value(finding.get("title")),
                        "score": quality["score"],
                        "missing": quality["missing"],
                        "titleLanguage": quality["titleLanguage"],
                        "report": str(path),
                    }
                )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "reports": len(reports),
        "projects": dict(sorted(projects.items())),
        "totals": {
            "findings": totals["findings"],
            "complete": totals["ok"],
            "incomplete": totals["findings"] - totals["ok"],
        },
        "missing_by_project": {
            project: dict(sorted(counts.items())) for project, counts in sorted(missing.items())
        },
        "invalid_reports": invalid_reports,
        "language_mismatch": language_rows,
        "incomplete": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Report quality",
        "",
        f"- generated: {payload['generated_at']}",
        f"- reports: {len(reports)}",
        f"- invalid reports: {len(invalid_reports)}",
        f"- findings: {totals['findings']}",
        f"- complete: {totals['ok']}",
        f"- incomplete: {payload['totals']['incomplete']}",
        f"- language: {language}",
        f"- title language mismatches: {language_missing}",
        "",
        "## Missing by project",
        "",
        "| project | findings | missing fields |",
        "|---|---:|---|",
    ]
    for project, counts in sorted(missing.items()):
        detail = ", ".join(f"{field}={count}" for field, count in sorted(counts.items()))
        lines.append(f"| {project} | {projects[project]} | {detail} |")
    if language_rows:
        lines += [
            "",
            "## Title language mismatches",
            "",
            "| project | id | title |",
            "|---|---|---|",
        ]
        for row in language_rows:
            lines.append(f"| {row['project']} | {row['id']} | {row['title'][:120]} |")
    if invalid_reports:
        lines += ["", "## Invalid reports", ""]
        lines += [f"- {row['project']}: {'; '.join(row['errors'])}" for row in invalid_reports]
    lines += [
        "",
        "Required fields: title, rootCause, impact, reproduction, remediation, evidence.",
        "When system language is zh, `title` must contain Chinese; "
        "English originals belong in `title_en`.",
        "",
        "_This is a content completeness check, not a vulnerability conclusion._",
        "",
    ]
    MD.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "reports": len(reports),
                    "invalid_reports": len(invalid_reports),
                    "findings": totals["findings"],
                    "complete": totals["ok"],
                    "incomplete": payload["totals"]["incomplete"],
                    "language_mismatch": language_missing,
                    "output": str(OUT),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if (args.fail or args.fail_language) and invalid_reports:
        return 2
    if args.fail and payload["totals"]["incomplete"]:
        return 1
    if args.fail_language and language_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
