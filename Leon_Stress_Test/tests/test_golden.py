"""Golden file : les chiffres clés du rapport de référence ne bougent pas sans qu'on le décide."""

import json
from datetime import date

import pytest
from conftest import ROOT
from test_failures import write_config

from quantlab.config import load_settings
from quantlab.pipelines import run_daily as rd

pytestmark = pytest.mark.slow
GOLDEN = ROOT / "tests" / "golden" / "report_2025-12-31.json"
TOL_EUR = 1.0


def key_figures(ctx):
    """Ce que le rapport publie, en nombres simples (pas de DataFrame : le JSON doit rester lisible)."""
    d = ctx.data
    return {
        "valeur_eur": d["valuation"]["valeur_eur"].round(2).to_dict(),
        "stress_total": d["stress"]["TOTAL"].round(2).to_dict(),
        "var99": round(d["var"]["var99"], 2),
        "es975": round(d["var"]["es975"], 2),
    }


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        return {k2: v2 for k, v in obj.items() for k2, v2 in flatten(v, f"{prefix}{k}/").items()}
    return {prefix.rstrip("/"): obj}


def test_reference_report(tmp_path, update_golden):
    config, _ = write_config(tmp_path)
    code, ctx = rd.run_daily(date(2025, 12, 31), load_settings(config))
    assert code == 0
    got = key_figures(ctx)
    if update_golden:
        GOLDEN.write_text(json.dumps(got, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip("golden file réécrit : relis le diff Git avant de commiter")
    expected, actual = flatten(json.loads(GOLDEN.read_text(encoding="utf-8"))), flatten(got)
    assert actual.keys() == expected.keys(), "positions ou scénarios ajoutés/retirés"
    diffs = {k: (expected[k], actual[k]) for k in expected if abs(actual[k] - expected[k]) > TOL_EUR}
    assert not diffs, "\n".join(f"{k}: attendu {e:,.2f}, obtenu {a:,.2f}" for k, (e, a) in diffs.items())
