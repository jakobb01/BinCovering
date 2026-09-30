"""Host-controlled, bounded execution of builder programs in rootless containers.

Only validated JSON crosses this boundary. A custom program never runs in Flask
or an experiment worker, and there is no host-execution fallback.
"""

import json
import math
import os
import selectors
import subprocess
import time
import uuid
from pathlib import Path

IMAGE = "localhost/bincovering-builder:v1"
LIMITS = {
    "seconds": 30,
    "memory_mb": 256,
    "cpus": 1,
    "pids": 64,
    "scratch_mb": 32,
    "request_bytes": 16 * 1024 * 1024,
    "output_bytes": 16 * 1024 * 1024,
}


class IsolationError(ValueError):
    """The required execution boundary is unavailable or exceeded its limits."""


def _podman(*arguments):
    try:
        return subprocess.check_output(
            ["podman", *arguments], stderr=subprocess.PIPE, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise IsolationError(
            "Builder execution needs a working rootless Podman runtime and the "
            "builder image. See docs/BUILDER.md for setup."
        ) from exc


def settings(root=None):
    config = {"image": IMAGE, "limits": dict(LIMITS)}
    path = Path(root or "outputs") / ".dashboard" / "execution.json"
    if path.is_file():
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or value.keys() - {"image", "limits"}:
            raise IsolationError("Invalid server execution settings")
        if "image" in value:
            config["image"] = value["image"]
        if "limits" in value:
            if not isinstance(value["limits"], dict) or value["limits"].keys() - LIMITS.keys():
                raise IsolationError("Invalid server execution limits")
            config["limits"].update(value["limits"])
    if not isinstance(config["image"], str) or not config["image"]:
        raise IsolationError("Invalid builder image")
    if any(type(v) not in (int, float) or v <= 0 for v in config["limits"].values()):
        raise IsolationError("Execution limits must be positive numbers")
    return config


def runtime_identity(root=None, runtime_image=None):
    """Resolve an immutable image identity and check required host capabilities."""
    info = json.loads(_podman("info", "--format", "json"))
    host = info.get("host", {})
    security = host.get("security", {})
    if (
        not security.get("rootless")
        or not security.get("seccompEnabled")
        or host.get("cgroupVersion") != "v2"
        or not {"cpu", "memory", "pids"} <= set(host.get("cgroupControllers", []))
    ):
        raise IsolationError("Rootless Podman with seccomp and CPU/memory/PID controls is required")
    image = runtime_image or settings(root)["image"]
    if runtime_image and (
        not isinstance(runtime_image, str)
        or not runtime_image.startswith("sha256:")
        or len(runtime_image) != 71
        or any(c not in "0123456789abcdef" for c in runtime_image[7:])
    ):
        raise IsolationError("Frozen builder runtime must be an immutable image ID")
    records = json.loads(_podman("image", "inspect", image))
    if not records or not records[0].get("Id"):
        raise IsolationError("The frozen builder runtime image is unavailable")
    image_id = records[0]["Id"]
    if not image_id.startswith("sha256:"):
        image_id = "sha256:" + image_id
    return {"image": image_id, "isolation": "rootless-podman", "cgroup_version": "v2"}


def container_command(image, name, limits):
    """No host mounts, no network, read-only image, and a bounded private tmpfs."""
    return [
        "podman", "run", "--rm", "--pull=never", "--name", name,
        "--network=none", "--http-proxy=false", "--read-only", "--read-only-tmpfs=false",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--user=65534:65534", "--pids-limit", str(int(limits["pids"])),
        "--memory", f"{int(limits['memory_mb'])}m", "--memory-swap", f"{int(limits['memory_mb'])}m",
        "--cpus", str(limits["cpus"]), "--timeout", str(max(1, math.ceil(limits["seconds"]))),
        "--stop-timeout=1", "--ulimit", "nofile=64:64",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={int(limits['scratch_mb'])}m",
        "--log-driver=none", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONUNBUFFERED=1", "--interactive", image,
        "python", "-m", "bincovering.builders.worker",
    ]


def _remove_container(name):
    try:
        subprocess.run(
            ["podman", "rm", "--force", name], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def execute_isolated(graph, *, items=None, seed=0, params=None, inputs=None, component_context=None, domain=None,
                     threshold=1, n=10, trace_limit=1000, trace_bytes=2 * 1024 * 1024,
                     root=None, runtime_image=None, cancelled=lambda: False):
    from .schema import validate_graph

    graph = validate_graph(graph)
    config = settings(root)
    identity = runtime_identity(root, runtime_image)
    payload = json.dumps(
        {"graph": graph, "items": items or [], "seed": seed, "params": params or {}, "inputs": inputs or {},
         "domain": domain or graph.get("domain", "float64"), "threshold": threshold,
         "n": n, "trace_limit": trace_limit, "trace_bytes": trace_bytes,
         "component_context": component_context},
        allow_nan=False, separators=(",", ":"),
    ).encode()
    limits = config["limits"]
    if len(payload) > limits["request_bytes"]:
        raise IsolationError("Builder input exceeds the execution request limit")
    if cancelled():
        raise InterruptedError("Cancelled")
    name = "bincovering-builder-" + uuid.uuid4().hex
    started = time.monotonic()
    process = None
    stdout, stderr = bytearray(), bytearray()
    try:
        process = subprocess.Popen(
            container_command(identity["image"], name, limits),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        with selectors.DefaultSelector() as selector:
            for pipe, event, label in (
                (process.stdin, selectors.EVENT_WRITE, "input"),
                (process.stdout, selectors.EVENT_READ, "output"),
                (process.stderr, selectors.EVENT_READ, "error"),
            ):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, event, label)
            sent = 0
            while selector.get_map():
                if cancelled():
                    raise InterruptedError("Cancelled")
                if time.monotonic() - started > limits["seconds"]:
                    raise IsolationError("Builder execution exceeded its time limit")
                for key, _ in selector.select(timeout=0.1):
                    pipe = key.fileobj
                    if key.data == "input":
                        try:
                            sent += os.write(pipe.fileno(), payload[sent:sent + 65536])
                        except BrokenPipeError:
                            sent = len(payload)
                        if sent == len(payload):
                            selector.unregister(pipe)
                            pipe.close()
                    else:
                        chunk = os.read(pipe.fileno(), 65536)
                        if not chunk:
                            selector.unregister(pipe)
                            pipe.close()
                            continue
                        destination = stdout if key.data == "output" else stderr
                        destination.extend(chunk)
                        if len(stdout) + len(stderr) > limits["output_bytes"]:
                            raise IsolationError("Builder execution exceeded its output limit")
        process.wait(timeout=5)
        if process.returncode:
            detail = stderr.decode(errors="replace")[-1500:].strip()
            raise IsolationError(f"Builder runtime exited with status {process.returncode}: {detail}")
        try:
            response = json.loads(stdout)
        except (ValueError, UnicodeDecodeError) as exc:
            raise IsolationError("Builder runtime returned an invalid response") from exc
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            raise IsolationError("Builder runtime returned an invalid result")
        response["execution"] = {**response.get("execution", {}), **identity, "limits": limits,
                                 "elapsed_seconds": time.monotonic() - started}
        return response
    except OSError as exc:
        raise IsolationError("Could not start the isolated builder runtime") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                _remove_container(name)
                process.kill()
                process.wait(timeout=10)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
        _remove_container(name)
