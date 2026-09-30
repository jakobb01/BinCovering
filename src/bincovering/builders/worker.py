"""The execution image's bounded stdin/stdout protocol; no filesystem inputs."""

import json
import sys

from .language import BuilderError
from .runtime import execute

MAX_REQUEST_BYTES = 16 * 1024 * 1024
ARGUMENTS = frozenset(
    {
        "graph",
        "items",
        "seed",
        "params",
        "domain",
        "threshold",
        "n",
        "trace_limit",
        "trace_bytes",
        "state_limit",
        "inputs",
        "component_context",
    }
)


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise BuilderError(
                "Worker request exceeds the 16 MB input limit", code="resource_limit"
            )
        request = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Invalid constant: {value}")
            ),
        )
        if (
            not isinstance(request, dict)
            or set(request) - ARGUMENTS
            or "graph" not in request
        ):
            raise BuilderError(
                "Worker expects an execute request with documented arguments",
                code="invalid_request",
            )
        response = execute(**request)
    except (BuilderError, ValueError, TypeError) as exc:
        error = (
            exc.as_dict()
            if isinstance(exc, BuilderError)
            else {
                "message": str(exc),
                "node_id": None,
                "line": None,
                "code": "invalid_request",
            }
        )
        response = {
            "ok": False,
            "result": None,
            "error": error,
            "trace": {"schema_version": 1, "events": [], "truncated": False},
        }
    sys.stdout.write(json.dumps(response, allow_nan=False, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
