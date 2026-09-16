import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

from bincovering.experiments.storage import list_runs


def main():
    parser = argparse.ArgumentParser(description="Bin covering research tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Hydra run: bincovering run seed=42 n=1000")
    sub.add_parser("algorithms")
    p = sub.add_parser("list")
    p.add_argument("--root", default="outputs")
    for name in ("inspect", "plot", "pin", "unpin"):
        p = sub.add_parser(name)
        p.add_argument("run")
    p = sub.add_parser("compare")
    p.add_argument("runs", nargs="+")
    p = sub.add_parser("export")
    p.add_argument("run")
    p.add_argument("--destination", default=None)
    p = sub.add_parser("cleanup")
    p.add_argument("--root", default="outputs")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("web")
    p.add_argument("--root", default="outputs")
    p.add_argument("--port", type=int, default=5000)
    # Preserve Hydra overrides and --help handling after the run subcommand.
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from bincovering.run import main as run

        run()
        return
    args = parser.parse_args()
    if args.command == "algorithms":
        from bincovering.algorithms.registry import ALIASES, PARAMETERS

        print(json.dumps({"algorithms": PARAMETERS, "aliases": ALIASES}, indent=2))
    elif args.command == "list":
        for r in list_runs(args.root):
            print(r["status"], r["name"], r["path"])
    elif args.command == "inspect":
        print((Path(args.run) / "manifest.json").read_text())
    elif args.command == "plot":
        from bincovering.reporting.reports import plot_run

        print(plot_run(args.run))
    elif args.command == "compare":
        from bincovering.reporting.reports import compare

        print(json.dumps(compare(args.runs), indent=2))
    elif args.command in ("pin", "unpin"):
        run = Path(args.run)
        if not (run / "manifest.json").is_file():
            parser.error("Not an experiment directory")
        if args.command == "pin":
            (run / "PINNED").touch()
        else:
            (run / "PINNED").unlink(missing_ok=True)
    elif args.command == "cleanup":
        # Only disposable derived files; raw trials, inputs and provenance are retained.
        for run in list_runs(args.root):
            path = Path(run["path"])
            if (path / "PINNED").exists() or run["status"] in ("running", "queued"):
                continue
            for name in ("figures", "traces"):
                candidate = path / name
                if candidate.is_dir() and not candidate.is_symlink():
                    print(
                        ("Removing " if args.apply else "Would remove ")
                        + str(candidate)
                    )
                    if args.apply:
                        shutil.rmtree(candidate)
    elif args.command == "export":
        run = Path(args.run).resolve()
        destination = (
            Path(args.destination)
            if args.destination
            else run / "exports" / f"{run.name}.zip"
        )
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
            for file in run.rglob("*"):
                if (
                    file.is_file()
                    and file != destination
                    and "exports" not in file.relative_to(run).parts
                ):
                    archive.write(file, str(file.relative_to(run)))
        print(destination)
    elif args.command == "web":
        from bincovering.web.app import create_app

        create_app(args.root).run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
