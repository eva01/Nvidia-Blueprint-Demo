# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Sovereign AI policy metadata for the school facility demo."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FacilitySovereigntyPolicy:
    """Printable policy state for local demo governance controls."""

    mode: str = "local-demo"
    data_residency_region: str = "local-dev"
    storage_backend: str = "sqlite-local"
    cloud_nim_allowed: bool = True
    pii_redaction_enabled: bool = False
    audit_log_enabled: bool = True

    def to_dict(self, *, db_path: Path | None = None) -> dict[str, object]:
        """Return a secret-safe status payload."""
        payload: dict[str, object] = asdict(self)
        if db_path is not None:
            payload["database_path"] = str(db_path)
        return payload


def load_facility_sovereignty_policy(
    env: Mapping[str, str] | None = None,
) -> FacilitySovereigntyPolicy:
    """Load sovereign demo policy from environment-style values."""
    values = env or os.environ
    return FacilitySovereigntyPolicy(
        mode=values.get("SOVEREIGN_MODE", "local-demo").strip() or "local-demo",
        data_residency_region=values.get("DATA_RESIDENCY_REGION", "local-dev").strip() or "local-dev",
        cloud_nim_allowed=_as_bool(values.get("ALLOW_CLOUD_NIM", "true")),
        pii_redaction_enabled=_as_bool(values.get("PII_REDACTION_ENABLED", "false")),
        audit_log_enabled=_as_bool(values.get("AUDIT_LOG_ENABLED", "true")),
    )


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
