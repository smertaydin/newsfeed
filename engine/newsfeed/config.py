from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    raw: dict

    def __getitem__(self, key):
        return self.raw[key]

    @property
    def state_dir(self) -> Path:
        p = ROOT / "state"
        p.mkdir(exist_ok=True)
        return p

    @property
    def out_dir(self) -> Path:
        p = ROOT / "out"
        p.mkdir(exist_ok=True)
        return p


def load(path: Path | None = None) -> Config:
    path = path or ROOT / "config.yaml"
    return Config(yaml.safe_load(path.read_text(encoding="utf-8")))
