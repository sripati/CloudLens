"""Per-cloud data mode (mock / live) and the Live connections entered on the Cloud Accounts screen.

Each environment of a cloud has its own connection to its own cloud account, and all of that account's
cost and resources belong to that environment. Everything is stored in the database, never in `.env`.
Secrets are encrypted and never returned by the API. A connection can only be saved, and a cloud only
switched to live, after that exact config has passed a connection test.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import CredentialsUnreadable, decrypt_secrets, encrypt_secrets, fingerprint
from app.models import CloudAccount, CloudConnection

PROVIDERS = ("aws", "azure", "gcp")
ENVIRONMENTS = ("production", "staging", "development")
GUID = "^[0-9a-fA-F-]{36}$"
AWS_REGION = r"[a-z]{2}(-[a-z]+)+-\d+"

FIELDS: Dict[str, List[Dict[str, Any]]] = {
    "aws": [
        {"name": "auth_method", "label": "Authentication", "type": "select", "required": True, "default": "access_keys", "options": [
            {"value": "access_keys", "label": "IAM user access keys"},
            {"value": "default_chain", "label": "EC2 instance role (no keys stored)"},
        ], "help": "Use the instance role when CloudLens runs on EC2, so no keys are stored."},
        {"name": "access_key_id", "label": "Access key ID", "type": "text", "required": True, "pattern": "^[A-Z0-9]{16,128}$",
         "show_when": {"auth_method": "access_keys"}, "placeholder": "AKIA..."},
        {"name": "secret_access_key", "label": "Secret access key", "type": "secret", "required": True, "show_when": {"auth_method": "access_keys"}},
        {"name": "session_token", "label": "Session token", "type": "secret", "required": False, "show_when": {"auth_method": "access_keys"},
         "help": "Only for temporary credentials (keys starting with ASIA)."},
        {"name": "regions", "label": "Regions to scan", "type": "text", "required": True, "pattern": f"^{AWS_REGION}(\\s*,\\s*{AWS_REGION})*$",
         "placeholder": "ap-south-1, us-east-1", "help": "Comma separated. EC2, RDS and CloudWatch are read from these regions."},
        {"name": "cost_explorer_region", "label": "Cost Explorer region", "type": "text", "required": True, "default": "us-east-1", "pattern": f"^{AWS_REGION}$",
         "help": "The Cost Explorer endpoint is global and lives in us-east-1."},
    ],
    "azure": [
        {"name": "tenant_id", "label": "Tenant (directory) ID", "type": "text", "required": True, "pattern": GUID},
        {"name": "client_id", "label": "Client (application) ID", "type": "text", "required": True, "pattern": GUID},
        {"name": "client_secret", "label": "Client secret", "type": "secret", "required": True},
        {"name": "subscription_id", "label": "Subscription ID", "type": "text", "required": True, "pattern": GUID},
    ],
    "gcp": [
        {"name": "service_account_json", "label": "Service account key (JSON)", "type": "secret_text", "required": True,
         "help": "Paste the key file content or choose the file."},
        {"name": "project_id", "label": "Project ID", "type": "text", "required": True},
        # interpolated into the BigQuery FROM clause, so the pattern must keep rejecting quotes and backticks
        {"name": "billing_export_table", "label": "Billing export table", "type": "text", "required": True,
         "pattern": r"^[A-Za-z0-9_:.-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_$-]+$",
         "placeholder": "my-project.billing_export.gcp_billing_export_v1_0123AB_CDEF45_6789GH",
         "help": "BigQuery table of the standard usage cost export (project.dataset.table)."},
    ],
}

GUIDES: Dict[str, Dict[str, Any]] = {
    "aws": {
        "prerequisites": [
            "Enable Cost Explorer in the AWS Billing console (first activation can take up to 24 hours).",
            "Attach deploy/aws/iam-policy.json to the IAM user or role.",
            "Use a separate AWS account for each environment. All of the account's own cost is shown under the environment you choose.",
        ],
        "cost_note": "Each test makes one Cost Explorer request, which AWS bills at $0.01.",
    },
    "azure": {
        "prerequisites": [
            "Register an app (service principal) in Microsoft Entra ID and create a client secret.",
            "Grant it Cost Management Reader, Monitoring Reader and Reader on the subscription.",
            "Use a separate subscription for each environment. All of its cost is shown under the environment you choose.",
        ],
        "cost_note": "Testing uses the Cost Management and Resource Manager read APIs, which have no per-request charge.",
    },
    "gcp": {
        "prerequisites": [
            "Turn on Cloud Billing export to BigQuery (standard usage cost). Data starts from the day it is enabled.",
            "Give the service account BigQuery Data Viewer, BigQuery Job User, Monitoring Viewer and Billing Account Viewer.",
            "Enable the BigQuery, Cloud Monitoring and Cloud Billing APIs on the project.",
            "Use a separate project for each environment. All of its cost is shown under the environment you choose.",
        ],
        "cost_note": "Testing uses a BigQuery dry run, which scans no data and is free.",
    },
}


class ConfigNotVerified(Exception):
    """A config was saved or activated without passing a connection test first."""


class AccountInUse(Exception):
    """The cloud account already serves another environment, so its cost would count twice."""


def _secret_names(provider: str) -> List[str]:
    return [f["name"] for f in FIELDS[provider] if f["type"] in ("secret", "secret_text")]


def _field_names(provider: str) -> List[str]:
    return [f["name"] for f in FIELDS[provider]]


def _defaults(provider: str) -> Dict[str, str]:
    return {f["name"]: f["default"] for f in FIELDS[provider] if f.get("default")}


def mode_of(db: Session, provider: str) -> str:
    row = db.get(CloudAccount, provider)
    return row.mode if row is not None else "mock"


def summary(db: Session) -> str:
    """Overall data source: mock, live, or mixed when clouds differ."""
    modes = {mode_of(db, p) for p in get_settings().enabled_providers}
    return modes.pop() if len(modes) == 1 else "mixed"


def _connection(db: Session, provider: str, environment: str) -> CloudConnection:
    row = db.get(CloudConnection, (provider, environment))
    if row is None:
        row = CloudConnection(provider=provider, environment=environment, config={}, secrets_encrypted="")
        db.add(row)
    return row


def _is_saved(row: CloudConnection) -> bool:
    return bool(row.config or row.secrets_encrypted)


def saved_connections(db: Session, provider: str) -> List[CloudConnection]:
    rows = db.execute(select(CloudConnection).where(CloudConnection.provider == provider)).scalars().all()
    return sorted((r for r in rows if _is_saved(r)), key=lambda r: ENVIRONMENTS.index(r.environment))


def _stored_secrets(row: Optional[CloudConnection]) -> Dict[str, str]:
    if row is None:
        return {}
    try:
        return decrypt_secrets(row.secrets_encrypted)
    except CredentialsUnreadable:
        return {}


def effective_config(db: Session, provider: str, environment: str, submitted: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merge field defaults, saved values and (optionally) values just typed in the form.

    A blank secret in the form means "keep the saved one". A blank non-secret field means "not set".
    """
    row = db.get(CloudConnection, (provider, environment))
    cfg = {**_defaults(provider), **{k: v for k, v in _stored_secrets(row).items() if v}}
    source = submitted if submitted is not None else (row.config if row is not None else {})
    allowed = set(_field_names(provider))
    cfg.update({k: str(v).strip() for k, v in (source or {}).items() if k in allowed and str(v).strip()})
    cfg["environment"] = environment
    return cfg


def validate(provider: str, cfg: Dict[str, str]) -> List[Dict[str, str]]:
    """Field-level checks that need no network. Returns [{field, message}]."""
    errors: List[Dict[str, str]] = []
    for f in FIELDS[provider]:
        cond = f.get("show_when")
        if cond and any(cfg.get(k) != v for k, v in cond.items()):
            continue
        value = cfg.get(f["name"], "")
        if not value:
            if f.get("required"):
                errors.append({"field": f["name"], "message": f"{f['label']} is required"})
            continue
        if len(value) > 16384:
            errors.append({"field": f["name"], "message": f"{f['label']} is too long"})
        elif f.get("pattern") and not re.match(f["pattern"], value):
            errors.append({"field": f["name"], "message": f"{f['label']} has an invalid format"})
        elif f.get("options") and value not in [o["value"] for o in f["options"]]:
            errors.append({"field": f["name"], "message": f"{f['label']} has an unknown value"})
    if provider == "gcp" and cfg.get("service_account_json"):
        message = _service_account_error(cfg["service_account_json"])
        if message:
            errors.append({"field": "service_account_json", "message": message})
    return errors


def _service_account_error(text: str) -> Optional[str]:
    try:
        info = json.loads(text)
    except ValueError:
        return "Service account key is not valid JSON"
    if not isinstance(info, dict) or info.get("type") != "service_account" or not info.get("private_key") or not info.get("client_email"):
        return "This JSON is not a service account key"
    return None


def is_verified(db: Session, provider: str, environment: str, cfg: Optional[Dict[str, str]] = None) -> bool:
    row = db.get(CloudConnection, (provider, environment))
    if row is None:
        return False
    fp = fingerprint(cfg if cfg is not None else effective_config(db, provider, environment))
    return fp in (row.tested_hash, row.verified_hash)


def account_conflict(db: Session, provider: str, environment: str, account: str) -> Optional[str]:
    """The other environment already using this cloud account, if any."""
    if not account:
        return None
    for row in saved_connections(db, provider):
        if row.environment != environment and row.account == account:
            return row.environment
    return None


def record_test(db: Session, provider: str, environment: str, cfg: Dict[str, str], result: Dict[str, Any]) -> None:
    row = _connection(db, provider, environment)
    fp = fingerprint(cfg)
    if result.get("ok"):
        row.tested_hash = fp
        row.last_test_account = str(result.get("account") or "")[:80]
        if row.verified_hash == fp:
            row.account = row.last_test_account
    else:  # these exact values stopped working: they may no longer be activated
        if row.tested_hash == fp:
            row.tested_hash = ""
        if row.verified_hash == fp:
            row.verified_hash = ""
    row.last_test_ok = bool(result.get("ok"))
    row.last_test_at = datetime.now(timezone.utc)
    row.last_test_message = str(result.get("message") or "")[:2000]
    db.commit()


def save_config(db: Session, provider: str, environment: str, submitted: Dict[str, str]) -> None:
    cfg = effective_config(db, provider, environment, submitted)
    row = _connection(db, provider, environment)
    if not row.tested_hash or fingerprint(cfg) != row.tested_hash:
        db.rollback()
        raise ConfigNotVerified("Run a successful connection test with these values before saving")
    other = account_conflict(db, provider, environment, row.last_test_account)
    if other:
        db.rollback()
        raise AccountInUse(f"Account {row.last_test_account} is already configured for {other.title()}. Its cost would count twice.")
    names, secrets = _field_names(provider), _secret_names(provider)
    row.config = {k: cfg[k] for k in names if k not in secrets and cfg.get(k)}
    row.secrets_encrypted = encrypt_secrets({k: cfg[k] for k in secrets if cfg.get(k)})
    row.verified_hash = row.tested_hash
    row.account = row.last_test_account
    db.commit()


def set_mode(db: Session, provider: str, mode: str) -> None:
    if mode == "live" and not any(is_verified(db, provider, c.environment) for c in saved_connections(db, provider)):
        raise ConfigNotVerified("Configure at least one environment and pass its connection test before switching to Live")
    row = db.get(CloudAccount, provider)
    if row is None:
        db.add(CloudAccount(provider=provider, mode=mode))
    else:
        row.mode = mode
    db.commit()


def clear_config(db: Session, provider: str, environment: str) -> None:
    """Forget one environment's connection, and return the cloud to mock when none is left."""
    row = db.get(CloudConnection, (provider, environment))
    if row is not None:
        db.delete(row)
        db.flush()
    if not saved_connections(db, provider):
        set_mode(db, provider, "mock")
    db.commit()


def connection_summaries(db: Session, provider: str) -> List[Dict[str, Any]]:
    return [{"environment": c.environment, "account": c.account, "verified": is_verified(db, provider, c.environment)} for c in saved_connections(db, provider)]


def public_view(db: Session, provider: str, environment: str) -> Dict[str, Any]:
    """Everything the configuration form needs. Secret values never leave the server."""
    row = db.get(CloudConnection, (provider, environment))
    cfg = effective_config(db, provider, environment)
    secrets = _secret_names(provider)
    unreadable = False
    if row is not None and row.secrets_encrypted:
        try:
            decrypt_secrets(row.secrets_encrypted)
        except CredentialsUnreadable:
            unreadable = True
    return {
        "provider": provider,
        "environment": environment,
        "environments": list(ENVIRONMENTS),
        "mode": mode_of(db, provider),
        "connections": connection_summaries(db, provider),
        "fields": FIELDS[provider],
        "values": {k: cfg.get(k, "") for k in _field_names(provider) if k not in secrets},
        "secrets_set": {k: bool(cfg.get(k)) for k in secrets},
        "secrets_unreadable": unreadable,
        "has_saved_config": bool(row is not None and _is_saved(row)),
        "verified": is_verified(db, provider, environment, cfg),
        "account": row.account if row is not None else "",
        **GUIDES[provider],
    }
