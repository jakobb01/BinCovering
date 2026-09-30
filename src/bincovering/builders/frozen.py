"""Frozen program contracts used by the shared experiment configuration."""

import copy
import re


def is_custom(identity):
    return isinstance(identity, str) and identity.startswith("custom:")


def normalize_custom(spec, kind):
    from .schema import RUNTIME_VERSION, graph_hash, validate_graph

    if not isinstance(spec, dict) or not re.fullmatch(r"custom:[a-zA-Z0-9_-]{1,80}", spec.get("id", "")):
        raise ValueError("Invalid custom component identity")
    allowed = {"id", "params", "backend", "revision", "frozen"}
    if kind == "algorithm" and spec.keys() - allowed:
        raise ValueError("Unknown custom algorithm setting")
    if spec.get("backend", "python") != "python":
        raise ValueError("Custom components use the Python runtime")
    revision = spec.get("revision")
    if type(revision) not in (str, int) or not str(revision) or len(str(revision)) > 100:
        raise ValueError("Select an immutable custom revision")
    frozen = spec.get("frozen")
    if not isinstance(frozen, dict) or not isinstance(frozen.get("graph"), dict):
        raise ValueError("Custom components need their frozen program package")
    frozen = copy.deepcopy(frozen)
    graph = validate_graph(frozen["graph"])
    if graph["kind"] != kind:
        raise ValueError(f"Select a custom {kind}")
    content_hash = graph_hash(graph)
    if frozen.get("content_hash") != content_hash:
        raise ValueError("Frozen component content hash does not match its graph")
    if str(frozen.get("runtime_version")) != str(RUNTIME_VERSION):
        raise ValueError("The frozen builder runtime version is unsupported")
    image = frozen.get("runtime_image")
    if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Frozen components require their tested runtime image identity")
    frozen["graph"] = graph
    params = spec.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("Custom parameters must be an object")
    from .schema import resolve_parameters

    params = resolve_parameters(graph, params)
    return {"id": spec["id"], "params": params, "backend": "python",
            "revision": revision, "frozen": frozen}


def group_identity(spec):
    """Keep each frozen revision distinct in existing report grouping keys."""
    return f"{spec['id']}@{spec['revision']}" if is_custom(spec["id"]) else spec["id"]
