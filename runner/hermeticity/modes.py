"""Hermeticity modes, enforcement, and evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from runner.hashing import canonical_hash, sha256_text


class HermeticityMode(str, Enum):
    NO_NETWORK = "no_network"
    ALLOWLISTED_NETWORK = "allowlisted_network"
    RECORDED_RESPONSE = "recorded_response"
    PARTNER_LOCAL = "partner_local"
    SYNTHETIC_DEPENDENCY = "synthetic_dependency"


class EnforcementStatus(str, Enum):
    ENFORCED = "enforced"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"


@dataclass(frozen=True)
class HermeticityPolicy:
    mode: HermeticityMode
    allowlist_hosts: tuple[str, ...] = ()
    cassette_digest: Optional[str] = None
    partner_local_paths: tuple[str, ...] = ()
    synthetic_dependency_digests: tuple[str, ...] = ()

    def policy_digest(self) -> str:
        payload = {
            "mode": self.mode.value,
            "allowlist_hosts": list(self.allowlist_hosts),
            "cassette_digest": self.cassette_digest,
            "partner_local_paths": list(self.partner_local_paths),
            "synthetic_dependency_digests": list(self.synthetic_dependency_digests),
        }
        return canonical_hash(payload, enforce_number_policy=True)


@dataclass
class HermeticityEvidence:
    mode: HermeticityMode
    status: EnforcementStatus
    policy_digest: str
    probe_result: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "status": self.status.value,
            "policy_digest": self.policy_digest,
            "probe_result": self.probe_result,
            "message": self.message,
        }


class HermeticityError(RuntimeError):
    """Fail-closed hermeticity error before or during execution."""


def policy_from_profile_network(network: Any) -> HermeticityPolicy:
    mode = HermeticityMode(network.mode)
    return HermeticityPolicy(
        mode=mode,
        allowlist_hosts=tuple(network.allowlist_hosts or []),
        cassette_digest=network.cassette_digest,
        partner_local_paths=tuple(network.partner_local_paths or []),
        synthetic_dependency_digests=tuple(network.synthetic_dependency_digests or []),
    )


def host_allowed(host: str, policy: HermeticityPolicy) -> bool:
    if policy.mode == HermeticityMode.NO_NETWORK:
        return False
    if policy.mode == HermeticityMode.ALLOWLISTED_NETWORK:
        return host in policy.allowlist_hosts
    if policy.mode == HermeticityMode.RECORDED_RESPONSE:
        return False
    if policy.mode == HermeticityMode.PARTNER_LOCAL:
        return False
    if policy.mode == HermeticityMode.SYNTHETIC_DEPENDENCY:
        return False
    return False


def path_within_partner(path: str, policy: HermeticityPolicy) -> bool:
    if policy.mode != HermeticityMode.PARTNER_LOCAL:
        return False
    from pathlib import Path

    target = Path(path).resolve()
    for allowed in policy.partner_local_paths:
        root = Path(allowed).resolve()
        if target == root:
            return True
        try:
            target.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def evidence_digest(evidence: HermeticityEvidence) -> str:
    return sha256_text(
        f"{evidence.mode.value}|{evidence.status.value}|{evidence.policy_digest}"
    )


CapabilityResult = Literal["supported", "unsupported"]
