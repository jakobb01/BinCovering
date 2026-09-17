import importlib.util
import random
from pathlib import Path

import pytest

from bincovering.algorithms.registry import normalize, solve


def test_mixer_percentage(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "legacy_mixer",
        str(Path(__file__).parent / "reference" / "mixer.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    counts = []
    monkeypatch.setattr(
        module,
        "randomize_sort",
        lambda numbers, amount: counts.append(amount) or numbers,
    )
    module.reorder_numbers([3, 2, 1], tmp_path / "mixed.txt", 5, 100)
    assert counts == [3]


@pytest.mark.parametrize(
    "name,module_name,class_name,params",
    [
        ("ThrowBin", "ThrowBin", "ThrowBinStrategy", {"bin_ratio": 0.5}),
        ("ThrowBin_1", "ThrowBin_1", "ThrowBin_1_Strategy", {"bin_ratio": 0.5}),
        ("ThrowBin_DNF", "ThrowBin_DNF", "ThrowBinDNFStrategy", {}),
        ("AdaptiveBin", "AdaptiveBin", "AdaptiveBinStrategy", {}),
        ("AdaptiveBinCovered", "AdaptiveBinCovered", "AdaptiveBinCoveredStrategy", {}),
    ],
)
def test_adapter_preserves_migrated_strategy(name, module_name, class_name, params):
    import importlib

    from bincovering.algorithms.registry import Stream

    cls = getattr(
        importlib.import_module("bincovering.algorithms." + module_name), class_name
    )
    items = [0.2, 0.9, 0.3, 0.7] * 20
    original = cls(**params)
    original.rng = random.Random(41)
    if name in ("ThrowBin", "ThrowBin_1"):
        original.start(Stream(items), num_items=len(items))
    else:
        original.start(Stream(items))
    while original.next() is not None:
        pass
    assert (
        solve(items, normalize({"id": name, "params": params}), 1.0, 41).covered_bins
        == original.covered_bins
    )
