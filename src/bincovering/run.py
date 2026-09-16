"""Hydra entry point; the reusable runner has no dependency on Hydra global state."""

import json

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from bincovering.experiments.runner import run_experiment


@hydra.main(version_base="1.3", config_path="configs", config_name="config")
def main(cfg: DictConfig):
    path = run_experiment(
        OmegaConf.to_container(cfg, resolve=True), HydraConfig.get().runtime.output_dir
    )
    print(f"Results: {path}")
    if json.loads((path / "manifest.json").read_text())["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
