#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Validate the cloud NIM configuration for the school facility voice demo."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.facility_sovereignty import load_facility_sovereignty_policy  # noqa: E402

EXPECTED_VALUES = {
    "TRANSPORT": "WEBRTC",
    "SYSTEM_PROMPT_SELECTOR": "nemotron-3-nano/school_facility_support",
    "ASR_SERVER_URL": "grpc.nvcf.nvidia.com:443",
    "TTS_SERVER_URL": "grpc.nvcf.nvidia.com:443",
    "NVIDIA_LLM_URL": "https://integrate.api.nvidia.com/v1",
}
DEFAULT_ENV_FILE = Path(".env")
DEFAULT_PROMPT_FILE = Path("config/prompt.yaml")
DEFAULT_DB_PATH = Path("data/facility_tickets.db")
FUNCTIONS_URL = "https://api.nvcf.nvidia.com/v2/nvcf/functions?visibility=public,authorized"


class ConfigError(RuntimeError):
    """Raised when cloud NIM configuration cannot be loaded."""


@dataclass
class ValidationResult:
    """Collected validation output safe to print."""

    errors: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    db_parent_created: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


def load_env_file(path: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Load dotenv-style values, with explicit environment values taking precedence."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if parsed is not None:
                key, value = parsed
                env[key] = value

    for key, value in (environ or os.environ).items():
        if value != "":
            env[key] = value
    return env


def validate_cloud_nim_config(
    env: Mapping[str, str],
    *,
    repo_root: Path | None = None,
) -> ValidationResult:
    """Validate local cloud NIM demo settings without exposing secrets."""
    root = (repo_root or Path.cwd()).resolve()
    result = ValidationResult()

    api_key = env.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        result.errors.append("NVIDIA_API_KEY is required in the shell environment for cloud NIM.")
    else:
        result.checks.append(f"NVIDIA_API_KEY is set: {mask_secret(api_key)}")

    for key, expected in EXPECTED_VALUES.items():
        actual = env.get(key, "").strip()
        if actual != expected:
            result.errors.append(f"{key} must be {expected!r}, got {actual!r}.")
        else:
            result.checks.append(f"{key} matches cloud demo setting.")

    policy = load_facility_sovereignty_policy(env)
    result.checks.append(f"SOVEREIGN_MODE is {policy.mode}.")
    result.checks.append(f"DATA_RESIDENCY_REGION is {policy.data_residency_region}.")
    result.checks.append(f"PII_REDACTION_ENABLED is {str(policy.pii_redaction_enabled).lower()}.")
    result.checks.append(f"AUDIT_LOG_ENABLED is {str(policy.audit_log_enabled).lower()}.")
    if _uses_cloud_nim(env) and not policy.cloud_nim_allowed:
        result.errors.append("ALLOW_CLOUD_NIM must be true when using hosted NVIDIA cloud NIM endpoints.")
    else:
        result.checks.append(f"ALLOW_CLOUD_NIM is {str(policy.cloud_nim_allowed).lower()}.")

    prompt_file = _resolve_path(env.get("PROMPT_FILE_PATH", str(DEFAULT_PROMPT_FILE)), root)
    prompt_selector = env.get("SYSTEM_PROMPT_SELECTOR", EXPECTED_VALUES["SYSTEM_PROMPT_SELECTOR"])
    if not prompt_file.exists():
        result.errors.append(f"PROMPT_FILE_PATH does not exist: {prompt_file}")
    elif not _prompt_selector_exists(prompt_file, prompt_selector):
        result.errors.append(f"Prompt selector {prompt_selector!r} was not found in {prompt_file}.")
    else:
        result.checks.append(f"prompt selector {prompt_selector} exists in {prompt_file}.")

    db_path = _resolve_path(env.get("FACILITY_TICKETS_DB_PATH", str(DEFAULT_DB_PATH)), root)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = db_path.parent / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        result.db_parent_created = True
        result.checks.append(f"FACILITY_TICKETS_DB_PATH parent is writable: {db_path.parent}")
    except OSError as exc:
        result.errors.append(f"FACILITY_TICKETS_DB_PATH parent is not writable: {db_path.parent}: {exc}")

    return result


def mask_secret(value: str) -> str:
    """Return a printable marker for a secret without exposing the full value."""
    if not value:
        return "<unset>"
    if len(value) < 12:
        return "<set>"
    return f"{value[:5]}...{value[-4:]}"


def filter_active_functions(payload: Mapping[str, object], patterns: Iterable[str]) -> list[tuple[str, str]]:
    """Return active NVCF function IDs and names matching any pattern."""
    lowered_patterns = [pattern.lower() for pattern in patterns]
    matches: list[tuple[str, str]] = []
    functions = payload.get("functions", [])
    if not isinstance(functions, list):
        return matches

    for item in functions:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        function_id = str(item.get("id", ""))
        status = str(item.get("status", ""))
        if status != "ACTIVE":
            continue
        if any(pattern in name.lower() for pattern in lowered_patterns):
            matches.append((function_id, name))
    return matches


def fetch_nvcf_functions(api_key: str) -> dict[str, object]:
    """Fetch visible NVCF functions using a bearer token."""
    request = urllib.request.Request(
        FUNCTIONS_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate cloud NIM school facility demo settings.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Path to dotenv file.")
    parser.add_argument(
        "--resolve-functions",
        action="store_true",
        help="Also query NVCF for active ASR/TTS functions. Requires network and NVIDIA_API_KEY.",
    )
    args = parser.parse_args(argv)

    env = load_env_file(args.env_file)
    result = validate_cloud_nim_config(env)

    for check in result.checks:
        print(f"OK: {check}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if not result.ok:
        return 1

    if args.resolve_functions:
        try:
            payload = fetch_nvcf_functions(env["NVIDIA_API_KEY"])
        except Exception as exc:
            print(f"ERROR: Could not resolve NVCF functions: {exc}", file=sys.stderr)
            return 2

        matches = filter_active_functions(payload, ["parakeet", "nemotron-asr", "magpie", "tts"])
        if not matches:
            print("WARNING: No active ASR/TTS NVCF functions matched the expected names.")
        else:
            print("Active ASR/TTS NVCF functions:")
            for function_id, name in matches:
                print(f"- {name}: {function_id}")

    return 0


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip("'\"")
    if not key:
        return None
    return key, value


def _resolve_path(raw_path: str, repo_root: Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _prompt_selector_exists(prompt_file: Path, selector: str) -> bool:
    if "/" not in selector:
        return False
    model, prompt_name = selector.split("/", 1)
    text = prompt_file.read_text(encoding="utf-8")
    model_re = re.compile(rf"^{re.escape(model)}:\s*(?:&\S+)?\s*$", re.MULTILINE)
    model_match = model_re.search(text)
    if model_match is None:
        return False

    next_top_level = re.search(r"^[A-Za-z0-9_.-]+:\s*(?:&\S+)?\s*$", text[model_match.end() :], re.MULTILINE)
    section_end = model_match.end() + next_top_level.start() if next_top_level else len(text)
    section = text[model_match.end() : section_end]
    prompt_re = re.compile(rf"^\s+{re.escape(prompt_name)}:\s*$", re.MULTILINE)
    return prompt_re.search(section) is not None


def _uses_cloud_nim(env: Mapping[str, str]) -> bool:
    values = [
        env.get("ASR_SERVER_URL", ""),
        env.get("TTS_SERVER_URL", ""),
        env.get("NVIDIA_LLM_URL", ""),
    ]
    return any("nvcf.nvidia.com" in value.lower() or "integrate.api.nvidia.com" in value.lower() for value in values)


if __name__ == "__main__":
    raise SystemExit(main())
