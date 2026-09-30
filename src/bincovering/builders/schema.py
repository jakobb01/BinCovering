"""Versioned visual programs and validation of frozen component dependencies."""

from __future__ import annotations

import copy
import hashlib
import json
import math

from .language import (
    READ_ONLY,
    BuilderError,
    identifier,
    notation_name,
    parse_expression,
    parse_program,
)

SCHEMA_VERSION = 1
RUNTIME_VERSION = "1"
MAX_NODES = 300
MAX_EDGES = 1500
MAX_COMPONENTS = 100
MAX_GRAPH_BYTES = 1_000_000
TYPES = {"number", "integer", "boolean", "list", "bin", "text", "any"}
NODE_TYPES = {
    "entry",
    "return",
    "custom",
    "condition",
    "loop",
    "assign",
    "create_bin",
    "select_bin",
    "place",
    "cover",
    "discard",
    "emit",
    "random",
    "component",
}
NODE_INPUTS = {
    "place": {"item": "number", "bin": "bin", "index": "integer"},
    "cover": {"bin": "bin"},
    "select_bin": {"bin": "bin"},
    "discard": {"index": "integer"},
    "emit": {"value": "number"},
    "condition": {"value": "boolean"},
    "assign": {"value": "any"},
}
NODE_OUTPUTS = {
    "create_bin": {"bin": "bin", "value": "bin"},
    "assign": {"value": "any"},
    "random": {"value": "number"},
    "condition": {"value": "boolean"},
    "place": {"load": "number", "bin": "bin"},
    "cover": {"covered": "integer"},
    "emit": {"value": "number"},
}


def _fail(message, node_id=None):
    raise BuilderError(message, node_id=node_id, code="invalid_graph")


def _json_copy(value):
    try:
        serialized = json.dumps(value, allow_nan=False, separators=(",", ":"))
        if len(serialized.encode()) > MAX_GRAPH_BYTES:
            _fail("Graph exceeds the 1 MB import limit")
        return json.loads(serialized)
    except (ValueError, TypeError, RecursionError) as exc:
        _fail(f"Graph must contain finite JSON values: {exc}")


def _definitions(value, *, state=False):
    if not isinstance(value, dict) or len(value) > 100:
        _fail("Declarations must be an object with at most 100 names")
    for name, definition in value.items():
        identifier(name)
        if name in READ_ONLY:
            _fail(
                f"{name} is managed by the runtime; choose a different declaration name"
            )
        if state:
            continue
        if (
            not isinstance(definition, dict)
            or definition.get("type", "number") not in TYPES
        ):
            _fail(f"Invalid typed declaration for {name}")
        definition.setdefault("type", "number")
        for bound in ("min", "max"):
            if bound in definition:
                value = definition[bound]
                if (
                    definition["type"] not in {"number", "integer", "bin"}
                    or type(value) not in (int, float)
                    or abs(value) > 1e100
                    or not math.isfinite(value)
                ):
                    _fail(f"{bound} for {name} must be a finite numeric bound")
        if (
            "min" in definition
            and "max" in definition
            and definition["min"] > definition["max"]
        ):
            _fail(f"Minimum exceeds maximum for {name}")
    return value


def check_type(value, definition, name="value"):
    """Validate primitive typed values without integer/float domain coercion."""
    kind = (
        definition.get("type", "number") if isinstance(definition, dict) else definition
    )
    finite_number = (
        type(value) in (int, float) and abs(value) <= 1e100 and math.isfinite(value)
    )
    valid = {
        "number": finite_number,
        "integer": type(value) is int and finite_number,
        "bin": type(value) is int and value >= 0 and finite_number,
        "boolean": type(value) is bool,
        "list": isinstance(value, list) and len(value) <= 10_000,
        "text": isinstance(value, str) and len(value) <= 1024,
        "any": value is not None,
    }.get(kind, False)
    if not valid:
        _fail(f"{name} requires {kind}")
    if isinstance(definition, dict):
        if "min" in definition and value < definition["min"]:
            _fail(f"{name} must be at least {definition['min']}")
        if "max" in definition and value > definition["max"]:
            _fail(f"{name} must be at most {definition['max']}")
    return value


def resolve_parameters(graph, values=None):
    values = {} if values is None else values
    if not isinstance(values, dict):
        _fail("Parameters must be an object")
    definitions = graph.get("parameters", {})
    unknown = set(values) - set(definitions)
    if unknown:
        _fail("Unknown parameters: " + ", ".join(sorted(unknown)))
    resolved = {}
    for name, definition in definitions.items():
        if name in values:
            value = values[name]
        elif "default" in definition:
            value = copy.deepcopy(definition["default"])
        else:
            _fail(f"Missing parameter: {name}")
        resolved[name] = check_type(value, definition, name)
    return resolved


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _port_definitions(node, graph, output=False):
    defaults = NODE_OUTPUTS if output else NODE_INPUTS
    ports = dict(defaults.get(node["type"], {}))
    field = "outputs" if output else "inputs"
    if output:
        ports.update({name: "any" for name in node["config"].get("exports", {})})
    declared = node.get(field, {})
    if not isinstance(declared, dict):
        _fail(f"Node {field} must be typed objects", node["id"])
    for name, definition in declared.items():
        identifier(name)
        kind = (
            definition.get("type", "any")
            if isinstance(definition, dict)
            else definition
        )
        if kind not in TYPES:
            _fail(f"Unknown port type for {name}", node["id"])
        ports[name] = kind
    if node["type"] == "component":
        component = graph["components"][node["config"]["component_id"]]["graph"]
        ports.update(
            {name: d.get("type", "any") for name, d in component[field].items()}
        )
    return ports


def port_types(node, graph, output=False):
    return _port_definitions(node, graph, output)


def _validate_node_config(node, graph):
    config, kind = node["config"], node["type"]
    expr_fields = {
        "condition": {"expression": "False"},
        "loop": {"values": "[]"},
        "assign": {"expression": "0"},
        "select_bin": {"expression": "active_bin"},
        "place": {"item": "item", "bin": "active_bin", "index": "index"},
        "cover": {"bin": "active_bin"},
        "discard": {"index": "index"},
        "emit": {"expression": "item"},
        "random": {"min": "0", "max": "1"},
    }
    programs = []
    if kind == "custom":
        config.setdefault("source", "")
        config["notation"] = notation_name(
            config.get("notation", config.get("language", "python"))
        )
        programs.append(parse_program(config["source"], config["notation"]))
    if kind in {"assign", "loop", "random"}:
        variable = config.setdefault("variable", "value" if kind != "loop" else "i")
        identifier(variable)
        if variable in READ_ONLY:
            _fail(f"{variable} is managed by the runtime", node["id"])
    if kind == "create_bin" and config.get("variable"):
        variable = identifier(config["variable"])
        if variable in READ_ONLY:
            _fail(f"{variable} is managed by the runtime", node["id"])
    for field, default in expr_fields.get(kind, {}).items():
        config.setdefault(field, default)
        programs.append(parse_expression(config[field]))
    for field in ("exports",):
        values = config.get(field, {})
        if not isinstance(values, dict):
            _fail(f"{field} must map names to expressions", node["id"])
        for name, source in values.items():
            identifier(name)
            programs.append(parse_expression(source))
    if kind == "component":
        component_id = config.get("component_id")
        if component_id not in graph["components"]:
            _fail(f"Missing frozen component: {component_id}", node["id"])
        component = graph["components"][component_id]["graph"]
        if graph["access"] == "online" and component["access"] == "offline":
            _fail(
                "An offline component cannot be used by an online program", node["id"]
            )
        for field in ("inputs", "outputs", "params"):
            config.setdefault(field, {})
            if not isinstance(config[field], dict):
                _fail(f"Component {field} must be an object", node["id"])
        if set(config["inputs"]) - set(component["inputs"]):
            _fail("Unknown component input", node["id"])
        if set(config["outputs"]) - set(component["outputs"]):
            _fail("Unknown component output", node["id"])
        for source in config["inputs"].values():
            programs.append(parse_expression(source))
        for target in config["outputs"].values():
            identifier(target)
            if target in READ_ONLY:
                _fail(f"Cannot write managed value {target}", node["id"])
        for name, source in config["params"].items():
            if name not in component["parameters"]:
                _fail(f"Unknown component parameter: {name}", node["id"])
            programs.append(
                parse_expression(source)
                if isinstance(source, str)
                else {"op": "constant", "value": source}
            )
    for program in programs:
        for expression in _walk(program):
            if (
                graph["access"] == "online"
                and expression.get("op") == "name"
                and expression.get("name") == "sequence"
            ):
                _fail(
                    "Online programs cannot access the full sequence; choose offline access",
                    node["id"],
                )
            if (
                graph["kind"] == "algorithm"
                and expression.get("op") == "call"
                and expression.get("name") == "emit"
            ):
                _fail(
                    "Algorithms place or discard input items; emit is for generators",
                    node["id"],
                )
    if graph["kind"] == "algorithm" and kind == "emit":
        _fail("Emit nodes are for generators", node["id"])
    if graph["kind"] == "generator" and kind in {
        "place",
        "cover",
        "discard",
        "create_bin",
        "select_bin",
    }:
        _fail("Bin operations are for algorithms", node["id"])


def _validate_graph(raw, _depth=0, _ancestors=()):
    """Normalize a complete graph or raise a located ``BuilderError``.

    Draft saving does not call this function: incomplete drafts remain editable.
    Reusable graphs are frozen inline, so archived definitions cannot alter runs.
    """
    if _depth > 8:
        _fail("Reusable component nesting is limited to eight levels")
    if not isinstance(raw, dict):
        _fail("Graph must be an object")
    graph = _json_copy(raw)
    if graph.get("schema_version", 1) != SCHEMA_VERSION:
        _fail("Unsupported graph schema version")
    graph["schema_version"] = SCHEMA_VERSION
    graph.setdefault("kind", "algorithm")
    graph.setdefault("access", "online")
    graph.setdefault("domain", "float64")
    if graph["kind"] not in {"algorithm", "generator", "component"}:
        _fail("Choose algorithm, generator or component")
    if graph["access"] not in {"online", "offline"}:
        _fail("Choose online or offline access")
    if graph["domain"] not in {"float64", "integer"}:
        _fail("Choose float64 or integer numerical domain")
    if graph["kind"] == "generator" and graph["access"] != "online":
        _fail("Generators use Start / Generate next / Stop lifecycle")
    for field in ("parameters", "inputs", "outputs", "state"):
        graph.setdefault(field, {})
        _definitions(graph[field], state=field == "state")
    overlap = (set(graph["parameters"]) & set(graph["state"])) | (
        set(graph["inputs"]) & set(graph["state"])
    )
    if overlap:
        _fail(f"Declaration names overlap: {', '.join(sorted(overlap))}")
    components = graph.setdefault("components", {})
    if not isinstance(components, dict) or len(components) > MAX_COMPONENTS:
        _fail("Components must be an object with at most 100 definitions")
    for component_id, component in components.items():
        if component_id in _ancestors:
            _fail("Recursive reusable components are not allowed")
        if not isinstance(component, dict) or "graph" not in component:
            _fail("Component definitions need a frozen graph and revision")
        component.setdefault("revision", 1)
        if type(component["revision"]) is not int or component["revision"] < 1:
            _fail("Component revisions are positive integers")
        component["graph"] = validate_graph(
            component["graph"], _depth + 1, (*_ancestors, component_id)
        )
        if component["graph"]["kind"] != "component":
            _fail("Reusable definitions must have kind component")
    nodes = graph.get("nodes")
    edges = graph.setdefault("edges", [])
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        _fail(f"Graphs need between 1 and {MAX_NODES} nodes")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        _fail(f"Graphs are limited to {MAX_EDGES} edges")
    by_id = {}
    for node in nodes:
        if (
            not isinstance(node, dict)
            or not isinstance(node.get("id"), str)
            or not node["id"]
            or len(node["id"]) > 100
        ):
            _fail("Each node needs a short unique ID")
        if node["id"] in by_id:
            _fail("Duplicate node ID", node["id"])
        if node.get("type") not in NODE_TYPES:
            _fail(f"Unknown node type: {node.get('type')}", node["id"])
        by_id[node["id"]] = node
        node.setdefault("label", node["type"].replace("_", " ").title())
        node.setdefault("config", {})
        if not isinstance(node["config"], dict):
            _fail("Node config must be an object", node["id"])
        for coordinate in ("x", "y"):
            node.setdefault(coordinate, 0)
            if not isinstance(node[coordinate], (int, float)) or not math.isfinite(
                node[coordinate]
            ):
                _fail("Node position must be finite", node["id"])
        try:
            _validate_node_config(node, graph)
        except BuilderError as exc:
            exc.node_id = exc.node_id or node["id"]
            raise
    required = (
        {"process"}
        if graph["kind"] == "component"
        else {"start", "stop", "process" if graph["access"] == "offline" else "next"}
    )
    entries = graph.get("entries", {})
    if not isinstance(entries, dict) or set(entries) != required:
        _fail("Lifecycle entries must be " + ", ".join(sorted(required)))
    for phase, entry_id in entries.items():
        if entry_id not in by_id or by_id[entry_id]["type"] != "entry":
            _fail(f"Missing {phase} lifecycle entry", entry_id)
        by_id[entry_id]["phase"] = phase
    if len(set(entries.values())) != len(entries):
        _fail("Each lifecycle phase needs its own entry")
    edge_ids, outgoing, adjacency = set(), {}, {node: [] for node in by_id}
    for ordinal, edge in enumerate(edges):
        if not isinstance(edge, dict):
            _fail("Edges must be objects")
        edge.setdefault("id", f"edge-{ordinal}")
        if not isinstance(edge["id"], str) or edge["id"] in edge_ids:
            _fail("Each connection needs a unique ID")
        edge_ids.add(edge["id"])
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id:
            _fail("Connection references a missing node", source)
        edge.setdefault("kind", "control")
        edge.setdefault("port", "next")
        if not isinstance(edge["port"], str):
            _fail("Execution port must be a name", source)
        if edge["kind"] == "control":
            allowed = (
                {"yes", "no"}
                if by_id[source]["type"] == "condition"
                else {"body", "next"}
                if by_id[source]["type"] == "loop"
                else {"next"}
            )
            if by_id[source]["type"] == "return" or edge["port"] not in allowed:
                _fail("Invalid execution port", source)
            if by_id[target]["type"] == "entry":
                _fail("Execution cannot connect into a lifecycle entry", target)
            key = (source, edge["port"])
            if key in outgoing:
                _fail("An execution port has one outgoing connection", source)
            outgoing[key] = edge
            adjacency[source].append(target)
        elif edge["kind"] == "data":
            source_port = edge.setdefault("source_port", "value")
            target_port = edge.setdefault("target_port", "value")
            source_ports = _port_definitions(by_id[source], graph, output=True)
            target_ports = _port_definitions(by_id[target], graph)
            if source_port not in source_ports or target_port not in target_ports:
                _fail("Data edge references an undeclared typed port", target)
            left, right = source_ports[source_port], target_ports[target_port]
            if (
                left != right
                and "any" not in (left, right)
                and not (left == "integer" and right == "number")
            ):
                _fail(f"Cannot connect {left} output to {right} input", target)
            key = (target, "data:" + target_port)
            if key in outgoing:
                _fail("A data input has one source", target)
            outgoing[key] = edge
        else:
            _fail("Connection kind must be control or data", source)

    def visit(node_id, visiting, visited):
        if node_id in visiting:
            _fail("Execution cycles are not allowed; use a bounded Loop node", node_id)
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in adjacency[node_id]:
            visit(target, visiting, visited)
        visiting.remove(node_id)
        visited.add(node_id)

    visited = set()
    for node_id in by_id:
        visit(node_id, set(), visited)
    phases = {}

    def assign_phase(node_id, phase):
        if node_id in phases:
            if phases[node_id] != phase:
                _fail("An operation cannot belong to two lifecycle phases", node_id)
            return
        phases[node_id] = phase
        by_id[node_id]["phase"] = phase
        for target in adjacency[node_id]:
            assign_phase(target, phase)

    for phase, entry_id in entries.items():
        assign_phase(entry_id, phase)
    for node in nodes:
        if node["id"] not in phases:
            _fail("Operation is disconnected from its lifecycle entry", node["id"])
        if node["type"] == "condition" and any(
            (node["id"], p) not in outgoing for p in ("yes", "no")
        ):
            _fail("Condition needs both Yes and No execution paths", node["id"])
        if node["type"] == "loop" and (node["id"], "body") not in outgoing:
            _fail("Loop needs a body execution path", node["id"])
    # A data source must run on every path to its consumer. This prevents using
    # stale values from a previous item or an untaken condition branch.
    parents = {node_id: set() for node_id in by_id}
    for source, targets in adjacency.items():
        for target in targets:
            parents[target].add(source)
    dominators = {}
    for phase, entry_id in entries.items():
        phase_nodes = {node_id for node_id, value in phases.items() if value == phase}
        phase_dom = {
            node_id: {entry_id} if node_id == entry_id else set(phase_nodes)
            for node_id in phase_nodes
        }
        changed = True
        while changed:
            changed = False
            for node_id in phase_nodes - {entry_id}:
                predecessors = parents[node_id]
                common = (
                    set.intersection(*(phase_dom[p] for p in predecessors))
                    if predecessors
                    else set()
                )
                value = {node_id} | common
                if value != phase_dom[node_id]:
                    phase_dom[node_id] = value
                    changed = True
        dominators.update(phase_dom)
    for edge in edges:
        if edge["kind"] == "data":
            source, target = edge["source"], edge["target"]
            if phases[source] != phases[target]:
                _fail(
                    "Data connections stay within a lifecycle phase; use state for values across phases",
                    target,
                )
            if source == target or source not in dominators[target]:
                _fail(
                    "A data source must execute before its consumer on every path",
                    target,
                )

    def reachable(node_id):
        result = set()
        pending = [node_id]
        while pending:
            node_id = pending.pop()
            if node_id not in result:
                result.add(node_id)
                pending.extend(adjacency[node_id])
        return result

    for node in nodes:
        if node["type"] == "loop" and (node["id"], "next") in outgoing:
            body_nodes = reachable(outgoing[(node["id"], "body")]["target"])
            after_nodes = reachable(outgoing[(node["id"], "next")]["target"])
            if body_nodes & after_nodes:
                _fail(
                    "Loop body and after-loop paths must end separately; use Return in the body",
                    node["id"],
                )
    return graph


def validate_graph(raw, _depth=0, _ancestors=()):
    """Return a normalized graph; malformed JSON always has a structured error."""
    try:
        return _validate_graph(raw, _depth, _ancestors)
    except BuilderError:
        raise
    except (TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        raise BuilderError(f"Malformed graph: {exc}", code="invalid_graph") from exc


def _execution_graph(graph):
    result = copy.deepcopy(graph)
    for key in ("name", "description", "ui", "preview", "draft_id", "updated_at"):
        result.pop(key, None)
    result["nodes"] = sorted(result["nodes"], key=lambda n: n["id"])
    result["edges"] = sorted(
        result["edges"],
        key=lambda e: (
            e["kind"],
            e["source"],
            e.get("port", ""),
            e["target"],
            e.get("source_port", ""),
            e.get("target_port", ""),
        ),
    )
    for node in result["nodes"]:
        for key in ("x", "y", "label", "selected", "width", "height"):
            node.pop(key, None)
        if node["type"] == "custom":
            config = node["config"]
            program = parse_program(config["source"], config["notation"])
            for entry in _walk(program):
                entry.pop("line", None)
            config.pop("source", None)
            config.pop("notation", None)
            config.pop("language", None)
            config["program"] = program
    for edge in result["edges"]:
        edge.pop("id", None)
    for component in result["components"].values():
        component["graph"] = _execution_graph(component["graph"])
    return result


def graph_hash(graph):
    """Content identity excludes layout and equivalent notation spelling."""
    normalized = _execution_graph(validate_graph(graph))
    return hashlib.sha256(
        json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def generated_source(graph):
    """Export readable frozen data and a small adapter; no user source is exec'd."""
    normalized = validate_graph(graph)
    payload = json.dumps(normalized, sort_keys=True, indent=2, allow_nan=False)
    return (
        '"""Frozen visual program. Requires bincovering builder runtime API 1.\n'
        'The graph and Custom statements remain inspectable below.\n"""\n'
        "import json\nfrom bincovering.builders.runtime import execute, RUNTIME_VERSION\n\n"
        + "GRAPH = json.loads("
        + repr(payload)
        + ")\n\n"
        + "def run(items=None, seed=0, params=None, threshold=1, n=10, trace_limit=0, inputs=None, component_context=None):\n"
        + "    if RUNTIME_VERSION != '1':\n"
        + "        raise RuntimeError('Frozen program requires builder runtime API 1')\n"
        + "    return execute(GRAPH, items=items or [], seed=seed, params=params or {},\n"
        + "                   threshold=threshold, n=n, trace_limit=trace_limit,\n"
        + "                   inputs=inputs, component_context=component_context)\n"
    )
