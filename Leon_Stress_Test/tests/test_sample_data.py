"""Données synthétiques : reproductibles, et prolongeables sans modifier le passé."""

from quantlab.make_sample_data import make_sample_data


def test_extension_keeps_history(tmp_path):
    base = make_sample_data(tmp_path / "a")
    longer = make_sample_data(tmp_path / "b", end="2026-03-31")
    assert longer.index[-1].strftime("%Y-%m-%d") == "2026-03-31"
    assert longer.loc[: base.index[-1]].equals(base)  # mêmes prix jusqu'au 31/12/2025


def test_same_seed_same_files(tmp_path):
    make_sample_data(tmp_path / "a")
    make_sample_data(tmp_path / "b")
    assert (tmp_path / "a" / "fx.csv").read_bytes() == (tmp_path / "b" / "fx.csv").read_bytes()
