"""Authoritative, bounded interpreter and physically measured bin ledger.

The web process must call the isolated worker, not this module directly.  These
functions are also useful for offline exports and unit tests.  The interpreter is
one defense; the supervisor's container/resource limits are the outer boundary.
"""

from __future__ import annotations

import copy
import json
import math
import operator
import random

from .language import (
    MAX_LIST,
    READ_ONLY,
    BuilderError,
    parse_expression,
    parse_program,
)
from .schema import (
    RUNTIME_VERSION,
    check_type,
    graph_hash,
    port_types,
    resolve_parameters,
    validate_graph,
)

MAX_ITEMS = 200_000
MAX_STEPS = 2_000_000
MAX_TRACE_EVENTS = 10_000
MAX_TRACE_BYTES = 4 * 1024 * 1024
DEFAULT_TRACE_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_VALUES = 1000
MAX_BINS = 200_001
NUMERIC_OPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "//": operator.floordiv,
    "%": operator.mod,
    "**": operator.pow,
}
COMPARE_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}
PURE_HELPERS = {
    "abs",
    "min",
    "max",
    "sum",
    "len",
    "range",
    "int",
    "float",
    "round",
    "sorted",
    "reversed",
    "bin_load",
    "is_covered",
    "active_bins",
}


def _integer(value, description):
    if type(value) is not int:
        raise BuilderError(f"{description} must be an integer", code="invalid_value")
    return value


def _numeric(value, description="Value"):
    if (
        type(value) not in (int, float)
        or abs(value) > 1e100
        or not math.isfinite(value)
    ):
        raise BuilderError(
            f"{description} must be a finite number within the supported range",
            code="invalid_value",
        )
    return value


def _bounded(value, depth=0):
    if depth > 8:
        raise BuilderError(
            "State lists are limited to eight nested levels", code="resource_limit"
        )
    if type(value) in (int, float):
        return _numeric(value)
    if type(value) is bool:
        return value
    if isinstance(value, str) and len(value) <= 1024:
        return value
    if isinstance(value, (list, tuple)) and len(value) <= MAX_LIST:
        return [_bounded(v, depth + 1) for v in value]
    raise BuilderError(
        "State must use numbers, booleans, short text or bounded lists",
        code="resource_limit",
    )


class _LoopBreak(Exception):
    pass


class _LoopContinue(Exception):
    pass


class _Context:
    def __init__(self, graph, parameters, path=()):
        self.graph = graph
        self.path = path
        self.parameters = parameters
        self.state = {
            name: _bounded(copy.deepcopy(value))
            for name, value in graph["state"].items()
        }
        self.inputs = {}
        self.bindings = {}
        self.outputs = {}
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.edges = {
            (e["source"], e["port"]): e
            for e in graph["edges"]
            if e["kind"] == "control"
        }
        self.data_edges = {}
        for edge in graph["edges"]:
            if edge["kind"] == "data":
                self.data_edges.setdefault(edge["target"], []).append(edge)
        self.programs, self.expressions = {}, {}
        self.instances = {}
        for node in graph["nodes"]:
            if node["type"] == "custom":
                self.programs[node["id"]] = parse_program(
                    node["config"]["source"], node["config"]["notation"]
                )


class _Engine:
    def __init__(
        self,
        graph,
        items,
        seed,
        params,
        threshold,
        n,
        trace_limit,
        trace_bytes,
        state_limit,
        component_context,
    ):
        self.graph, self.items, self.threshold, self.n = graph, items, threshold, n
        if graph["kind"] == "algorithm":
            self.n = len(items)
        self.rng = random.Random(seed)
        self.component_context = component_context
        self.execution_kind = (
            component_context.get("kind", "algorithm")
            if graph["kind"] == "component"
            else graph["kind"]
        )
        self.root = _Context(graph, resolve_parameters(graph, params))
        self.current_context = self.root
        self.current_node = None
        self.phase, self.index, self.item = "start", -1, None
        self.active_bin = None
        self.bins = {}
        self.next_bin = 0
        self.consumed = [False] * len(items)
        self.discarded_indices = []
        self.covered = 0
        self.generated = []
        self.steps = 0
        self.trace_limit, self.trace_bytes, self.state_limit = (
            trace_limit,
            trace_bytes,
            state_limit,
        )
        self.trace = {
            "schema_version": 1,
            "events": [],
            "truncated": False,
            "event_limit": trace_limit,
            "byte_limit": trace_bytes,
            "snapshot_value_limit": state_limit,
            "total_events": 0,
        }
        self.trace_size = 0
        self.trace_stopped = False

    def tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise BuilderError(
                "Program exceeded the bounded operation budget", code="resource_limit"
            )

    def lookup(self, name, context):
        if name == "sequence":
            if (
                self.graph["access"] != "offline"
                or context.graph["access"] != "offline"
            ):
                raise BuilderError(
                    "The full sequence is available only to offline programs",
                    code="access_mode",
                )
            return self.items
        if name == "output":
            return tuple(self.generated)
        builtins = {
            "item": self.item,
            "index": self.index,
            "item_index": self.index,
            "threshold": self.threshold,
            "n": self.n,
            "active_bin": self.active_bin,
            "covered_bins": self.covered,
            "discarded_items": len(self.discarded_indices),
        }
        if name in builtins:
            if builtins[name] is None:
                raise BuilderError(
                    f"{name} is unavailable in this phase; create/select a bin or use Next item"
                )
            return builtins[name]
        if name == "params":
            return context.parameters
        for values in (
            context.bindings,
            context.inputs,
            context.parameters,
            context.state,
        ):
            if name in values:
                return values[name]
        raise BuilderError(f"Unknown variable: {name}", code="unknown_variable")

    def expr(self, expression, context, *, pure=False):
        self.tick()
        op = expression["op"]
        if op == "constant":
            return expression["value"]
        if op == "name":
            return self.lookup(expression["name"], context)
        if op == "list":
            return _bounded(
                [self.expr(e, context, pure=pure) for e in expression["values"]]
            )
        if op == "binary":
            return self.binary(
                expression["operator"],
                self.expr(expression["left"], context, pure=pure),
                self.expr(expression["right"], context, pure=pure),
            )
        if op == "unary":
            value = self.expr(expression["value"], context, pure=pure)
            if expression["operator"] == "not":
                return not value
            return (
                _numeric(value) if expression["operator"] == "+" else -_numeric(value)
            )
        if op == "boolean":
            value = None
            for entry in expression["values"]:
                value = self.expr(entry, context, pure=pure)
                if (
                    expression["operator"] == "and"
                    and not value
                    or expression["operator"] == "or"
                    and value
                ):
                    break
            return value
        if op == "compare":
            previous = self.expr(expression["values"][0], context, pure=pure)
            for operator_name, entry in zip(
                expression["operators"], expression["values"][1:], strict=True
            ):
                current = self.expr(entry, context, pure=pure)
                if not COMPARE_OPS[operator_name](previous, current):
                    return False
                previous = current
            return True
        if op == "select":
            field = (
                "yes"
                if self.expr(expression["condition"], context, pure=pure)
                else "no"
            )
            return self.expr(expression[field], context, pure=pure)
        if op == "index":
            values = self.expr(expression["value"], context, pure=pure)
            index = self.expr(expression["index"], context, pure=pure)
            if isinstance(values, dict):
                if not isinstance(index, str) or index not in values:
                    raise BuilderError("Unknown parameter key")
                return values[index]
            if not isinstance(values, (list, tuple, str)):
                raise BuilderError("Indexing requires a list or short text")
            _integer(index, "List index")
            try:
                return values[index]
            except IndexError as exc:
                raise BuilderError(
                    "List index is out of range", code="invalid_value"
                ) from exc
        if op == "call":
            name = expression["name"]
            if pure and name not in PURE_HELPERS:
                raise BuilderError(
                    f"{name} has side effects; use a Custom or operation node instead"
                )
            args = [self.expr(e, context, pure=pure) for e in expression["args"]]
            return self.helper(name, args, context)
        raise BuilderError("Unsupported expression representation")

    def binary(self, op, left, right):
        if op == "+" and isinstance(left, list) and isinstance(right, list):
            if len(left) + len(right) > MAX_LIST:
                raise BuilderError(
                    "List exceeds the bounded state limit", code="resource_limit"
                )
            return left + right
        _numeric(left)
        _numeric(right)
        if op == "**" and (abs(right) > 16 or type(right) is not int):
            raise BuilderError("Powers require an integer exponent between -16 and 16")
        return _numeric(NUMERIC_OPS[op](left, right))

    def assign(self, target, value, context):
        name = target["name"]
        if (
            name in READ_ONLY
            or name in context.parameters
            or name in context.inputs
            or name in context.bindings
        ):
            raise BuilderError(f"{name} is read-only")
        value = _bounded(value)
        if "index" in target:
            values = context.state.get(name)
            if not isinstance(values, list):
                raise BuilderError("Only state lists support element assignment")
            index = _integer(self.expr(target["index"], context), "List index")
            try:
                values[index] = value
            except IndexError as exc:
                raise BuilderError("List index is out of range") from exc
        else:
            if name not in context.state and len(context.state) >= 100:
                raise BuilderError(
                    "Programs are limited to 100 state variables", code="resource_limit"
                )
            context.state[name] = value

    def statements(self, entries, context):
        for entry in entries:
            self.tick()
            try:
                op = entry["op"]
                if op == "assign":
                    self.assign(
                        entry["target"], self.expr(entry["value"], context), context
                    )
                elif op == "augment":
                    target = entry["target"]
                    current = self.lookup(target["name"], context)
                    if "index" in target:
                        current = current[
                            _integer(self.expr(target["index"], context), "List index")
                        ]
                    self.assign(
                        target,
                        self.binary(
                            entry["operator"],
                            current,
                            self.expr(entry["value"], context),
                        ),
                        context,
                    )
                elif op == "expression":
                    self.expr(entry["value"], context)
                elif op == "if":
                    branch = bool(self.expr(entry["condition"], context))
                    self.record(
                        context,
                        line=entry["line"],
                        branch="yes" if branch else "no",
                        operation="custom_condition",
                    )
                    self.statements(entry["yes"] if branch else entry["no"], context)
                elif op == "for":
                    values = self.expr(entry["values"], context)
                    if not isinstance(values, (list, tuple)) or len(values) > MAX_ITEMS:
                        raise BuilderError("FOR requires a bounded list or RANGE")
                    for value in tuple(values):
                        self.assign(entry["target"], value, context)
                        try:
                            self.statements(entry["body"], context)
                        except _LoopBreak:
                            break
                        except _LoopContinue:
                            continue
                elif op == "break":
                    raise _LoopBreak
                elif op == "continue":
                    raise _LoopContinue
                self.record(
                    context, line=entry["line"], operation="statement", statement=op
                )
            except (
                BuilderError,
                ArithmeticError,
                LookupError,
                TypeError,
                ValueError,
            ) as exc:
                if not isinstance(exc, BuilderError):
                    exc = BuilderError(
                        f"Invalid operation: {type(exc).__name__}: {exc}",
                        code="execution_error",
                    )
                exc.line = exc.line or entry["line"]
                raise exc

    def helper(self, name, args, context):
        self.tick()
        if name in {"abs", "int", "float"}:
            if len(args) != 1:
                raise BuilderError(f"{name} needs one argument")
            _numeric(args[0])
            return _numeric({"abs": abs, "int": int, "float": float}[name](args[0]))
        if name == "round":
            if not 1 <= len(args) <= 2:
                raise BuilderError("round needs a value and optional decimal places")
            _numeric(args[0])
            if len(args) == 2 and abs(_integer(args[1], "Decimal places")) > 16:
                raise BuilderError("Decimal places must be between -16 and 16")
            return round(*args)
        if name in {"min", "max", "sum"}:
            values = (
                args[0]
                if len(args) == 1 and isinstance(args[0], (list, tuple))
                else args
            )
            if not values:
                if name == "sum":
                    return 0
                raise BuilderError(f"{name} needs at least one value")
            for value in values:
                _numeric(value)
            return _numeric({"min": min, "max": max, "sum": sum}[name](values))
        if name == "len":
            if len(args) != 1 or not isinstance(args[0], (list, tuple, str)):
                raise BuilderError("len needs one list or text value")
            return len(args[0])
        if name == "range":
            if not 1 <= len(args) <= 3:
                raise BuilderError("range needs one to three integers")
            values = range(*[_integer(v, "Range argument") for v in args])
            if len(values) > MAX_ITEMS:
                raise BuilderError(
                    "Range exceeds the bounded iteration limit", code="resource_limit"
                )
            return tuple(values)
        if name in {"sorted", "reversed"}:
            if (
                len(args) != 1
                or not isinstance(args[0], (list, tuple))
                or len(args[0]) > MAX_ITEMS
            ):
                raise BuilderError(f"{name} needs one bounded list")
            return sorted(args[0]) if name == "sorted" else list(reversed(args[0]))
        if name in {"append", "pop"}:
            if (
                not args
                or not isinstance(args[0], list)
                or not any(args[0] is v for v in context.state.values())
            ):
                raise BuilderError(f"{name} modifies a declared state list only")
            if name == "append":
                if len(args) != 2 or len(args[0]) >= MAX_LIST:
                    raise BuilderError(
                        "append needs a state list and value within the list limit"
                    )
                args[0].append(_bounded(args[1]))
                return len(args[0])
            if len(args) not in (1, 2):
                raise BuilderError("pop needs a state list and optional integer index")
            return args[0].pop(
                _integer(args[1], "List index") if len(args) == 2 else -1
            )
        if name in {"uniform", "randint"}:
            if len(args) != 2:
                raise BuilderError(f"{name} needs minimum and maximum")
            low, high = [_numeric(v) for v in args]
            if low > high:
                raise BuilderError("Random minimum exceeds maximum")
            value = (
                self.rng.uniform(low, high)
                if name == "uniform"
                else self.rng.randint(
                    _integer(low, "Minimum"), _integer(high, "Maximum")
                )
            )
            self.record(context, operation="random", helper=name, value=value)
            return value
        if name == "choice":
            if len(args) != 1 or not isinstance(args[0], (list, tuple)) or not args[0]:
                raise BuilderError("choice needs one nonempty bounded list")
            value = self.rng.choice(args[0])
            self.record(context, operation="random", helper=name, value=value)
            return value
        if name == "emit":
            if self.execution_kind != "generator":
                raise BuilderError("Only generators emit items")
            if len(args) != 1:
                raise BuilderError("emit needs exactly one item")
            value = self.validate_item(args[0])
            if len(self.generated) >= self.n:
                raise BuilderError(
                    "Generator emitted more than the requested item count"
                )
            self.generated.append(value)
            self.record(
                context,
                operation="emit",
                value=value,
                output_index=len(self.generated) - 1,
            )
            return value
        if self.execution_kind == "generator":
            raise BuilderError("Generators cannot use bin ledger operations")
        if name == "create_bin":
            if args:
                raise BuilderError("create_bin takes no arguments")
            if len(self.bins) >= MAX_BINS:
                raise BuilderError("Bin limit exceeded", code="resource_limit")
            bin_id = self.next_bin
            self.next_bin += 1
            self.bins[bin_id] = {
                "id": bin_id,
                "load": 0 if self.graph["domain"] == "integer" else 0.0,
                "status": "active",
                "item_indices": [],
            }
            self.active_bin = bin_id
            self.record(context, operation="create_bin", bin_id=bin_id)
            return bin_id
        if name == "active_bins":
            if args:
                raise BuilderError("active_bins takes no arguments")
            return [
                key for key, value in self.bins.items() if value["status"] == "active"
            ]
        if name == "select_bin":
            if len(args) != 1:
                raise BuilderError("select_bin needs one bin ID")
            selected = self.bin(args[0])
            if selected["status"] != "active":
                raise BuilderError("A covered bin cannot be selected")
            self.active_bin = selected["id"]
            self.record(context, operation="select_bin", bin_id=self.active_bin)
            return self.active_bin
        if name in {"bin_load", "is_covered"}:
            if len(args) > 1:
                raise BuilderError(f"{name} takes an optional bin ID")
            selected = self.bin(args[0] if args else self.active_bin)
            return (
                selected["load"]
                if name == "bin_load"
                else selected["load"] >= self.threshold
            )
        if name == "place":
            if len(args) > 3:
                raise BuilderError(
                    "place takes item, bin ID, and optional immutable input index"
                )
            value = args[0] if args else self.item
            bin_id = args[1] if len(args) > 1 else self.active_bin
            index = args[2] if len(args) > 2 else self.index
            self.validate_item(value)
            self.check_input(index, value)
            selected = self.bin(bin_id)
            if selected["status"] != "active":
                raise BuilderError(
                    "Cannot place an item into a closed bin", code="ledger_error"
                )
            before = selected["load"]
            selected["load"] += value
            _numeric(selected["load"], "Bin load")
            selected["item_indices"].append(index)
            self.consumed[index] = True
            if self.graph["access"] == "offline":
                self.index, self.item = index, value
            self.record(
                context,
                operation="place",
                bin_id=bin_id,
                input_index=index,
                value=value,
                load_before=before,
                load_after=selected["load"],
            )
            return selected["load"]
        if name == "cover":
            if len(args) > 1:
                raise BuilderError("cover takes an optional bin ID")
            selected = self.bin(args[0] if args else self.active_bin)
            if selected["status"] != "active" or selected["load"] < self.threshold:
                raise BuilderError(
                    "Only an active bin whose measured load reaches threshold can be covered",
                    code="ledger_error",
                )
            selected["status"] = "covered"
            self.covered += 1
            self.record(
                context, operation="cover", bin_id=selected["id"], load=selected["load"]
            )
            if selected["id"] == self.active_bin:
                self.helper("create_bin", [], context)
            return self.covered
        if name == "discard":
            if len(args) > 1:
                raise BuilderError("discard takes an optional immutable input index")
            index = args[0] if args else self.index
            self.check_input(index)
            self.consumed[index] = True
            self.discarded_indices.append(index)
            if self.graph["access"] == "offline":
                self.index, self.item = index, self.items[index]
            self.record(
                context, operation="discard", input_index=index, value=self.items[index]
            )
            return len(self.discarded_indices)
        raise BuilderError(f"Unsupported helper: {name}")

    def bin(self, bin_id):
        _integer(bin_id, "Bin ID")
        if bin_id not in self.bins:
            raise BuilderError(
                "Unknown bin ID; create a bin first", code="ledger_error"
            )
        return self.bins[bin_id]

    def check_input(self, index, value=None):
        _integer(index, "Input index")
        if not 0 <= index < len(self.items):
            raise BuilderError(
                "Input index is outside the immutable sequence", code="ledger_error"
            )
        if self.graph["access"] == "online" and index != self.index:
            raise BuilderError(
                "Online algorithms can place/discard only the current input",
                code="access_mode",
            )
        if self.consumed[index]:
            raise BuilderError(
                "Each input item can be placed or discarded exactly once",
                code="ledger_error",
            )
        if value is not None and (type(value) is bool or value != self.items[index]):
            raise BuilderError(
                "Item value differs from the indexed immutable input",
                code="ledger_error",
            )

    def validate_item(self, value):
        _numeric(value, "Item")
        if self.graph["domain"] == "integer":
            _integer(value, "Integer-domain item")
        if not 0 < value <= self.threshold:
            raise BuilderError(
                "Items must be finite and in (0, threshold]", code="invalid_item"
            )
        return value

    def expression(self, source, context, *, pure=False):
        if source not in context.expressions:
            context.expressions[source] = parse_expression(source)
        return self.expr(context.expressions[source], context, pure=pure)

    def config_value(self, node, field, context, input_port=None):
        if input_port and input_port in context.bindings:
            return context.bindings[input_port]
        return self.expression(node["config"][field], context)

    def component(self, node, context):
        config = node["config"]
        graph = context.graph["components"][config["component_id"]]["graph"]
        parameters = {
            name: self.expression(value, context) if isinstance(value, str) else value
            for name, value in config["params"].items()
        }
        parameters = resolve_parameters(graph, parameters)
        if node["id"] not in context.instances:
            context.instances[node["id"]] = _Context(
                graph, parameters, (*context.path, node["id"])
            )
        instance = context.instances[node["id"]]
        instance.parameters = parameters
        inputs = {}
        for name, definition in graph["inputs"].items():
            if name in context.bindings:
                value = context.bindings[name]
            elif name in config["inputs"]:
                value = self.expression(config["inputs"][name], context)
            elif "default" in definition:
                value = copy.deepcopy(definition["default"])
            else:
                raise BuilderError(f"Missing component input: {name}")
            inputs[name] = _bounded(copy.deepcopy(check_type(value, definition, name)))
        instance.inputs = inputs
        self.record(
            context,
            operation="component_enter",
            component_id=config["component_id"],
            component_revision=context.graph["components"][config["component_id"]][
                "revision"
            ],
        )
        self.run_path(graph["entries"]["process"], instance)
        outputs = {}
        for name, definition in graph["outputs"].items():
            value = self.lookup(name, instance)
            outputs[name] = _bounded(copy.deepcopy(check_type(value, definition, name)))
            if name in config["outputs"]:
                self.assign({"name": config["outputs"][name]}, value, context)
        self.current_context, self.current_node = context, node
        self.record(context, operation="component_exit", component_outputs=outputs)
        return outputs

    def run_path(self, node_id, context):
        while node_id:
            self.tick()
            node = context.nodes[node_id]
            self.current_context, self.current_node = context, node
            context.bindings = {}
            for edge in context.data_edges.get(node_id, []):
                values = context.outputs.get(edge["source"], {})
                if edge["source_port"] not in values:
                    raise BuilderError(
                        "Data source has not executed on this path",
                        node_id=node_id,
                        code="data_dependency",
                    )
                definition = port_types(node, context.graph)[edge["target_port"]]
                context.bindings[edge["target_port"]] = copy.deepcopy(
                    check_type(
                        values[edge["source_port"]], definition, edge["target_port"]
                    )
                )
            kind, config, port, output = node["type"], node["config"], "next", {}
            try:
                if kind == "return":
                    self.record(context, operation="return")
                    return
                if kind == "custom":
                    self.statements(context.programs[node_id], context)
                elif kind == "condition":
                    value = bool(
                        self.config_value(node, "expression", context, "value")
                    )
                    port = "yes" if value else "no"
                    output = {"value": value}
                elif kind == "loop":
                    values = self.config_value(node, "values", context)
                    if not isinstance(values, (list, tuple)) or len(values) > MAX_ITEMS:
                        raise BuilderError(
                            "Loop values must be a bounded list or RANGE"
                        )
                    body = context.edges[(node_id, "body")]
                    for loop_index, value in enumerate(tuple(values)):
                        self.assign({"name": config["variable"]}, value, context)
                        self.current_context, self.current_node = context, node
                        self.record(
                            context,
                            operation="loop_iteration",
                            loop_index=loop_index,
                            edge_id=body["id"],
                        )
                        self.run_path(body["target"], context)
                    self.current_context, self.current_node = context, node
                elif kind == "assign":
                    value = self.config_value(node, "expression", context, "value")
                    self.assign({"name": config["variable"]}, value, context)
                    output = {"value": value}
                elif kind == "create_bin":
                    value = self.helper("create_bin", [], context)
                    if config.get("variable"):
                        self.assign({"name": config["variable"]}, value, context)
                    output = {"bin": value, "value": value}
                elif kind == "select_bin":
                    self.helper(
                        "select_bin",
                        [self.config_value(node, "expression", context, "bin")],
                        context,
                    )
                elif kind == "place":
                    args = [
                        self.config_value(node, field, context, field)
                        for field in ("item", "bin", "index")
                    ]
                    load = self.helper("place", args, context)
                    output = {"load": load, "bin": args[1]}
                elif kind == "cover":
                    output = {
                        "covered": self.helper(
                            "cover",
                            [self.config_value(node, "bin", context, "bin")],
                            context,
                        )
                    }
                elif kind == "discard":
                    self.helper(
                        "discard",
                        [self.config_value(node, "index", context, "index")],
                        context,
                    )
                elif kind == "emit":
                    output = {
                        "value": self.helper(
                            "emit",
                            [self.config_value(node, "expression", context, "value")],
                            context,
                        )
                    }
                elif kind == "random":
                    args = [
                        self.config_value(node, field, context)
                        for field in ("min", "max")
                    ]
                    value = self.helper(
                        "randint" if config.get("integer") else "uniform", args, context
                    )
                    self.assign({"name": config["variable"]}, value, context)
                    output = {"value": value}
                elif kind == "component":
                    output = self.component(node, context)
                for name, source in config.get("exports", {}).items():
                    output[name] = _bounded(
                        copy.deepcopy(self.expression(source, context, pure=True))
                    )
                for name, definition in port_types(
                    node, context.graph, output=True
                ).items():
                    if name in output:
                        check_type(output[name], definition, name)
                context.outputs[node_id] = output
                edge = context.edges.get((node_id, port))
                self.record(
                    context,
                    operation="node",
                    branch=port if kind == "condition" else None,
                    edge_id=edge["id"] if edge else None,
                )
                node_id = edge["target"] if edge else None
            except BuilderError as exc:
                exc.node_id = exc.node_id or node["id"]
                raise

    def snapshot(self, context):
        remaining = self.state_limit
        truncated = False

        def value_snapshot(value, depth=0):
            nonlocal remaining, truncated
            if remaining <= 0 or depth > 4:
                truncated = True
                return {"omitted": True}
            remaining -= 1
            if isinstance(value, (list, tuple)):
                result = []
                for value_entry in value:
                    if remaining <= 0:
                        truncated = True
                        break
                    result.append(value_snapshot(value_entry, depth + 1))
                if len(result) < len(value):
                    result.append({"omitted_values": len(value) - len(result)})
                return result
            return value

        state = {name: value_snapshot(value) for name, value in context.state.items()}
        bins = []
        # Show the most recently touched ledger bins rather than a full unbounded
        # deep copy at every operation. Item history has its own bounded marker.
        for bin_id in list(self.bins)[-100:]:
            entry = self.bins[bin_id]
            indices = entry["item_indices"][-30:]
            bins.append(
                {
                    **entry,
                    "item_indices": indices,
                    "items_truncated": len(indices) < len(entry["item_indices"]),
                }
            )
        truncated = truncated or len(self.bins) > len(bins)
        return {
            "state": state,
            "bins": bins,
            "covered_bins": self.covered,
            "discarded_items": len(self.discarded_indices),
            "active_bin": self.active_bin,
            "output": self.generated[-30:],
            "output_truncated": len(self.generated) > 30,
            "snapshot_truncated": truncated,
        }

    def record(self, context, **details):
        self.trace["total_events"] += 1
        if not self.trace_limit:
            return
        if self.trace_stopped or len(self.trace["events"]) >= self.trace_limit:
            self.trace["truncated"] = True
            self.trace_stopped = True
            return
        node = self.current_node or {}
        event = {
            "step": self.trace["total_events"] - 1,
            "phase": self.phase,
            "node_id": node.get("id"),
            "node_type": node.get("type"),
            "label": node.get("label"),
            "call_path": list(context.path),
            "item_index": self.index if self.index >= 0 else None,
            "item": self.item,
            **details,
            **self.snapshot(context),
        }
        size = len(json.dumps(event, allow_nan=False, separators=(",", ":")).encode())
        if self.trace_size + size > self.trace_bytes:
            self.trace["truncated"] = True
            self.trace_stopped = True
            return
        self.trace_size += size
        self.trace["events"].append(event)

    def finish(self):
        if self.graph["kind"] == "generator":
            if len(self.generated) != self.n:
                raise BuilderError(
                    f"Generator emitted {len(self.generated)} items; requested {self.n}",
                    code="generator_count",
                )
            return {"items": self.generated}
        unconsumed = [i for i, used in enumerate(self.consumed) if not used]
        if unconsumed:
            raise BuilderError(
                f"{len(unconsumed)} input items were neither placed nor discarded (first index {unconsumed[0]})",
                code="ledger_error",
            )
        covered = [
            entry for entry in self.bins.values() if entry["status"] == "covered"
        ]
        active = [entry for entry in self.bins.values() if entry["status"] == "active"]
        total = (
            sum(self.items)
            if self.graph["domain"] == "integer"
            else math.fsum(self.items)
        )
        unfinished = (
            sum(entry["load"] for entry in active)
            if self.graph["domain"] == "integer"
            else math.fsum(entry["load"] for entry in active)
        )
        excess = (
            sum(entry["load"] - self.threshold for entry in covered)
            if self.graph["domain"] == "integer"
            else math.fsum(entry["load"] - self.threshold for entry in covered)
        )
        discarded = (
            sum(self.items[i] for i in self.discarded_indices)
            if self.graph["domain"] == "integer"
            else math.fsum(self.items[i] for i in self.discarded_indices)
        )
        useful = self.covered * self.threshold
        error = total - useful - excess - unfinished - discarded
        histogram = [0] * 20
        for entry in covered:
            ratio = (entry["load"] - self.threshold) / self.threshold
            histogram[min(19, max(0, int(ratio * 20)))] += 1
        return {
            "covered_bins": self.covered,
            "discarded_items": len(self.discarded_indices),
            "bin_statistics": {
                "schema_version": 1,
                "input_mass": total,
                "useful_mass": useful,
                "overshoot_mass": excess,
                "unfinished_mass": unfinished,
                "discarded_mass": discarded,
                "covered_bins": self.covered,
                "conservation_error": error,
                "conservation_ok": error == 0
                if self.graph["domain"] == "integer"
                else abs(error) <= 1e-9 * max(1, abs(total)),
                "overshoot_edges": [i / 20 for i in range(21)],
                "overshoot_counts": histogram,
                "load_unit": "fraction_of_covering_threshold",
            },
        }

    def run(self):
        if self.graph["kind"] == "component":
            if self.execution_kind == "algorithm":
                self.phase = "fixture"
                for indices in self.component_context.get("bins", []):
                    self.helper("create_bin", [], self.root)
                    for index in indices:
                        self.index, self.item = index, self.items[index]
                        self.helper(
                            "place", [self.item, self.active_bin, index], self.root
                        )
                self.index = self.component_context.get(
                    "current_index", len(self.items) - 1
                )
                self.item = self.items[self.index] if self.index >= 0 else None
            self.phase = "process"
            self.run_path(self.graph["entries"]["process"], self.root)
            result = {
                "outputs": {
                    name: check_type(self.lookup(name, self.root), definition, name)
                    for name, definition in self.graph["outputs"].items()
                }
            }
            if self.execution_kind == "generator":
                result["items"] = self.generated
            else:
                result.update(
                    covered_bins=self.covered,
                    discarded_items=len(self.discarded_indices),
                )
            return result
        self.run_path(self.graph["entries"]["start"], self.root)
        if self.graph["kind"] == "generator":
            self.phase = "next"
            # The generation lifecycle runs at most n times. Components may emit
            # a bounded pair at a time; stop as soon as exactly n are available.
            for index in range(self.n):
                if len(self.generated) >= self.n:
                    break
                self.index = index
                self.run_path(self.graph["entries"]["next"], self.root)
        elif self.graph["access"] == "offline":
            self.phase = "process"
            self.run_path(self.graph["entries"]["process"], self.root)
        else:
            self.phase = "next"
            for index, item in enumerate(self.items):
                self.index, self.item = index, item
                self.run_path(self.graph["entries"]["next"], self.root)
                if not self.consumed[index]:
                    raise BuilderError(
                        "Current input was neither placed nor discarded before advancing",
                        code="ledger_error",
                    )
        self.phase, self.index, self.item = "stop", -1, None
        self.run_path(self.graph["entries"]["stop"], self.root)
        return self.finish()


def execute(
    graph,
    items=None,
    seed=0,
    params=None,
    domain=None,
    threshold=1,
    n=10,
    trace_limit=1000,
    trace_bytes=DEFAULT_TRACE_BYTES,
    state_limit=256,
    inputs=None,
    component_context=None,
):
    """Execute one frozen trial and return finite bounded JSON, including errors."""
    engine = None
    response = {
        "ok": False,
        "runtime_version": RUNTIME_VERSION,
        "graph_hash": None,
        "result": None,
        "trace": {"schema_version": 1, "events": [], "truncated": False},
    }
    try:
        graph = validate_graph(graph)
        response["graph_hash"] = graph_hash(graph)
        if domain is not None and domain != graph["domain"]:
            raise BuilderError(
                "Requested domain differs from the frozen graph", code="domain_mismatch"
            )
        _integer(seed, "Seed")
        _integer(n, "Requested item count")
        if not 0 <= n <= MAX_ITEMS:
            raise BuilderError(
                f"Requested item count must be between 0 and {MAX_ITEMS}"
            )
        for name, value, maximum in (
            ("trace_limit", trace_limit, MAX_TRACE_EVENTS),
            ("trace_bytes", trace_bytes, MAX_TRACE_BYTES),
            ("state_limit", state_limit, MAX_SNAPSHOT_VALUES),
        ):
            _integer(value, name)
            if not 0 <= value <= maximum:
                raise BuilderError(f"{name} must be between 0 and {maximum}")
        _numeric(threshold, "Threshold")
        if threshold <= 0:
            raise BuilderError("Threshold must be positive")
        if graph["domain"] == "integer":
            _integer(threshold, "Integer-domain threshold")
        if items is None:
            items = []
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            raise BuilderError(f"Input must be a list of at most {MAX_ITEMS} items")
        component_context = {} if component_context is None else component_context
        if not isinstance(component_context, dict) or set(component_context) - {
            "kind",
            "bins",
            "current_index",
        }:
            raise BuilderError(
                "Component context supports kind, bins and current_index only"
            )
        if component_context and graph["kind"] != "component":
            raise BuilderError("Only component previews accept a fixture context")
        if component_context.get("kind", "algorithm") not in {"algorithm", "generator"}:
            raise BuilderError("Component fixture kind is algorithm or generator")
        if graph["kind"] == "component" and len(items) > MAX_LIST:
            raise BuilderError(
                "Component preview fixtures are limited to 10000 input items"
            )
        if "bins" in component_context:
            if (
                not isinstance(component_context["bins"], list)
                or len(component_context["bins"]) > 100
            ):
                raise BuilderError(
                    "Fixture bins must be arrays of input indices, with at most 100 bins"
                )
            indices = []
            for fixture_bin in component_context["bins"]:
                if not isinstance(fixture_bin, list):
                    raise BuilderError("Each fixture bin lists immutable input indices")
                for index in fixture_bin:
                    if type(index) is not int or not 0 <= index < len(items):
                        raise BuilderError(
                            "Fixture index is outside the immutable input"
                        )
                    indices.append(index)
            if len(indices) != len(set(indices)):
                raise BuilderError("Fixture bins cannot use an input twice")
        if "current_index" in component_context:
            current_index = _integer(
                component_context["current_index"], "Fixture current index"
            )
            if not -1 <= current_index < len(items):
                raise BuilderError(
                    "Fixture current index is outside the immutable input"
                )
        engine = _Engine(
            graph,
            items,
            seed,
            params if params is not None else {},
            threshold,
            n,
            trace_limit,
            trace_bytes,
            state_limit,
            component_context,
        )
        for item in items:
            engine.validate_item(item)
        if graph["kind"] == "component":
            inputs = {} if inputs is None else inputs
            if not isinstance(inputs, dict) or set(inputs) - set(graph["inputs"]):
                raise BuilderError(
                    "Component preview inputs must match declared input names"
                )
            for name, definition in graph["inputs"].items():
                if name in inputs:
                    value = inputs[name]
                elif "default" in definition:
                    value = copy.deepcopy(definition["default"])
                else:
                    raise BuilderError(
                        f"Reusable component preview needs a default for input {name}"
                    )
                engine.root.inputs[name] = _bounded(
                    copy.deepcopy(check_type(value, definition, name))
                )
        elif inputs:
            raise BuilderError("Only component previews accept explicit typed inputs")
        result = engine.run()
        response.update(
            ok=True,
            result=result,
            trace=engine.trace,
            execution={
                "operations": engine.steps,
                "trace_bytes": engine.trace_size,
                "component_fixture": component_context
                if graph["kind"] == "component"
                else None,
                "timing_scope": "restricted graph interpreter including bounded trace collection",
            },
        )
    except (
        BuilderError,
        ArithmeticError,
        LookupError,
        TypeError,
        ValueError,
        RecursionError,
    ) as exc:
        if not isinstance(exc, BuilderError):
            exc = BuilderError(
                f"Invalid operation: {type(exc).__name__}: {exc}",
                code="execution_error",
            )
        if engine:
            exc.node_id = exc.node_id or (engine.current_node or {}).get("id")
            engine.record(
                engine.current_context, operation="error", error=exc.as_dict()
            )
            response["trace"] = engine.trace
        response["error"] = exc.as_dict()
    return response
