"""Reproducibility metadata. Hashes identify source/templates, not clinical validity."""
import hashlib
from pathlib import Path
from uuid import uuid4
from models import AlertIn, GenerationProvenance, RuleOutput
from explanation_contract import VALIDATION_VERSION
from prompt_builder import PROMPT_VERSION, prompt_hash, rendered_hash


def rules_version() -> str:
    root = Path(__file__).resolve().parent
    files = ["rules_engine.py", "router.py"]
    content = b"".join(name.encode() + b"\0" + (root / name).read_bytes().replace(b"\r\n", b"\n") for name in files)
    return "rules-v1-sha256:" + hashlib.sha256(content).hexdigest()


def generation_metadata(alert: AlertIn, rules: RuleOutput, correlation_id: str | None = None) -> GenerationProvenance:
    return GenerationProvenance(rules_version=rules_version(), prompt_version=PROMPT_VERSION,
        prompt_hash=prompt_hash(alert.alert_type.value), rendered_prompt_hash=rendered_hash(alert, rules),
        validation_version=VALIDATION_VERSION, request_correlation_id=correlation_id or str(uuid4()))
