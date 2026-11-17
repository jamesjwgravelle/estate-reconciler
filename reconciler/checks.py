"""The check registry.

Each check lives in its own file under reconciler/rules/ and registers itself with @check.
Any file in that folder whose name does not start with "_" is loaded automatically, so
adding a check never means editing this file. See AGENTS.md for the recipe.

Anything involving arithmetic or matching is done in plain code, never by a language model.
A finding is a discrepancy to follow up on, not a conclusion about anyone's conduct.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from .models import Finding, Matter


@dataclass
class Config:
    exact_window_days: int = 5        # same amount, dates this close: treated as the same item
    similar_window_days: int = 10     # similar payee, dates this close, different amount: mismatch
    late_window_days: int = 60        # same amount but dates this far apart: date discrepancy
    materiality: Decimal = Decimal("25.00")       # bank items below this are not flagged
    letter_amount_floor: Decimal = Decimal("1000")
    # Rule of thumb for executor compensation: a percentage of receipts plus a percentage of
    # disbursements. 2.5% + 2.5% is the customary Ontario starting point; set per jurisdiction.
    comp_rate_receipts: Decimal = Decimal("0.025")
    comp_rate_disbursements: Decimal = Decimal("0.025")


CheckFn = Callable[[Matter, Config], list[Finding]]
REGISTRY: list[CheckFn] = []
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def check(fn: CheckFn) -> CheckFn:
    """Decorator: register a function (matter, config) -> list of Findings."""
    REGISTRY.append(fn)
    return fn


def run_all(m: Matter, cfg: Config | None = None) -> list[Finding]:
    cfg = cfg or Config()
    findings = [f for fn in REGISTRY for f in fn(m, cfg)]
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.type, f.key))


def _load_rules() -> None:
    from . import rules
    for mod in sorted(pkgutil.iter_modules(rules.__path__), key=lambda x: x.name):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{rules.__name__}.{mod.name}")


_load_rules()
