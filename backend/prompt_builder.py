"""Versioned templates plus canonical evidence; no clinical primers or rule scores."""
import hashlib
import json
from pathlib import Path
from string import Template
from evidence import catalog_for
from models import AlertIn, RuleOutput

PROMPT_VERSION = "explanation-contract-v4"
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def prompt_metadata(alert_type: str) -> tuple[str, str]:
    path = _PROMPTS_DIR / f"{alert_type}_prompt.md"
    if not path.exists(): path = _PROMPTS_DIR / "explainability_prompt.md"
    system = (_PROMPTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    template = path.read_text(encoding="utf-8")
    return system, template


def prompt_hash(alert_type: str) -> str:
    return hashlib.sha256(json.dumps(prompt_metadata(alert_type), ensure_ascii=False).encode()).hexdigest()


def build_messages(alert: AlertIn, rule_output: RuleOutput) -> tuple[str, str]:
    system, template = prompt_metadata(alert.alert_type.value)
    catalog = {k: v for k, v in catalog_for(alert, rule_output).items() if k != "escalated_route"}  # Validator-only lookup.
    return system, Template(template).substitute(evidence_json=json.dumps(catalog, ensure_ascii=False, sort_keys=True))


def rendered_hash(alert: AlertIn, rules: RuleOutput) -> str:
    return hashlib.sha256(json.dumps(build_messages(alert, rules), ensure_ascii=False).encode()).hexdigest()
