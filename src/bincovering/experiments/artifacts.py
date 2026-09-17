"""Export and rerun research records without overwriting evidence."""

import json
import uuid
import zipfile
from pathlib import Path

from .lifecycle import RunLease


def export_run(run, destination=None):
    run = Path(run).resolve()
    if not (run / "manifest.json").is_file():
        raise ValueError("Not an experiment directory")
    target = (
        Path(destination).resolve()
        if destination
        else run / "exports" / f"{run.name}-{uuid.uuid4().hex[:8]}.zip"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with RunLease(run):
        if json.loads((run / "manifest.json").read_text())["status"] in (
            "queued",
            "running",
        ):
            raise ValueError("Wait for the run to finish before exporting")
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(run.rglob("*")):
                if file.is_symlink():
                    raise ValueError("Refusing to export linked files")
                relative = file.relative_to(run)
                if (
                    file.is_file()
                    and file != target
                    and "exports" not in relative.parts
                    and file.name != ".run.lock"
                ):
                    archive.write(file, str(relative))
    return target


def rerun(run, output_root=None):
    """Rerun with current code; the new manifest records its own source revision."""
    from .runner import run_experiment
    from .storage import write_json

    run = Path(run).resolve()
    cfg = json.loads((run / "config.json").read_text())
    if cfg["generator"]["id"] == "file":
        cfg["generator"]["path"] = str(run / "input-source.txt")
    if any(spec["backend"] == "cpp" for spec in cfg["algorithms"]):
        cfg["native_executable"] = str(run / "native-executable")
    if output_root:
        cfg["output_root"] = str(Path(output_root).resolve())
    out = run_experiment(cfg)
    metadata = json.loads((out / "manifest.json").read_text())
    metadata["rerun_of"] = str(run)
    write_json(out / "manifest.json", metadata)
    return out
