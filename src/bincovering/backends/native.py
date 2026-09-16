import json
import subprocess

from bincovering.algorithms.registry import Result


def solve_native(items, spec, domain, threshold, executable, cancelled=lambda: False):
    command = [
        str(executable),
        spec["id"],
        domain,
        str(threshold),
        str(spec["params"].get("k", 5)),
    ]
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        payload = "\n".join(map(str, items)) + "\n"
        try:
            while True:
                if cancelled():
                    raise InterruptedError("Cancelled")
                try:
                    stdout, stderr = process.communicate(input=payload, timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    payload = None
            if process.returncode:
                raise RuntimeError(stderr.strip())
            return Result(**json.loads(stdout))
        except BaseException:
            process.kill()
            process.communicate()
            raise
