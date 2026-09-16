import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def now():
    return datetime.now(UTC).isoformat()


def new_run(root):
    path = Path(root).resolve() / (
        datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:10]
    )
    path.mkdir(parents=True)
    return path


def provenance(out):
    source = Path(__file__).resolve().parents[1]
    record = {
        "python": sys.version,
        "platform": platform.platform(),
        "rng": "random.Random/MT19937",
        "git_commit": None,
        "git_dirty": None,
    }
    record["packages"] = {}
    for name in (
        "bincovering",
        "hydra-core",
        "omegaconf",
        "numpy",
        "matplotlib",
        "Flask",
    ):
        try:
            record["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(source), *args], stderr=subprocess.DEVNULL
        )

    files = []
    try:
        root = Path(git("rev-parse", "--show-toplevel").decode().strip())
        record["git_commit"] = git("rev-parse", "HEAD").decode().strip()
        record["git_dirty"] = bool(git("status", "--porcelain").strip())
        names = (
            git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
            .decode()
            .split("\0")
        )
        files = [
            (root / n, n)
            for n in sorted(set(names))
            if n
            and (root / n).is_file()
            and Path(n).suffix
            in (
                ".py",
                ".cpp",
                ".h",
                ".hpp",
                ".yaml",
                ".toml",
                ".md",
                ".txt",
                ".lock",
                ".html",
                ".css",
                ".js",
            )
        ]
    except (OSError, subprocess.CalledProcessError):
        files = [
            (p, str(p.relative_to(source.parent)))
            for p in source.rglob("*")
            if p.is_file() and p.suffix in (".py", ".yaml", ".html", ".css", ".js")
        ]
    with zipfile.ZipFile(out / "source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, name)
    record["source_sha256"] = hashlib.sha256(
        (out / "source.zip").read_bytes()
    ).hexdigest()
    return record


def list_runs(root):
    root = Path(root).resolve()
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.rglob("manifest.json"), reverse=True):
        try:
            record = json.loads(path.read_text())
            rows.append({"path": str(path.parent), **record})
        except (ValueError, OSError):
            continue
    return rows
