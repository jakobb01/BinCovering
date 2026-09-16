import json
import sys
from pathlib import Path

from bincovering.experiments.runner import run_experiment

if __name__ == "__main__":
    path = Path(sys.argv[1])
    run_experiment(json.loads((path / "request.json").read_text()), path)
