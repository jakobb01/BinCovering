"""Side-effect-free generation and ordering with independent random streams."""

import hashlib
import json
import math
import random
from fractions import Fraction


def digest(items):
    return hashlib.sha256(
        json.dumps(items, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def generate(cfg, data_seed, order_seed):
    rng = random.Random(data_seed)
    n, domain, threshold = cfg["n"], cfg["domain"], cfg["threshold"]
    generator = cfg["generator"]
    name = generator["id"]
    low, high = generator["min"], generator["max"]
    exact = None
    if name == "file":
        from pathlib import Path

        parse = int if domain == "integer" else float
        items = [parse(x) for x in Path(generator["path"]).read_text().split()]
    elif name in ("uniform", "big_items"):
        sample = rng.randint if domain == "integer" else rng.uniform
        items = [sample(low, high) for _ in range(n)]
        if name == "big_items":
            exact = n // 2
    elif name == "complementary_pairs":
        items = []
        for _ in range(n // 2):
            # Dyadic floats make both complements and their sum exactly representable.
            small = (
                rng.randint(1, threshold - 1)
                if domain == "integer"
                else rng.randint(1, 2**51 - 1) / 2**52
            )
            items.extend([small, threshold - small])
        exact = n // 2
    else:
        raise ValueError(f"Unknown generator: {name}")
    if any(not math.isfinite(x) or x <= 0 or x > threshold for x in items):
        raise ValueError("Items must be finite and in (0, threshold]")
    base_hash = digest(items)
    ordering = cfg["ordering"]
    order_rng = random.Random(order_seed)
    if ordering in ("ascending", "descending", "swaps"):
        items.sort(reverse=ordering != "ascending")
    elif ordering == "shuffle":
        order_rng.shuffle(items)
    if ordering == "swaps" and items:
        for _ in range(cfg["swaps"]):
            i, j = order_rng.randrange(len(items)), order_rng.randrange(len(items))
            items[i], items[j] = items[j], items[i]
    # Exact arithmetic on the represented inputs avoids rounding a mass bound upward/downward.
    mass = sum((Fraction(x) for x in items), Fraction())
    bound = int(mass // Fraction(threshold))
    return items, {
        "base_input_hash": base_hash,
        "input_hash": digest(items),
        "upper_bound": bound,
        "exact_optimum": exact,
        "reference_kind": "constructed_optimum"
        if name == "complementary_pairs"
        else "exact_optimum"
        if exact is not None
        else "mass_upper_bound",
    }
