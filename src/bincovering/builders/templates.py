"""Working graphs and contextual examples for the compact Custom field."""

from copy import deepcopy


def _node(identifier, kind, label, phase, x, y, **config):
    return {
        "id": identifier,
        "type": kind,
        "label": label,
        "phase": phase,
        "x": x,
        "y": y,
        "config": config,
    }


def _edge(source, target, port="next"):
    return {
        "id": f"{source}-{port}-{target}",
        "kind": "control",
        "source": source,
        "target": target,
        "port": port,
    }


def _base(kind="algorithm", access="online"):
    return {
        "schema_version": 1,
        "kind": kind,
        "access": access,
        "domain": "float64",
        "parameters": {},
        "state": {},
        "inputs": {},
        "outputs": {},
        "components": {},
        "nodes": [],
        "edges": [],
    }


def _online():
    graph = _base()
    graph.update(
        name="Next fit",
        description="Place each current item, then close a physically covered bin.",
    )
    graph["entries"] = {"start": "start", "next": "next", "stop": "stop"}
    component = _base("component")
    component.update(name="Close covered bin", entries={"process": "entry"})
    component["nodes"] = [
        _node("entry", "entry", "Component input", "process", 40, 40),
        _node(
            "close",
            "custom",
            "Close the covered bin",
            "process",
            310,
            40,
            notation="python",
            source="cover(active_bin)",
        ),
    ]
    component["edges"] = [_edge("entry", "close")]
    graph["components"] = {"starter-close": {"revision": 1, "graph": component}}
    graph["nodes"] = [
        _node("start", "entry", "Start", "start", 40, 40),
        _node("open", "create_bin", "Create active bin", "start", 320, 40),
        _node("next", "entry", "Next item", "next", 40, 230),
        _node(
            "place",
            "place",
            "Place current item",
            "next",
            320,
            230,
            item="item",
            bin="active_bin",
            index="index",
        ),
        _node(
            "check",
            "condition",
            "Bin covered?",
            "next",
            610,
            230,
            expression="bin_load(active_bin) >= threshold",
        ),
        _node(
            "close",
            "component",
            "Close covered bin",
            "next",
            910,
            150,
            component_id="starter-close",
            inputs={},
            outputs={},
            params={},
        ),
        _node("done", "return", "Wait for next item", "next", 1210, 230),
        _node("stop", "entry", "Stop", "stop", 40, 450),
    ]
    graph["edges"] = [
        _edge("start", "open"),
        _edge("next", "place"),
        _edge("place", "check"),
        _edge("check", "close", "yes"),
        _edge("check", "done", "no"),
        _edge("close", "done"),
    ]
    return graph


def _offline():
    graph = _base(access="offline")
    graph.update(
        name="Sequence next fit",
        description="Access the whole sequence explicitly; iterate its immutable indices.",
    )
    graph["entries"] = {"start": "start", "process": "process", "stop": "stop"}
    graph["nodes"] = [
        _node("start", "entry", "Start", "start", 40, 40),
        _node("open", "create_bin", "Create active bin", "start", 320, 40),
        _node("process", "entry", "Process sequence", "process", 40, 230),
        _node(
            "items",
            "loop",
            "Each sequence index",
            "process",
            320,
            230,
            variable="i",
            values="range(len(sequence))",
        ),
        _node(
            "place",
            "place",
            "Place sequence item",
            "process",
            620,
            230,
            item="sequence[i]",
            bin="active_bin",
            index="i",
        ),
        _node(
            "check",
            "condition",
            "Bin covered?",
            "process",
            900,
            230,
            expression="bin_load(active_bin) >= threshold",
        ),
        _node(
            "close",
            "custom",
            "Close covered bin",
            "process",
            1190,
            130,
            notation="python",
            source="cover(active_bin)",
        ),
        _node("item_done", "return", "Next sequence index", "process", 1490, 230),
        _node("finished", "return", "Sequence processed", "process", 320, 450),
        _node("stop", "entry", "Stop", "stop", 40, 630),
    ]
    graph["edges"] = [
        _edge("start", "open"),
        _edge("process", "items"),
        _edge("items", "place", "body"),
        _edge("items", "finished"),
        _edge("place", "check"),
        _edge("check", "close", "yes"),
        _edge("check", "item_done", "no"),
        _edge("close", "item_done"),
    ]
    return graph


def _generator():
    graph = _base("generator")
    graph.update(
        name="Seeded uniform",
        description="Emit one bounded random item per generation step.",
    )
    graph["parameters"] = {
        "min_size": {"type": "number", "default": 0.1, "min": 0},
        "max_size": {"type": "number", "default": 0.9, "min": 0},
    }
    graph["entries"] = {"start": "start", "next": "next", "stop": "stop"}
    graph["nodes"] = [
        _node("start", "entry", "Start", "start", 40, 40),
        _node("next", "entry", "Generate next", "next", 40, 230),
        _node(
            "sample",
            "custom",
            "Sample and emit",
            "next",
            320,
            230,
            notation="python",
            source="emit(uniform(min_size, max_size))",
        ),
        _node("stop", "entry", "Stop", "stop", 40, 450),
    ]
    graph["edges"] = [_edge("next", "sample")]
    return graph


def _component():
    graph = _base("component")
    graph.update(
        name="Scale a value",
        description="A reusable component with explicit typed input/output and local state.",
    )
    graph["parameters"] = {"factor": {"type": "number", "default": 1}}
    graph["inputs"] = {"incoming": {"type": "number"}}
    graph["outputs"] = {"value": {"type": "number"}}
    graph["entries"] = {"process": "entry"}
    graph["nodes"] = [
        _node("entry", "entry", "Component input", "process", 40, 40),
        _node(
            "scale",
            "custom",
            "Scale value",
            "process",
            320,
            40,
            notation="python",
            source="value = incoming * factor",
        ),
    ]
    graph["edges"] = [_edge("entry", "scale")]
    return graph


def starter_templates():
    return [
        {
            "id": "online",
            "name": "Online next fit",
            "description": "Current-item access and a reusable close component",
            "graph": _online(),
        },
        {
            "id": "offline",
            "name": "Offline sequence",
            "description": "Whole-sequence access with a visual bounded loop",
            "graph": _offline(),
        },
        {
            "id": "generator",
            "name": "Seeded generator",
            "description": "Uniform items using the experiment's data seed",
            "graph": _generator(),
        },
        {
            "id": "component",
            "name": "Reusable component",
            "description": "Typed inputs/outputs with a configurable parameter",
            "graph": _component(),
        },
    ]


def get_template(name):
    for template in starter_templates():
        if template["id"] == name:
            return deepcopy(template["graph"])
    raise ValueError(f"Unknown builder template: {name}")


def examples():
    return [
        {
            "id": "condition",
            "name": "Close a covered bin",
            "kind": "algorithm",
            "requires": "Place the current item before this block; active_bin is runtime-managed.",
            "python": "if bin_load(active_bin) >= threshold:\n    cover(active_bin)",
            "pseudocode": "IF BIN_LOAD(active_bin) >= threshold THEN\n    COVER active_bin\nEND",
        },
        {
            "id": "state",
            "name": "Count processed items",
            "kind": "all",
            "requires": "Declare count = 0 in graph state, or initialize it in Start.",
            "python": "count += 1",
            "pseudocode": "ADD 1 TO count",
        },
        {
            "id": "choose",
            "name": "Choose an active bin",
            "kind": "algorithm",
            "requires": "Create at least one bin first. select_bin changes the runtime's active_bin.",
            "python": "select_bin(choice(active_bins()))",
            "pseudocode": "SELECT BIN CHOICE(ACTIVE_BINS())",
        },
        {
            "id": "uniform",
            "name": "Emit a seeded item",
            "kind": "generator",
            "requires": "Declare min_size and max_size parameters; float64 domain.",
            "python": "emit(uniform(min_size, max_size))",
            "pseudocode": "EMIT UNIFORM(min_size, max_size)",
        },
        {
            "id": "integer",
            "name": "Emit an integer item",
            "kind": "generator",
            "requires": "Set integer domain and integer min_size/max_size parameters.",
            "python": "emit(randint(min_size, max_size))",
            "pseudocode": "EMIT RANDINT(min_size, max_size)",
        },
        {
            "id": "offline",
            "name": "Process every sequence item",
            "kind": "algorithm",
            "requires": "Offline access and a bin created in Start. Immutable indices identify each input exactly once.",
            "python": "for i in range(len(sequence)):\n    place(sequence[i], active_bin, i)\n    if bin_load(active_bin) >= threshold:\n        cover(active_bin)",
            "pseudocode": "FOR i IN RANGE(LEN(sequence)) DO\n    CALL PLACE(sequence[i], active_bin, i)\n    IF BIN_LOAD(active_bin) >= threshold THEN\n        COVER active_bin\n    END\nEND",
        },
    ]


templates = starter_templates
