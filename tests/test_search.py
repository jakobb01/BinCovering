"""Exercise the browser's search helper against realistic saved configurations."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SEARCH = Path(__file__).resolve().parents[1] / "src/bincovering/web/static/search.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    NODE is None, reason="Node is unavailable; browser tests cover search"
)

RUNS = {
    "incomplete": {"id": "old-run", "name": "Incomplete archive"},
    "shuffle": {
        "id": "20260930-alpha",
        "name": "Alphá study",
        "status": "completed",
        "config": {
            "n": 1000,
            "trials": 30,
            "seed": 42,
            "workers": 2,
            "ordering": "shuffle",
            "swaps": 100,
            "swap_mode": "distinct",
            "domain": "float64",
            "dataset_mode": "fixed",
            "generator": {"id": "uniform", "min": 0.0001, "max": 1, "bins": 100},
            "algorithms": [
                {"id": "dual_next_fit", "backend": "python", "params": {}},
                {
                    "id": "throwbin_replace",
                    "backend": "python",
                    "params": {"bin_ratio": 0.3},
                },
            ],
        },
    },
    "swaps": {
        "id": "beta-run",
        "name": "Beta study",
        "status": "completed",
        "config": {
            "n": 2000,
            "trials": 20,
            "seed": 7,
            "workers": 4,
            "ordering": "swaps",
            "swaps": 100,
            "swap_mode": "with_replacement",
            "domain": "float64",
            "dataset_mode": "fresh",
            "generator": {"id": "big_items", "min": 0.6, "max": 0.9},
            "algorithms": [
                {"id": "dual_harmonic", "backend": "python", "params": {"k": 5}}
            ],
        },
    },
    "native": {
        "id": "gamma-run",
        "name": "Gamma study",
        "status": "failed",
        "config": {
            "n": 10000,
            "trials": 3,
            "seed": 2,
            "workers": 1,
            "ordering": "descending",
            "swaps": 1000,
            "swap_mode": "distinct",
            "domain": "integer",
            "dataset_mode": "fixed",
            "generator": {"id": "file", "path": "/datasets/sample.dat"},
            "algorithms": [{"id": "dual_next_fit", "backend": "cpp", "params": {}}],
        },
    },
}


def check_cases(cases):
    script = """
      const {matchesRun} = require(process.argv[1]);
      const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
      process.stdout.write(JSON.stringify(input.cases.map(([run,query]) =>
        matchesRun(query, input.runs[run]))));
    """
    result = subprocess.run(
        [NODE, "-e", script, str(SEARCH)],
        input=json.dumps(
            {"runs": RUNS, "cases": [[run, query] for run, query, _ in cases]}
        ),
        text=True,
        capture_output=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    for (_, query, expected), found in zip(cases, actual, strict=True):
        assert found is expected, query


def test_search_recorded_research_metadata_and_aliases():
    check_cases(
        [
            ("shuffle", "shuffle 1000", True),
            ("shuffle", "shuffled items:1000", True),
            ("shuffle", "permutation fixed uniform python", True),
            (
                "shuffle",
                "order:shuffle generator:uniform dataset:fixed backend:python",
                True,
            ),
            ("shuffle", "dnf throw bin replacement bin_ratio:0.3", True),
            ("shuffle", "workers:2 trials:30 seed:42", True),
            ("shuffle", "float64 completed alpha", True),
            ("swaps", "swaps 100 with replacement harmonic k:5", True),
            ("swaps", "swaps:100 trials:20 fresh big_items", True),
            ("native", "desc native integer sample.dat", True),
            ("native", "ordering:descending backend:cpp failed", True),
            ("native", "shuffle", False),
            ("shuffle", "shuffle harmonic", False),
        ]
    )


def test_numeric_search_is_exact_and_ignores_inactive_swaps():
    check_cases(
        [
            ("shuffle", "100", False),
            ("shuffle", "1001", False),
            ("shuffle", "1000", True),
            ("shuffle", "1,000", True),
            ("native", "1000", False),
            ("shuffle", "n:1000", True),
            ("shuffle", "items:100", False),
            ("shuffle", "n:1001", False),
            ("shuffle", "swaps:100", False),
            ("shuffle", "swaps 100", False),
            ("shuffle", "swaps:0", False),
            ("shuffle", "distinct", False),
            ("shuffle", "swap_mode:distinct", False),
            ("shuffle", "bins:100", False),
            ("swaps", "items:100", False),
            ("swaps", "swaps 2000", False),
            ("swaps", "swaps:1000", False),
            ("shuffle", "bin_ratio:0.4", False),
            ("shuffle", "workers:3", False),
            ("shuffle", "seed:4", False),
        ]
    )


def test_numeric_ranges_and_spacing_compose_with_text_terms():
    check_cases(
        [
            ("shuffle", "n >= 1000 n<1001 trials: 30", True),
            ("shuffle", "items > 1000", False),
            ("native", "n>=1000 n<=10000 backend:cpp", True),
            ("native", "n<10000", False),
            ("swaps", "swaps>=100 swaps<101", True),
            ("shuffle", "swaps<101", False),
            ("shuffle", "bin_ratio>=0.3 bin_ratio<0.31", True),
            ("shuffle", "n:many", False),
            ("shuffle", "n:", False),
            ("shuffle", "unknown:1000", False),
            ("shuffle", "n>=NaN", False),
        ]
    )


def test_fuzzy_words_accents_and_empty_or_missing_records():
    check_cases(
        [
            ("shuffle", "", True),
            ("shuffle", "   ", True),
            ("shuffle", "ALPHA SHUFFLE", True),
            ("shuffle", "alpza shufle", True),
            ("shuffle", "thrbn", True),
            ("shuffle", "unifom", True),
            ("shuffle", "alphaxxx", False),
            ("native", "missing", False),
            ("incomplete", "archive", True),
            ("incomplete", "n:1000", False),
            ("incomplete", "seed:42", False),
            ("incomplete", "python shuffle", False),
        ]
    )
