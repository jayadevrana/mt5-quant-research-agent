from __future__ import annotations

import json
import logging
import math
from datetime import datetime, time
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def setup_logging(log_dir: str | Path = "logs", level: int = logging.INFO) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mt5_codex_quant_agent")
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(Path(log_dir) / "agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def timeframe_to_minutes(timeframe: str) -> int:
    mapping = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }
    key = timeframe.upper()
    if key not in mapping:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return mapping[key]


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def session_contains(timestamp: Any, start: str, end: str) -> bool:
    ts = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp
    current = ts.time()
    start_t = parse_hhmm(start)
    end_t = parse_hhmm(end)
    if start_t <= end_t:
        return start_t <= current <= end_t
    return current >= start_t or current <= end_t


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        raise ValueError("step must be positive")
    return math.floor((value / step) + 1e-10) * step
