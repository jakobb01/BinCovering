"""A small, deterministic language. Parsing never executes user Python.

Both UI notations lower to a JSON-compatible representation interpreted by
``runtime.py``.  The allowlist is deliberately independent of Python's evaluator.
"""

from __future__ import annotations

import ast
import math
import re

MAX_SOURCE = 32_000
MAX_AST_NODES = 4_000
MAX_LIST = 10_000
HELPERS = frozenset(
    {
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
        "append",
        "pop",
        "uniform",
        "randint",
        "choice",
        "create_bin",
        "select_bin",
        "active_bins",
        "bin_load",
        "is_covered",
        "place",
        "cover",
        "discard",
        "emit",
    }
)
READ_ONLY = frozenset(
    {
        "item",
        "index",
        "item_index",
        "sequence",
        "threshold",
        "n",
        "covered_bins",
        "discarded_items",
        "output",
        "params",
        "active_bin",
    }
)
OPERATORS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.In: "in",
    ast.NotIn: "not in",
}
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


class BuilderError(ValueError):
    """A user-facing validation/execution failure with a source location."""

    def __init__(self, message, *, node_id=None, line=None, code="invalid_program"):
        super().__init__(message)
        self.message, self.node_id, self.line, self.code = message, node_id, line, code

    def as_dict(self):
        return {
            "message": self.message,
            "node_id": self.node_id,
            "line": self.line,
            "code": self.code,
        }


def identifier(name):
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in HELPERS:
        raise BuilderError(f"Invalid variable name: {name!r}")
    return name


def notation_name(value):
    aliases = {
        "python": "python",
        "simple_python": "python",
        "simple-python": "python",
        "pseudocode": "pseudocode",
        "pseudo": "pseudocode",
    }
    try:
        return aliases[value.lower()]
    except (AttributeError, KeyError) as exc:
        raise BuilderError("Choose Simple Python or defined pseudocode") from exc


def _pseudo_expression(source):
    # These tokens are reserved in the documented notation. Quoted strings retain
    # their contents; substitution only applies outside quotes.
    parts = re.split(r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", source)
    aliases = {name.upper(): name for name in HELPERS}
    aliases.update(
        {
            "TRUE": "True",
            "FALSE": "False",
            "AND": "and",
            "OR": "or",
            "NOT": "not",
            "IN": "in",
        }
    )
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\b[A-Z_]+\b", lambda m: aliases.get(m[0], m[0]), parts[i])
    return "".join(parts)


def _pseudocode_to_python(source):
    result, line_map, stack = [], {}, []
    indent = 0
    for line_no, original in enumerate(source.splitlines(), 1):
        text = original.strip()
        if not text or text.startswith("#"):
            continue
        upper = text.upper()
        if upper == "END":
            if not stack:
                raise BuilderError("END has no matching IF or FOR", line=line_no)
            indent -= 1
            stack.pop()
            continue
        if upper == "ELSE" or upper.startswith("ELSE IF "):
            if not stack or stack[-1] != "if":
                raise BuilderError("ELSE has no matching IF", line=line_no)
            indent -= 1
            if upper == "ELSE":
                code = "else:"
            elif upper.endswith(" THEN"):
                code = "elif " + _pseudo_expression(text[8:-5]) + ":"
            else:
                raise BuilderError("Use ELSE IF condition THEN", line=line_no)
            result.append("    " * indent + code)
            line_map[len(result)] = line_no
            indent += 1
            continue
        if upper.startswith("IF ") and upper.endswith(" THEN"):
            code = "if " + _pseudo_expression(text[3:-5]) + ":"
            block = "if"
        elif upper.startswith("FOR ") and upper.endswith(" DO"):
            body = text[4:-3]
            match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)\s+IN\s+(.+)", body, re.I)
            if not match:
                raise BuilderError("Use FOR variable IN values DO", line=line_no)
            code = f"for {match[1]} in {_pseudo_expression(match[2])}:"
            block = "for"
        else:
            block = None
            if upper.startswith("SET "):
                code = _pseudo_expression(text[4:])
            elif upper.startswith("ADD "):
                match = re.fullmatch(r"ADD (.+) TO ([A-Za-z][A-Za-z0-9_]*)", text, re.I)
                if not match:
                    raise BuilderError("Use ADD expression TO variable", line=line_no)
                code = f"{match[2]} += {_pseudo_expression(match[1])}"
            elif upper.startswith("EMIT "):
                code = f"emit({_pseudo_expression(text[5:])})"
            elif upper == "COVER" or upper == "CLOSE BIN":
                code = "cover()"
            elif upper.startswith("COVER "):
                code = f"cover({_pseudo_expression(text[6:])})"
            elif upper == "DISCARD":
                code = "discard()"
            elif upper.startswith("DISCARD "):
                code = f"discard({_pseudo_expression(text[8:])})"
            elif upper.startswith("CREATE BIN AS "):
                code = f"{text[14:]} = create_bin()"
            elif upper.startswith("SELECT BIN "):
                code = f"select_bin({_pseudo_expression(text[11:])})"
            elif upper.startswith("CALL "):
                code = _pseudo_expression(text[5:])
            elif upper in {"BREAK", "CONTINUE", "PASS"}:
                code = upper.lower()
            else:
                raise BuilderError(
                    "Use SET, IF, FOR, CALL, COVER, DISCARD or EMIT; prose is not executable",
                    line=line_no,
                )
        result.append("    " * indent + code)
        line_map[len(result)] = line_no
        if block:
            stack.append(block)
            indent += 1
    if stack:
        raise BuilderError("Missing END for IF or FOR", line=len(source.splitlines()))
    return "\n".join(result), line_map


def _expression(node):
    line = getattr(node, "lineno", None)
    if isinstance(node, ast.Constant):
        value = node.value
        if not isinstance(value, (str, bool, int, float)) or value is None:
            raise BuilderError(
                "Only numbers, booleans and short text constants are supported",
                line=line,
            )
        if isinstance(value, str) and len(value) > 1024:
            raise BuilderError(
                "Text constants are limited to 1024 characters", line=line
            )
        if isinstance(value, (int, float)) and (
            abs(value) > 1e100 or not math.isfinite(value)
        ):
            raise BuilderError(
                "Numeric constant exceeds the supported range", line=line
            )
        return {"op": "constant", "value": value}
    if isinstance(node, ast.Name):
        identifier(node.id)
        return {"op": "name", "name": node.id}
    if isinstance(node, (ast.List, ast.Tuple)):
        return {"op": "list", "values": [_expression(n) for n in node.elts]}
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return {
            "op": "binary",
            "operator": OPERATORS[type(node.op)],
            "left": _expression(node.left),
            "right": _expression(node.right),
        }
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub, ast.Not)
    ):
        return {
            "op": "unary",
            "operator": {ast.UAdd: "+", ast.USub: "-", ast.Not: "not"}[type(node.op)],
            "value": _expression(node.operand),
        }
    if isinstance(node, ast.BoolOp):
        return {
            "op": "boolean",
            "operator": "and" if isinstance(node.op, ast.And) else "or",
            "values": [_expression(n) for n in node.values],
        }
    if isinstance(node, ast.Compare) and all(type(n) in OPERATORS for n in node.ops):
        return {
            "op": "compare",
            "operators": [OPERATORS[type(n)] for n in node.ops],
            "values": [
                _expression(node.left),
                *[_expression(n) for n in node.comparators],
            ],
        }
    if isinstance(node, ast.IfExp):
        return {
            "op": "select",
            "condition": _expression(node.test),
            "yes": _expression(node.body),
            "no": _expression(node.orelse),
        }
    if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
        return {
            "op": "index",
            "value": _expression(node.value),
            "index": _expression(node.slice),
        }
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in HELPERS
    ):
        if node.keywords:
            raise BuilderError("Helpers use positional arguments", line=line)
        return {
            "op": "call",
            "name": node.func.id,
            "args": [_expression(n) for n in node.args],
        }
    raise BuilderError(f"Unsupported expression: {type(node).__name__}", line=line)


def parse_expression(source):
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        raise BuilderError("An expression must be text within the source limit")
    try:
        tree = ast.parse(source, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise BuilderError("Expression is too complex")
        return _expression(tree.body)
    except (SyntaxError, RecursionError) as exc:
        raise BuilderError(
            f"Invalid expression: {getattr(exc, 'msg', str(exc))}",
            line=getattr(exc, "lineno", None),
        ) from exc


def _target(node):
    if isinstance(node, ast.Name):
        identifier(node.id)
        if node.id in READ_ONLY:
            raise BuilderError(
                f"{node.id} is managed by the runtime and cannot be assigned",
                line=node.lineno,
            )
        return {"name": node.id}
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and not isinstance(node.slice, ast.Slice)
    ):
        name = identifier(node.value.id)
        if name in READ_ONLY:
            raise BuilderError(f"{name} is read-only", line=node.lineno)
        return {"name": name, "index": _expression(node.slice)}
    raise BuilderError(
        "Assign a state variable or one of its list elements",
        line=getattr(node, "lineno", None),
    )


def _statements(nodes, loop_depth=0):
    result = []
    for node in nodes:
        entry = {"line": node.lineno}
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            entry.update(
                op="assign",
                target=_target(node.targets[0]),
                value=_expression(node.value),
            )
        elif isinstance(node, ast.AugAssign) and type(node.op) in OPERATORS:
            entry.update(
                op="augment",
                target=_target(node.target),
                operator=OPERATORS[type(node.op)],
                value=_expression(node.value),
            )
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            entry.update(op="expression", value=_expression(node.value))
        elif isinstance(node, ast.If):
            entry.update(
                op="if",
                condition=_expression(node.test),
                yes=_statements(node.body, loop_depth),
                no=_statements(node.orelse, loop_depth),
            )
        elif (
            isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and not node.orelse
        ):
            target = _target(node.target)
            entry.update(
                op="for",
                target=target,
                values=_expression(node.iter),
                body=_statements(node.body, loop_depth + 1),
            )
        elif isinstance(node, (ast.Break, ast.Continue)) and loop_depth:
            entry.update(op="break" if isinstance(node, ast.Break) else "continue")
        elif isinstance(node, ast.Pass):
            entry.update(op="pass")
        else:
            raise BuilderError(
                f"Unsupported statement: {type(node).__name__}. Use assignments, if/else, bounded for, and helpers.",
                line=node.lineno,
            )
        result.append(entry)
    return result


def parse_program(source, notation="python"):
    """Return a JSON program; line locations refer to the original notation."""
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        raise BuilderError(f"Custom blocks are limited to {MAX_SOURCE} characters")
    notation = notation_name(notation)
    line_map = {}
    if notation == "pseudocode":
        source, line_map = _pseudocode_to_python(source)
    try:
        tree = ast.parse(source, mode="exec")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise BuilderError("Custom block is too complex")
        result = _statements(tree.body)
    except (SyntaxError, RecursionError) as exc:
        line = getattr(exc, "lineno", None)
        raise BuilderError(
            f"Invalid syntax: {getattr(exc, 'msg', str(exc))}",
            line=line_map.get(line, line),
        ) from exc
    except BuilderError as exc:
        if line_map and exc.line:
            exc.line = line_map.get(exc.line, exc.line)
        raise

    def remap(entries):
        for entry in entries:
            entry["line"] = line_map.get(entry["line"], entry["line"])
            for field in ("yes", "no", "body"):
                if field in entry:
                    remap(entry[field])

    remap(result)
    return result


def expression_source(expr):
    op = expr["op"]
    if op == "constant":
        return repr(expr["value"])
    if op == "name":
        return expr["name"]
    if op == "list":
        return "[" + ", ".join(expression_source(e) for e in expr["values"]) + "]"
    if op == "binary":
        return f"({expression_source(expr['left'])} {expr['operator']} {expression_source(expr['right'])})"
    if op == "unary":
        return f"({expr['operator']} {expression_source(expr['value'])})"
    if op == "boolean":
        return (
            "("
            + f" {expr['operator']} ".join(expression_source(e) for e in expr["values"])
            + ")"
        )
    if op == "compare":
        values = expr["values"]
        return (
            "("
            + expression_source(values[0])
            + "".join(
                f" {operator} {expression_source(value)}"
                for operator, value in zip(expr["operators"], values[1:], strict=True)
            )
            + ")"
        )
    if op == "select":
        return f"({expression_source(expr['yes'])} if {expression_source(expr['condition'])} else {expression_source(expr['no'])})"
    if op == "index":
        return f"{expression_source(expr['value'])}[{expression_source(expr['index'])}]"
    if op == "call":
        return (
            expr["name"]
            + "("
            + ", ".join(expression_source(e) for e in expr["args"])
            + ")"
        )
    raise BuilderError("Unknown expression representation")


def render_program(program, notation="python"):
    notation = notation_name(notation)
    pseudo = notation == "pseudocode"
    lines = []

    def render(entries, indent=0):
        for entry in entries:
            op, prefix = entry["op"], "    " * indent
            if op in {"assign", "augment"}:
                target = entry["target"]["name"]
                if "index" in entry["target"]:
                    target += "[" + expression_source(entry["target"]["index"]) + "]"
                operator = "=" if op == "assign" else entry["operator"] + "="
                lines.append(
                    prefix
                    + ("SET " if pseudo else "")
                    + target
                    + f" {operator} "
                    + expression_source(entry["value"])
                )
            elif op == "expression":
                value = entry["value"]
                name, args = value["name"], value["args"]
                if pseudo and name in {"cover", "discard", "emit"} and len(args) <= 1:
                    lines.append(
                        prefix
                        + name.upper()
                        + (" " + expression_source(args[0]) if args else "")
                    )
                else:
                    lines.append(
                        prefix + ("CALL " if pseudo else "") + expression_source(value)
                    )
            elif op == "if":
                lines.append(
                    prefix
                    + ("IF " if pseudo else "if ")
                    + expression_source(entry["condition"])
                    + (" THEN" if pseudo else ":")
                )
                render(entry["yes"] or [{"op": "pass"}], indent + 1)
                if entry["no"]:
                    lines.append(prefix + ("ELSE" if pseudo else "else:"))
                    render(entry["no"], indent + 1)
                if pseudo:
                    lines.append(prefix + "END")
            elif op == "for":
                lines.append(
                    prefix
                    + ("FOR " if pseudo else "for ")
                    + entry["target"]["name"]
                    + (" IN " if pseudo else " in ")
                    + expression_source(entry["values"])
                    + (" DO" if pseudo else ":")
                )
                render(entry["body"] or [{"op": "pass"}], indent + 1)
                if pseudo:
                    lines.append(prefix + "END")
            else:
                lines.append(prefix + (op.upper() if pseudo else op))

    render(program)
    return "\n".join(lines)


def convert_program(source, from_notation, to_notation):
    return render_program(parse_program(source, from_notation), to_notation)


translate = convert_program
