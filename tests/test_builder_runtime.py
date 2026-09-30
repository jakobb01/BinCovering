"""Research semantics and language boundaries of the authoritative graph runtime."""

import copy
import json
import random
import subprocess
import sys

import pytest

from bincovering.algorithms.registry import solve
from bincovering.builders import (
    BuilderError,
    convert_program,
    execute,
    generated_source,
    get_template,
    graph_hash,
    parse_program,
    resolve_parameters,
    starter_templates,
    validate_graph,
)
from bincovering.builders.schema import port_types

ITEMS = [0.35, 0.75, 0.4, 0.65, 0.2, 0.3]


def _custom_graph(source, *, kind="algorithm", access="online", notation="python"):
    if kind == "component":
        graph = get_template("component")
        graph["inputs"] = {}
        graph["outputs"] = {}
        graph["parameters"] = {}
        graph["nodes"][1]["config"] = {"source": source, "notation": notation}
        return graph
    graph = get_template(
        "generator"
        if kind == "generator"
        else "offline"
        if access == "offline"
        else "online"
    )
    phase = "process" if access == "offline" else "next"
    graph["nodes"] = [node for node in graph["nodes"] if node["type"] == "entry"]
    if kind == "algorithm":
        graph["nodes"].append({"id": "open", "type": "create_bin", "config": {}})
    graph["nodes"].append(
        {
            "id": "custom",
            "type": "custom",
            "config": {"source": source, "notation": notation},
        }
    )
    graph["edges"] = [{"id": "execute", "source": phase, "target": "custom"}]
    if kind == "algorithm":
        graph["edges"].append({"id": "init", "source": "start", "target": "open"})
    return graph


def test_working_online_and_offline_match_dnf_for_paired_inputs():
    rng = random.Random(17)
    cases = [
        [],
        ITEMS,
        [1.0, 1.0],
        [0.1] * 10,
        [rng.uniform(0.0001, 0.999) for _ in range(127)],
    ]
    for items in cases:
        expected = solve(items, {"id": "dual_next_fit", "params": {}}, 1, 99)
        for kind in ("online", "offline"):
            response = execute(get_template(kind), items=items, n=len(items), seed=99)
            assert response["ok"], response
            assert response["result"]["covered_bins"] == expected.covered_bins
            assert response["result"]["bin_statistics"]["conservation_ok"]


def test_integer_domain_never_rescales_and_uses_exact_ledger():
    graph = get_template("online")
    graph["domain"] = "integer"
    for component in graph["components"].values():
        component["graph"]["domain"] = "integer"
    response = execute(graph, items=[4, 7, 5, 5, 2], threshold=10, domain="integer")
    assert response["ok"]
    statistics = response["result"]["bin_statistics"]
    assert statistics["covered_bins"] == 2
    assert statistics["unfinished_mass"] == 2
    assert statistics["conservation_error"] == 0
    assert type(statistics["input_mass"]) is int
    assert not execute(graph, items=[0.4], threshold=10)["ok"]
    assert not execute(graph, items=[4], threshold=1.0)["ok"]
    assert not execute(graph, items=[4], threshold=10, domain="float64")["ok"]


def test_float_coverage_has_no_implicit_epsilon():
    response = execute(get_template("online"), items=[0.1] * 10)
    assert response["ok"]
    assert response["result"]["covered_bins"] == 0
    assert response["result"]["bin_statistics"]["unfinished_mass"] < 1


def test_generator_rng_is_python_private_random_stream():
    graph = get_template("generator")
    response = execute(graph, seed=312, n=20, params={"min_size": 0.2, "max_size": 0.5})
    rng = random.Random(312)
    assert response["ok"]
    assert response["result"]["items"] == [rng.uniform(0.2, 0.5) for _ in range(20)]
    assert response == execute(
        graph, seed=312, n=20, params={"min_size": 0.2, "max_size": 0.5}
    )
    assert response["result"] != execute(graph, seed=313, n=20)["result"]


def test_python_pseudocode_share_result_and_trace():
    python = "for i in range(len(sequence)):\n    place(sequence[i], active_bin, i)\n    if bin_load(active_bin) >= threshold:\n        cover(active_bin)"
    pseudo = convert_program(python, "python", "pseudocode")
    converted = convert_program(pseudo, "pseudocode", "python")
    graph = _custom_graph(python, access="offline")
    second = _custom_graph(pseudo, access="offline", notation="pseudocode")
    third = _custom_graph(converted, access="offline")
    first_result = execute(graph, items=ITEMS)
    second_result = execute(second, items=ITEMS)
    assert first_result["ok"] and second_result["ok"]
    assert (
        first_result["result"]
        == second_result["result"]
        == execute(third, items=ITEMS)["result"]
    )
    assert graph_hash(graph) == graph_hash(second) == graph_hash(third)

    def strip_locations(trace):
        result = copy.deepcopy(trace)
        for event in result["events"]:
            event.pop("line", None)
        return result

    assert strip_locations(first_result["trace"]) == strip_locations(
        second_result["trace"]
    )


@pytest.mark.parametrize(
    "source",
    [
        "import os",
        "__import__('os')",
        "open('/tmp/secret')",
        "item.real",
        "while True:\n    pass",
        "def f():\n    pass",
        "[x for x in range(3)]",
        "exec('pass')",
        "lambda x: x",
        "state = {'sequence': [1]}",
        "sequence[0] = 3",
        "covered_bins = 100",
        "active_bin = 1",
    ],
)
def test_arbitrary_python_and_ledger_assignments_are_rejected(source):
    with pytest.raises(BuilderError):
        parse_program(source)


def test_pseudocode_has_fixed_grammar_and_original_error_lines():
    with pytest.raises(BuilderError) as error:
        parse_program(
            "IF TRUE THEN\n    SET x = 1\nEND\nmake the bin larger", "pseudocode"
        )
    assert error.value.line == 4
    with pytest.raises(BuilderError):
        parse_program("IF TRUE THEN\nSET x = 1", "pseudocode")
    graph = _custom_graph(
        "SET value = 1\nSET other = value / 0", kind="generator", notation="pseudocode"
    )
    response = execute(graph, n=1)
    assert not response["ok"]
    assert response["error"]["node_id"] == "custom"
    assert response["error"]["line"] == 2


@pytest.mark.parametrize(
    "source,needle",
    [
        ("place(item)\nplace(item)", "exactly once"),
        ("place(item + .01)", "differs"),
        ("cover()", "measured load"),
        ("count = 1", "neither placed nor discarded"),
        ("discard()\nplace(item)", "exactly once"),
        ("place(item, active_bin, index + 1)", "current input"),
    ],
)
def test_managed_ledger_rejects_mass_and_identity_fabrication(source, needle):
    response = execute(_custom_graph(source), items=ITEMS)
    assert not response["ok"]
    assert needle in response["error"]["message"]
    assert response["error"]["node_id"] == "custom"


def test_discard_accounting_and_unclosed_covered_load_are_measured():
    response = execute(
        _custom_graph("if item < .3:\n    discard()\nelse:\n    place(item)"),
        items=ITEMS,
    )
    assert response["ok"]
    assert response["result"]["covered_bins"] == 0
    assert response["result"]["discarded_items"] == 1
    statistics = response["result"]["bin_statistics"]
    assert statistics["unfinished_mass"] == pytest.approx(2.45)
    assert statistics["discarded_mass"] == pytest.approx(0.2)
    assert statistics["conservation_ok"]


def test_online_sequence_access_and_offline_component_composition_rejected():
    graph = _custom_graph("place(sequence[index])")
    with pytest.raises(BuilderError, match="full sequence"):
        validate_graph(graph)
    graph = get_template("online")
    graph["components"]["starter-close"]["graph"]["access"] = "offline"
    with pytest.raises(BuilderError, match="offline component"):
        validate_graph(graph)


def test_parameters_are_typed_bounded_and_cannot_shadow_inputs():
    graph = get_template("generator")
    assert resolve_parameters(graph, {}) == {"min_size": 0.1, "max_size": 0.9}
    with pytest.raises(BuilderError, match="Unknown parameters"):
        resolve_parameters(graph, {"sequence": [1]})
    with pytest.raises(BuilderError, match="at least"):
        resolve_parameters(graph, {"min_size": -1})
    with pytest.raises(BuilderError):
        resolve_parameters(graph, {"max_size": True})
    graph["parameters"]["sequence"] = {"type": "list", "default": [1]}
    with pytest.raises(BuilderError, match="managed"):
        validate_graph(graph)


def test_trace_has_actual_branches_bin_placement_and_nested_call_context():
    response = execute(get_template("online"), items=ITEMS)
    assert response["ok"]
    events = response["trace"]["events"]
    assert {event["branch"] for event in events if event.get("branch")} == {"yes", "no"}
    placements = [e for e in events if e["operation"] == "place"]
    assert [e["input_index"] for e in placements] == list(range(len(ITEMS)))
    assert placements[1]["load_before"] == 0.35
    assert placements[1]["load_after"] == 0.35 + 0.75
    assert any(
        e["call_path"] == ["close"] and e["operation"] == "cover" for e in events
    )
    assert any(e.get("edge_id") == "check-yes-close" for e in events)


def test_trace_limits_do_not_change_results_and_mark_truncation():
    graph = get_template("online")
    full = execute(graph, items=ITEMS)
    limited = execute(graph, items=ITEMS, trace_limit=2)
    bytes_limited = execute(graph, items=ITEMS, trace_bytes=1)
    none = execute(graph, items=ITEMS, trace_limit=0)
    assert (
        full["result"] == limited["result"] == bytes_limited["result"] == none["result"]
    )
    assert limited["trace"]["truncated"] and len(limited["trace"]["events"]) == 2
    assert bytes_limited["trace"]["truncated"] and not bytes_limited["trace"]["events"]
    assert not none["trace"]["truncated"] and not none["trace"]["events"]
    graph["state"] = {"values": [1, 2, 3, 4]}
    snapshot = execute(graph, items=ITEMS, state_limit=2)
    assert any(e["snapshot_truncated"] for e in snapshot["trace"]["events"])


def test_layout_and_notation_changes_do_not_change_execution_hash():
    graph = get_template("online")
    changed = copy.deepcopy(graph)
    changed["name"] = "A new display name"
    for node in changed["nodes"]:
        node.update(x=node["x"] + 12, y=node["y"] + 100, label="New label")
    changed["edges"].reverse()
    assert graph_hash(graph) == graph_hash(changed)
    changed["nodes"][4]["config"]["expression"] = (
        "bin_load(active_bin) >= threshold * 1.2"
    )
    assert graph_hash(graph) != graph_hash(changed)


def test_graph_cycles_dangling_edges_and_missing_branches_are_rejected():
    graph = get_template("online")
    graph["edges"] = [edge for edge in graph["edges"] if edge.get("port") != "no"]
    with pytest.raises(BuilderError, match="both Yes and No"):
        validate_graph(graph)
    graph = get_template("online")
    graph["edges"].append({"id": "cycle", "source": "done", "target": "place"})
    with pytest.raises(BuilderError):
        validate_graph(graph)
    graph = get_template("online")
    graph["edges"][0]["target"] = "missing"
    with pytest.raises(BuilderError, match="missing node"):
        validate_graph(graph)


def _data_graph():
    graph = _custom_graph("discard()")
    graph["nodes"].extend(
        [
            {
                "id": "producer",
                "type": "assign",
                "config": {"variable": "sample", "expression": "item"},
                "outputs": {"value": {"type": "number"}},
            },
            {
                "id": "consumer",
                "type": "custom",
                "inputs": {"incoming": {"type": "number"}},
                "outputs": {"value": {"type": "number"}},
                "config": {
                    "source": "doubled = incoming * 2",
                    "exports": {"value": "doubled"},
                },
            },
        ]
    )
    graph["edges"] = [
        {"id": "init", "source": "start", "target": "open"},
        {"id": "e1", "source": "next", "target": "producer"},
        {"id": "e2", "source": "producer", "target": "consumer"},
        {"id": "e3", "source": "consumer", "target": "custom"},
        {
            "id": "data",
            "source": "producer",
            "target": "consumer",
            "kind": "data",
            "source_port": "value",
            "target_port": "incoming",
        },
    ]
    return graph


def test_typed_data_ports_execute_the_controlled_source_value():
    graph = _data_graph()
    response = execute(graph, items=[0.25, 0.5])
    assert response["ok"], response
    assert port_types(graph["nodes"][-1], graph, output=True)["value"] == "number"
    states = [
        e["state"] for e in response["trace"]["events"] if e["node_id"] == "consumer"
    ]
    assert states[-1]["doubled"] == 1
    graph["nodes"][-1]["inputs"]["incoming"]["type"] = "boolean"
    with pytest.raises(BuilderError, match="Cannot connect"):
        validate_graph(graph)


def test_invalid_data_order_cross_phase_and_declared_output_types_rejected():
    graph = _data_graph()
    edge = graph["edges"][-1]
    edge.update(source="consumer", target="producer", target_port="value")
    with pytest.raises(BuilderError, match="execute before"):
        validate_graph(graph)
    graph = _data_graph()
    graph["edges"][-1].update(source="open", source_port="value")
    graph["nodes"][-1]["inputs"]["incoming"]["type"] = "bin"
    with pytest.raises(BuilderError, match="lifecycle phase"):
        validate_graph(graph)
    graph = _data_graph()
    graph["nodes"][-1]["config"]["exports"]["value"] = "'wrong type'"
    response = execute(graph, items=[0.5])
    assert not response["ok"] and "requires number" in response["error"]["message"]


def test_reusable_typed_component_has_private_persistent_state():
    graph = _custom_graph("discard()")
    component = get_template("component")
    component["state"] = {"count": 0}
    component["nodes"][1]["config"]["source"] = (
        "count += 1\nvalue = incoming * factor + count"
    )
    graph["components"] = {"scale": {"revision": 3, "graph": component}}
    graph["nodes"].append(
        {
            "id": "scale",
            "type": "component",
            "config": {
                "component_id": "scale",
                "inputs": {"incoming": "item"},
                "outputs": {"value": "scaled"},
                "params": {"factor": "2"},
            },
        }
    )
    graph["edges"][0]["target"] = "scale"
    graph["edges"].append({"id": "finish", "source": "scale", "target": "custom"})
    response = execute(graph, items=[0.25, 0.5])
    assert response["ok"], response
    states = [e["state"] for e in response["trace"]["events"] if not e["call_path"]]
    assert states[-1]["scaled"] == 3
    assert "count" not in states[-1]
    assert any(e.get("component_revision") == 3 for e in response["trace"]["events"])


def test_recursive_component_ids_are_rejected():
    graph = get_template("online")
    nested = get_template("component")
    nested["components"] = {
        "starter-close": {"revision": 1, "graph": get_template("component")}
    }
    graph["components"]["starter-close"]["graph"]["components"] = {
        "nested": {"revision": 1, "graph": nested}
    }
    with pytest.raises(BuilderError, match="Recursive"):
        validate_graph(graph)


def test_component_fixtures_are_explicit_traced_and_conserve_item_identity():
    graph = get_template("online")["components"]["starter-close"]["graph"]
    response = execute(
        graph,
        items=[0.4, 0.7],
        component_context={"bins": [[0, 1]], "current_index": 1},
    )
    assert response["ok"], response
    assert response["result"]["covered_bins"] == 1
    assert any(e["phase"] == "fixture" for e in response["trace"]["events"])
    assert response["execution"]["component_fixture"]["bins"] == [[0, 1]]
    invalid = execute(graph, items=[0.4, 0.7], component_context={"bins": [[0], [0]]})
    assert not invalid["ok"] and "twice" in invalid["error"]["message"]
    no_fixture = execute(graph, items=[0.4, 0.7])
    assert not no_fixture["ok"]
    pure = execute(
        get_template("component"), inputs={"incoming": 0.5}, params={"factor": 3}
    )
    assert pure["ok"] and pure["result"]["outputs"] == {"value": 1.5}


def test_component_generator_fixture_and_standalone_effect_validation():
    graph = _custom_graph("emit(.5)", kind="component")
    response = execute(graph, component_context={"kind": "generator"}, n=2)
    assert response["ok"] and response["result"]["items"] == [0.5]
    assert not execute(graph)["ok"]


def test_bounds_of_loops_lists_rng_and_generator_output():
    graph = _custom_graph(
        "values = []\nfor i in range(3):\n    append(values, i)\nemit(values[2] / 4)",
        kind="generator",
    )
    assert execute(graph, n=1)["result"]["items"] == [0.5]
    for source in (
        "for i in range(200001):\n    pass",
        "value = 2 ** 100",
        "emit(0)",
        "emit(2)",
    ):
        response = execute(_custom_graph(source, kind="generator"), n=1)
        assert not response["ok"]
    assert not execute(get_template("generator"), n=200001)["ok"]
    assert not execute(get_template("generator"), trace_limit=10001)["ok"]


def test_worker_protocol_and_generated_export_use_same_runtime(tmp_path):
    request = {"graph": get_template("online"), "items": ITEMS, "seed": 4}
    process = subprocess.run(
        [sys.executable, "-m", "bincovering.builders.worker"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(process.stdout) == execute(**request)
    invalid = subprocess.run(
        [sys.executable, "-m", "bincovering.builders.worker"],
        input='{"graph":{},"unexpected":true}',
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(invalid.stdout)["error"]["code"] == "invalid_request"
    export = tmp_path / "frozen.py"
    export.write_text(generated_source(request["graph"]))
    # This executes the project's generated adapter, never Custom text as Python.
    import runpy

    loaded = runpy.run_path(str(export))
    assert loaded["run"](ITEMS, seed=4)["result"] == execute(**request)["result"]


def test_templates_normalization_is_idempotent():
    for item in starter_templates():
        graph = validate_graph(item["graph"])
        assert validate_graph(graph) == graph


def test_malformed_numeric_and_graph_metadata_have_structured_errors():
    huge = "9" * 1000
    with pytest.raises(BuilderError, match="supported range"):
        parse_program("value = " + huge)
    graph = get_template("generator")
    graph["parameters"]["min_size"]["min"] = "invalid"
    with pytest.raises(BuilderError, match="finite numeric"):
        validate_graph(graph)
    graph = get_template("online")
    graph["edges"][0]["port"] = []
    with pytest.raises(BuilderError):
        validate_graph(graph)
    graph = get_template("online")
    graph["kind"] = []
    assert execute(graph)["error"]["code"] == "invalid_graph"


def test_integer_domain_rejects_float_placement_even_when_numerically_equal():
    graph = _custom_graph("place(item * 1.0)")
    graph["domain"] = "integer"
    response = execute(graph, items=[1], threshold=10)
    assert not response["ok"]
    assert "Integer-domain item" in response["error"]["message"]
