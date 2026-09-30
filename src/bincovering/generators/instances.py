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


def generate(cfg, data_seed, order_seed, cancelled=lambda: False, builder_trace=None):
    rng = random.Random(data_seed)
    n, domain, threshold = cfg["n"], cfg["domain"], cfg["threshold"]
    generator = cfg["generator"]
    name = generator["id"]
    low, high = generator["min"], generator["max"]
    exact = None
    target = None

    def checkpoint(index):
        if index % 1024 == 0 and cancelled():
            raise InterruptedError("Cancelled")

    if name.startswith("custom:"):
        from bincovering.builders.execution import execute_isolated

        frozen = generator["frozen"]
        response = execute_isolated(
            frozen["graph"], seed=data_seed, params=generator["params"],
            domain=domain, threshold=threshold, n=n, root=cfg["output_root"],
            runtime_image=frozen["runtime_image"], cancelled=cancelled,
            trace_limit=cfg["trace_limit"] if builder_trace else 0,
            trace_bytes=cfg["trace_bytes"],
        )
        if builder_trace:
            builder_trace(response.get("trace", {}), response["execution"])
        if not response["ok"]:
            raise ValueError(response.get("error", {}).get("message", "Custom generation failed"))
        items = response["result"].get("items")
        if not isinstance(items, list) or any(type(value) not in (int, float) for value in items):
            raise ValueError("Custom generator returned invalid item sizes")
        if domain == "integer" and any(type(value) is not int for value in items):
            raise ValueError("Integer custom generators must emit integer item sizes")
    elif name == "file":
        from pathlib import Path

        parse = int if domain == "integer" else float
        items = [parse(x) for x in Path(generator["path"]).read_text().split()]
    elif name in ("uniform", "big_items"):
        sample = rng.randint if domain == "integer" else rng.uniform
        items = []
        for index in range(n):
            checkpoint(index)
            items.append(sample(low, high))
        if name == "big_items":
            exact = n // 2
    elif name == "complementary_pairs":
        items = []
        for index in range(n // 2):
            checkpoint(index)
            # Dyadic floats make both complements and their sum exactly representable.
            small = (
                rng.randint(1, threshold - 1)
                if domain == "integer"
                else rng.randint(1, 2**51 - 1) / 2**52
            )
            items.extend([small, threshold - small])
        exact = n // 2
    elif name == "one_over_n":
        smalls = []
        for index in range(n // 2):
            checkpoint(index)
            # Match the historical generator, including reversed endpoints for N>20000.
            smalls.append(rng.uniform(0.0001, 1 / (n // 2)))
        items = smalls + [1.0 - value for value in smalls]
        items.sort(reverse=True)
        target = n // 2
    elif name == "optimal_uniform_legacy":
        items = []
        remaining = threshold
        completed = 0
        draws = 0
        target = generator["bins"]
        while completed < target:
            checkpoint(draws)
            draws += 1
            value = rng.uniform(low, high)
            previous = remaining
            remaining -= value
            if remaining == previous:
                raise ValueError("Generator makes no floating-point progress")
            if remaining < generator["completion_fraction"] * threshold:
                if remaining < 0:
                    remaining += value
                    if remaining > low:
                        items.append(remaining)
                else:
                    items.append(value)
                    if remaining > low:
                        items.append(remaining)
                remaining = threshold
                completed += 1
            else:
                items.append(value)
        items.sort(reverse=True)
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
        if cfg["swap_mode"] == "distinct" and len(items) < 2 and cfg["swaps"]:
            raise ValueError("Distinct swaps need at least two items")
        for index in range(cfg["swaps"]):
            checkpoint(index)
            i, j = (
                order_rng.sample(range(len(items)), 2)
                if cfg["swap_mode"] == "distinct"
                else (order_rng.randrange(len(items)), order_rng.randrange(len(items)))
            )
            items[i], items[j] = items[j], items[i]
    # Exact arithmetic on the represented inputs avoids rounding a mass bound upward/downward.
    mass = Fraction()
    for index, item in enumerate(items):
        checkpoint(index)
        mass += Fraction(item)
    bound = int(mass // Fraction(threshold))
    return items, {
        "base_input_hash": base_hash,
        "input_hash": digest(items),
        "upper_bound": bound,
        "exact_optimum": exact,
        "construction_target": target,
        "reference_kind": "constructed_optimum"
        if name == "complementary_pairs"
        else "exact_optimum"
        if exact is not None
        else "mass_upper_bound",
    }
