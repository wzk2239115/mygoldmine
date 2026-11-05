#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SCENARIO_SCHEMA_VERSION = 1
SUPPORTED_MODES = frozenset({"http", "cli", "library"})
DIRECT_MODES = frozenset({"cli", "library"})
HEX_256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SAFE_MODE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
QUALIFIED_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
BLOCKED_REQUIRED = {
    "schema_version",
    "status",
    "finding_id",
    "finding_sha256",
    "source",
    "mode",
    "attacked_surface",
    "reason",
    "checked_entries",
    "missing_capabilities",
    "evidence",
    "attempted",
    "next_conditions",
    "claims_dynamic_validation",
}
BLOCKED_KEYS = BLOCKED_REQUIRED | {"victim_image", "attacker_image"}
VERDICT_KEYS = {
    "verdict",
    "intended_vulnerability",
    "flag_provenance",
    "no_cheat",
    "environment_plausible",
    "reproducible",
    "minimal",
    "confidence",
    "reason",
    "concerns",
    "recommended_status",
}
APPROVAL_FIELDS = (
    "intended_vulnerability",
    "flag_provenance",
    "no_cheat",
    "environment_plausible",
    "reproducible",
    "minimal",
)


class ContractError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def finding_id(finding):
    value = finding.get("id") or finding.get("finding_id")
    if not isinstance(value, str) or not SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ContractError("blocked_invalid_finding", "finding id must be a safe path component")
    return value


def scenario_path(root, project, finding):
    if not SAFE_COMPONENT.fullmatch(project) or project in {".", ".."}:
        raise ContractError("blocked_invalid_project", "project must be a safe path component")
    finding = finding_id({"id": finding}) if not isinstance(finding, dict) else finding_id(finding)
    return Path(root) / "labs" / project / finding / "scenario.json"


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ContractError("blocked_scenario_invalid", f"{field} must be a non-empty string")
    return value.strip()


def _validate_launch(launch):
    if launch is None:
        return {"command": []}
    if isinstance(launch, str):
        return {"command": _required_string(launch, "launch")}
    if isinstance(launch, list) and all(isinstance(item, str) and item for item in launch):
        return {"command": list(launch)}
    if (
        isinstance(launch, dict)
        and set(launch) == {"command"}
        and isinstance(launch["command"], (str, list))
    ):
        return _validate_launch(launch["command"])
    raise ContractError(
        "blocked_scenario_invalid",
        "launch must be null, a command string, or a non-empty string argument list",
    )


def _validate_direct_launch(launch):
    entrypoint = None
    if isinstance(launch, dict):
        if set(launch) - {"command", "entrypoint"} or "command" not in launch:
            raise ContractError(
                "blocked_scenario_invalid",
                "cli/library launch must contain command and optional entrypoint",
            )
        entrypoint = launch.get("entrypoint")
        launch = launch["command"]
    if isinstance(launch, str):
        raise ContractError(
            "blocked_scenario_invalid",
            "cli/library launch.command must be an argument list, not a shell string",
        )
    if not isinstance(launch, list) or not launch:
        raise ContractError(
            "blocked_scenario_invalid",
            "cli/library launch.command must be a non-empty string argument list",
        )
    if any(not isinstance(item, str) or not item for item in launch):
        raise ContractError(
            "blocked_scenario_invalid",
            "cli/library launch.command must contain only non-empty strings",
        )
    normalized = {"command": list(launch)}
    if entrypoint is not None:
        if not isinstance(entrypoint, str) or not entrypoint.strip() or any(ch.isspace() for ch in entrypoint.strip()):
            raise ContractError(
                "blocked_scenario_invalid",
                "launch.entrypoint must be a non-empty path or program without whitespace",
            )
        normalized["entrypoint"] = entrypoint.strip()
    return normalized


def _safe_relative_path(value, field, suffix=None):
    text = _required_string(value, field)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or text in {".", ".."}:
        raise ContractError("blocked_scenario_invalid", f"{field} must stay inside the lab directory")
    if suffix and path.suffix != suffix:
        raise ContractError("blocked_scenario_invalid", f"{field} must end with {suffix}")
    return text


def _validate_input(value):
    if not isinstance(value, dict) or set(value) - {"path"}:
        raise ContractError("blocked_scenario_invalid", "input must be an object containing only path")
    path = _required_string(value.get("path"), "input.path")
    if path != "/input":
        raise ContractError("blocked_scenario_invalid", "input.path must be /input")
    return {"path": path}


def _validate_entry(value):
    if not isinstance(value, dict) or set(value) != {"module", "qualname", "source_ref"}:
        raise ContractError(
            "blocked_scenario_invalid",
            "entry must contain exactly module, qualname and source_ref",
        )
    module = _required_string(value["module"], "entry.module")
    qualname = _required_string(value["qualname"], "entry.qualname")
    source_ref = _required_string(value["source_ref"], "entry.source_ref")
    if not MODULE_NAME.fullmatch(module):
        raise ContractError("blocked_scenario_invalid", "entry.module must be a dotted Python module")
    if not QUALIFIED_NAME.fullmatch(qualname):
        raise ContractError("blocked_scenario_invalid", "entry.qualname must be a dotted Python name")
    return {"module": module, "qualname": qualname, "source_ref": source_ref}


def _validate_negative_control(value):
    if value is None:
        return {"kind": "empty_input"}
    if not isinstance(value, dict) or set(value) - {"kind", "fixture"}:
        raise ContractError("blocked_scenario_invalid", "negative_control must be an object")
    kind = value.get("kind", "empty_input")
    if kind == "empty_input":
        if "fixture" in value:
            raise ContractError("blocked_scenario_invalid", "empty_input cannot declare a fixture")
        return {"kind": "empty_input"}
    if kind == "benign_fixture":
        return {
            "kind": kind,
            "fixture": _safe_relative_path(value.get("fixture"), "negative_control.fixture"),
        }
    raise ContractError(
        "blocked_scenario_invalid",
        "negative_control.kind must be empty_input or benign_fixture",
    )


def _validate_source(source, expected_source=None):
    if not isinstance(source, dict) or len([key for key in ("commit", "content_sha256") if key in source]) != 1:
        raise ContractError(
            "blocked_scenario_invalid",
            "source must bind exactly one of commit or content_sha256",
        )
    if set(source) - {"commit", "content_sha256"}:
        raise ContractError("blocked_scenario_invalid", "source contains unsupported binding fields")
    if "commit" in source:
        commit = source["commit"]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
            raise ContractError("blocked_scenario_invalid", "source.commit must be a hexadecimal revision")
    elif not isinstance(source["content_sha256"], str) or not HEX_256.fullmatch(source["content_sha256"]):
        raise ContractError("blocked_scenario_invalid", "source.content_sha256 must be a lowercase SHA-256")
    if expected_source is not None and source != expected_source:
        raise ContractError("blocked_scenario_stale", "scenario source binding does not match this build")
    return dict(source)


def _validate_http_fields(scenario):
    target_url = _required_string(scenario["target_url"], "target_url").rstrip("/")
    parsed = urlsplit(target_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "victim" or parsed.username or parsed.password:
        raise ContractError(
            "blocked_scenario_invalid",
            "target_url must use http(s) and the internal victim hostname",
        )
    health = scenario["health"]
    if not isinstance(health, dict) or set(health) - {"path", "attempts", "interval_seconds", "timeout_seconds"}:
        raise ContractError("blocked_scenario_invalid", "health must be an object with a path and optional timing")
    health_path = _required_string(health.get("path"), "health.path")
    if not health_path.startswith("/") or health_path == "/flag" or health_path.startswith("/flag?"):
        raise ContractError("blocked_scenario_invalid", "health.path must be a non-flag absolute path")
    normalized_health = {"path": health_path}
    for field, default, minimum in (
        ("attempts", 30, 1),
        ("interval_seconds", 0.5, 0),
        ("timeout_seconds", 2, 1),
    ):
        value = health.get(field, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
            raise ContractError("blocked_scenario_invalid", f"health.{field} has an invalid value")
        normalized_health[field] = value
    return target_url, normalized_health, health_path


def _reject_mounts(scenario):
    for key in ("attacker_mounts", "victim_mounts", "host_mounts", "volumes"):
        if key in scenario and scenario[key] not in (None, []):
            raise ContractError(
                "blocked_scenario_invalid",
                f"{key} is not supported; the harness alone may mount the victim flag",
            )
    mounts = scenario.get("mounts")
    if mounts is not None:
        if not isinstance(mounts, dict):
            raise ContractError("blocked_scenario_invalid", "mounts must be an object")
        if set(mounts) - {"attacker", "victim", "host"} or any(
            mounts.get(role) not in (None, []) for role in ("attacker", "victim", "host")
        ):
            raise ContractError(
                "blocked_scenario_invalid",
                "scenario mounts are forbidden; only the harness-managed victim flag mount is allowed",
            )


def validate_scenario(
    scenario,
    *,
    expected_finding_id,
    expected_finding_sha256,
    expected_source=None,
):
    if not isinstance(scenario, dict):
        raise ContractError("blocked_scenario_invalid", "scenario must be a JSON object")
    required = {
        "schema_version",
        "finding_id",
        "finding_sha256",
        "source",
        "mode",
        "victim_image",
        "attacker_image",
        "launch",
    }
    missing = sorted(required - set(scenario))
    if missing:
        raise ContractError("blocked_scenario_invalid", f"missing scenario fields: {', '.join(missing)}")
    if type(scenario["schema_version"]) is not int or scenario["schema_version"] != SCENARIO_SCHEMA_VERSION:
        raise ContractError("blocked_scenario_invalid", "unsupported scenario schema_version")
    if scenario["finding_id"] != expected_finding_id:
        raise ContractError(
            "blocked_scenario_mismatch",
            f"scenario finding {scenario['finding_id']!r} does not match {expected_finding_id!r}",
        )
    finding_hash = scenario["finding_sha256"]
    if not isinstance(finding_hash, str) or not HEX_256.fullmatch(finding_hash):
        raise ContractError("blocked_scenario_invalid", "finding_sha256 must be a lowercase SHA-256")
    if finding_hash != expected_finding_sha256:
        raise ContractError("blocked_scenario_stale", "scenario was built for different finding content")
    source = _validate_source(scenario["source"], expected_source)
    mode = scenario["mode"]
    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        raise ContractError(
            "blocked_unsupported_mode",
            f"mode {mode!r} has no deterministic executable adapter; supported: {', '.join(sorted(SUPPORTED_MODES))}",
        )
    for field in ("victim_image", "attacker_image"):
        image = _required_string(scenario[field], field)
        if any(character.isspace() for character in image):
            raise ContractError("blocked_scenario_invalid", f"{field} cannot contain whitespace")
    _reject_mounts(scenario)
    normalized = dict(scenario)
    normalized["source"] = source
    if mode == "http":
        for field in ("target_url", "health"):
            if field not in scenario:
                raise ContractError("blocked_scenario_invalid", f"http scenario requires {field}")
        target_url, normalized_health, health_path = _validate_http_fields(scenario)
        normalized.update({
            "target_url": target_url,
            "health": normalized_health,
            "health_path": health_path,
            "launch": _validate_launch(scenario["launch"]),
        })
        return normalized
    for field in ("target_url", "health"):
        if field in scenario:
            raise ContractError(
                "blocked_scenario_invalid",
                f"{mode} scenario cannot declare {field}",
            )
    if "input" not in scenario:
        raise ContractError("blocked_scenario_invalid", f"{mode} scenario requires input")
    normalized["input"] = _validate_input(scenario["input"])
    normalized["launch"] = _validate_direct_launch(scenario["launch"])
    normalized["negative_control"] = _validate_negative_control(scenario.get("negative_control"))
    if mode == "library":
        if "driver" not in scenario or "entry" not in scenario:
            raise ContractError("blocked_scenario_invalid", "library scenario requires driver and entry")
        normalized["driver"] = _safe_relative_path(scenario["driver"], "driver", suffix=".py")
        normalized["entry"] = _validate_entry(scenario["entry"])
    else:
        for field in ("driver", "entry"):
            if field in scenario:
                raise ContractError(
                    "blocked_scenario_invalid",
                    f"cli scenario cannot declare {field}",
                )
    return normalized


def resolve_scenario(root, project, finding, finding_bytes):
    identifier = finding_id(finding)
    expected_hash = sha256_bytes(finding_bytes)
    preferred = scenario_path(root, project, identifier)
    legacy = Path(root) / "labs" / project / "scenario.json"
    path = preferred if preferred.exists() else legacy if legacy.exists() else None
    if path is None:
        raise ContractError("blocked_no_lab", f"no scenario for {project}/{identifier}")
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError("blocked_scenario_invalid", f"cannot read scenario: {exc}") from exc
    if path == legacy and scenario.get("legacy_compatible") is not True:
        raise ContractError(
            "blocked_legacy_scenario",
            "project-level scenario requires explicit legacy_compatible: true and current content binding",
        )
    return path, validate_scenario(
        scenario,
        expected_finding_id=identifier,
        expected_finding_sha256=expected_hash,
    )


def _string_list(value, field, *, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError("blocked_delivery_invalid", f"{field} must be a list of non-empty strings")
    if nonempty and not value:
        raise ContractError("blocked_delivery_invalid", f"{field} must not be empty")
    return [item.strip() for item in value]


def validate_blocked(
    document,
    *,
    expected_finding_id=None,
    expected_finding_sha256=None,
    expected_source=None,
):
    if not isinstance(document, dict):
        raise ContractError("blocked_delivery_invalid", "blocked delivery must be a JSON object")
    missing = sorted(BLOCKED_REQUIRED - set(document))
    extra = sorted(set(document) - BLOCKED_KEYS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unknown: {', '.join(extra)}")
        raise ContractError("blocked_delivery_invalid", "; ".join(details))
    if type(document["schema_version"]) is not int or document["schema_version"] != SCENARIO_SCHEMA_VERSION:
        raise ContractError("blocked_delivery_invalid", "unsupported blocked schema_version")
    if document["status"] != "blocked":
        raise ContractError("blocked_delivery_invalid", "status must be blocked")
    if expected_finding_id is not None and document["finding_id"] != expected_finding_id:
        raise ContractError(
            "blocked_finding_mismatch",
            f"blocked finding {document['finding_id']!r} does not match {expected_finding_id!r}",
        )
    if not isinstance(document["finding_id"], str) or not SAFE_COMPONENT.fullmatch(document["finding_id"]):
        raise ContractError("blocked_delivery_invalid", "finding_id must be a safe path component")
    if not isinstance(document["finding_sha256"], str) or not HEX_256.fullmatch(document["finding_sha256"]):
        raise ContractError("blocked_delivery_invalid", "finding_sha256 must be a lowercase SHA-256")
    if expected_finding_sha256 is not None and document["finding_sha256"] != expected_finding_sha256:
        raise ContractError("blocked_scenario_stale", "blocked delivery was built for different finding content")
    document["source"] = _validate_source(document["source"], expected_source)
    if not isinstance(document["mode"], str) or not SAFE_MODE.fullmatch(document["mode"]):
        raise ContractError("blocked_delivery_invalid", "mode must be a short lowercase identifier")
    for field in ("victim_image", "attacker_image"):
        if field in document:
            image = _required_string(document[field], field)
            if any(character.isspace() for character in image):
                raise ContractError("blocked_delivery_invalid", f"{field} cannot contain whitespace")
    for field in ("attacked_surface", "reason"):
        if not isinstance(document[field], str) or len(document[field].strip()) < 4:
            raise ContractError("blocked_delivery_invalid", f"{field} must be a concrete non-empty description")
        document[field] = document[field].strip()
    _string_list(document["checked_entries"], "checked_entries", nonempty=True)
    _string_list(document["missing_capabilities"], "missing_capabilities", nonempty=True)
    _string_list(document["next_conditions"], "next_conditions", nonempty=True)
    _string_list(document["attempted"], "attempted")
    evidence = _string_list(document["evidence"], "evidence", nonempty=True)
    for name in evidence:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name in {".", ".."}:
            raise ContractError("blocked_delivery_invalid", "evidence paths must stay inside the lab directory")
    if document["claims_dynamic_validation"] is not False:
        raise ContractError(
            "blocked_delivery_invalid",
            "a blocked delivery cannot claim dynamic validation",
        )
    return document


def validate_verdict(verdict):
    if not isinstance(verdict, dict):
        raise ContractError("judge_schema_invalid", "verdict must be a JSON object")
    missing = sorted(VERDICT_KEYS - set(verdict))
    extra = sorted(set(verdict) - VERDICT_KEYS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unknown: {', '.join(extra)}")
        raise ContractError("judge_schema_invalid", "; ".join(details))
    if not isinstance(verdict["verdict"], str) or verdict["verdict"] not in {"approved", "rejected", "needs_review"}:
        raise ContractError("judge_schema_invalid", "invalid verdict value")
    for field in APPROVAL_FIELDS:
        if type(verdict[field]) is not bool:
            raise ContractError("judge_schema_invalid", f"{field} must be a JSON boolean")
    if verdict["verdict"] == "approved" and not all(verdict[field] for field in APPROVAL_FIELDS):
        raise ContractError("judge_schema_invalid", "approved requires every approval boolean to be true")
    if not isinstance(verdict["confidence"], str) or verdict["confidence"] not in {"high", "medium", "low"}:
        raise ContractError("judge_schema_invalid", "invalid confidence")
    if not isinstance(verdict["reason"], str) or not verdict["reason"].strip():
        raise ContractError("judge_schema_invalid", "reason must be a non-empty string")
    if not isinstance(verdict["concerns"], list) or not all(isinstance(item, str) for item in verdict["concerns"]):
        raise ContractError("judge_schema_invalid", "concerns must be a list of strings")
    if not isinstance(verdict["recommended_status"], str) or verdict["recommended_status"] not in {
        "runtime-validated", "needs-rerun", "rejected"
    }:
        raise ContractError("judge_schema_invalid", "invalid recommended_status")
    if verdict["verdict"] == "approved" and verdict["recommended_status"] != "runtime-validated":
        raise ContractError("judge_schema_invalid", "approved must recommend runtime-validated")
    return verdict


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError("provenance_invalid", f"cannot read {Path(path).name}: {exc}") from exc


def recompute_flag_provenance(run_dir, document):
    run_dir = Path(run_dir)
    if not isinstance(document, dict) or not isinstance(document.get("result"), dict):
        raise ContractError("provenance_invalid", "result document is malformed")
    result = document["result"]
    if result.get("captured") is not True:
        raise ContractError("provenance_invalid", "run does not contain a captured result")
    provenance = result.get("flag_provenance")
    if not isinstance(provenance, dict):
        raise ContractError("provenance_invalid", "missing deterministic flag provenance")
    required = {"source", "event_id", "capture_event_id", "output_sha256", "flag_sha256"}
    if set(provenance) != required or provenance["source"] != "tool_output":
        raise ContractError("provenance_invalid", "provenance must identify exactly one real tool output")
    for field in ("event_id", "capture_event_id"):
        if not isinstance(provenance[field], str) or not provenance[field]:
            raise ContractError("provenance_invalid", f"invalid {field}")
    for field in ("output_sha256", "flag_sha256"):
        if not isinstance(provenance[field], str) or not HEX_256.fullmatch(provenance[field]):
            raise ContractError("provenance_invalid", f"invalid {field}")
    if document.get("flag_sha256") != provenance["flag_sha256"]:
        raise ContractError("provenance_invalid", "result and provenance flag hashes differ")
    try:
        flag = (run_dir / "flag.txt").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ContractError("provenance_invalid", f"cannot read flag: {exc}") from exc
    if sha256_text(flag) != provenance["flag_sha256"] or result.get("answer") != flag:
        raise ContractError("provenance_invalid", "captured answer does not match the run flag")
    try:
        records = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        raise ContractError("provenance_invalid", f"cannot read trace: {exc}") from exc
    tool_events = [
        record for record in records
        if isinstance(record, dict)
        and record.get("kind") == "tool_result"
        and record.get("event_id") == provenance["event_id"]
    ]
    if len(tool_events) != 1 or not isinstance(tool_events[0].get("output"), str):
        raise ContractError("provenance_invalid", "provenance does not reference exactly one tool result")
    event = tool_events[0]
    if event.get("output_sha256") != provenance["output_sha256"] or sha256_text(event["output"]) != provenance["output_sha256"]:
        raise ContractError("provenance_invalid", "tool output hash does not match the trace")
    if flag not in event["output"]:
        raise ContractError("provenance_invalid", "referenced real tool output does not contain the flag")
    capture_events = [
        record for record in records
        if isinstance(record, dict)
        and record.get("kind") == "flag_capture"
        and record.get("event_id") == provenance["capture_event_id"]
    ]
    if len(capture_events) != 1:
        raise ContractError("provenance_invalid", "missing or ambiguous flag capture event")
    capture = capture_events[0]
    if any(capture.get(field) != provenance[field] for field in ("output_sha256", "flag_sha256")) or capture.get("tool_event_id") != provenance["event_id"]:
        raise ContractError("provenance_invalid", "flag capture event does not match its tool output")
    return {
        "event_id": provenance["event_id"],
        "capture_event_id": provenance["capture_event_id"],
        "output_sha256": provenance["output_sha256"],
        "flag_sha256": provenance["flag_sha256"],
        "source": "tool_output",
        "verified": True,
    }


def classify_agent_failure(returncode, result=None, timed_out=False):
    if timed_out:
        return "agent_timeout"
    nested = result.get("result", {}) if isinstance(result, dict) else {}
    status = nested.get("status") if isinstance(nested, dict) else None
    if status in {
        "model_timeout", "lab_unhealthy", "blocked_scenario_invalid",
        "not_captured", "lab_error", "agent_error",
    }:
        return status
    return {
        2: "not_captured",
        4: "model_timeout",
        5: "lab_unhealthy",
    }.get(returncode, "agent_error")
