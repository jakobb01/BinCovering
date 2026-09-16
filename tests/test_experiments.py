import csv
import json
from fractions import Fraction

import pytest

from bincovering.experiments.config import validate
from bincovering.experiments.runner import run_experiment
from bincovering.generators.instances import generate


def rows(path):
    with (path / "trials.csv").open() as f:
        return sorted(csv.DictReader(f), key=lambda r: (r["trial"], r["algorithm"]))


def test_parallel_reproducibility_and_paired_inputs(tmp_path):
    config = {
        "n": 40,
        "trials": 3,
        "output_root": str(tmp_path),
        "algorithms": [
            {"id": "dnf"},
            {"id": "ThrowBin_1"},
            {"id": "AdaptiveBin"},
            {"id": "AdaptiveBinCovered"},
        ],
    }
    a = run_experiment(config)
    b = run_experiment(config | {"workers": 2})
    left, right = rows(a), rows(b)
    for left_row, right_row in zip(left, right, strict=True):
        left_row.pop("elapsed_seconds")
        right_row.pop("elapsed_seconds")
        assert left_row == right_row
    for trial in ("0", "1", "2"):
        assert len({r["input_hash"] for r in left if r["trial"] == trial}) == 1
    assert (a / "source.zip").is_file()
    assert not (a / "traces").exists()


@pytest.mark.parametrize("domain,threshold", [("float64", 1.0), ("integer", 1000000)])
def test_constructed_optimum(domain, threshold):
    cfg = validate(
        {
            "n": 20,
            "domain": domain,
            "threshold": threshold,
            "generator": {"id": "complementary_pairs"},
            "ordering": "original",
        }
    )
    items, info = generate(cfg, 123, 321)
    assert all(
        Fraction(a) + Fraction(b) == threshold
        for a, b in zip(items[::2], items[1::2], strict=True)
    )
    assert info["exact_optimum"] == info["upper_bound"] == 10


def test_ordering_preserves_input_multiset():
    cfg = validate({"n": 100, "ordering": "original"})
    a, ai = generate(cfg, 1, 2)
    for order in ("descending", "ascending", "shuffle", "swaps"):
        b, bi = generate(cfg | {"ordering": order, "swaps": 20}, 1, 2)
        assert sorted(a) == sorted(b)
        assert ai["base_input_hash"] == bi["base_input_hash"]


def test_failed_trial_is_recorded(tmp_path):
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "n": 1,
            "trials": 1,
            "algorithms": [{"id": "ThrowBin_1"}],
        }
    )
    assert rows(path)[0]["status"] == "failed"
    assert json.loads((path / "manifest.json").read_text())["status"] == "failed"


def test_pre_cancelled_job(tmp_path):
    out = tmp_path / "cancelled"
    out.mkdir()
    (out / "CANCEL").touch()
    run_experiment({"trials": 3}, out)
    assert json.loads((out / "manifest.json").read_text())["status"] == "cancelled"


def test_reject_overwrite(tmp_path):
    path = run_experiment({"output_root": str(tmp_path), "n": 2, "trials": 1})
    before = (path / "trials.csv").read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        run_experiment({}, path)
    assert (path / "trials.csv").read_bytes() == before


def test_file_inputs_are_saved_exactly(tmp_path):
    source = tmp_path / "items.txt"
    source.write_text("0.25\n0.75\n")
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "trials": 1,
            "generator": {"id": "file", "path": str(source)},
            "ordering": "original",
        }
    )
    assert json.loads((path / "inputs/0.json").read_text()) == [0.25, 0.75]


@pytest.mark.parametrize(
    "settings",
    [
        {"workers": 0},
        {"generator": {"id": "big_items", "min": 0.1}},
        {"generator": {"id": "complementary_pairs"}, "n": 3},
        {"domain": "integer", "threshold": 1.0},
        {"algorithms": [{"id": "unknown"}]},
    ],
)
def test_invalid_config(settings):
    with pytest.raises(ValueError):
        validate(settings)
