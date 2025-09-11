import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "WakaWaka",
    "version": "0.2.0",
    "camera": {"width": 640, "height": 480, "fps": 30},
    "stream": {"host": "0.0.0.0", "port": 8000, "debug": False},
}


def config_path() -> Path:
    return Path(__file__).with_name("config.json")


def load_config() -> Dict[str, Any]:
    path = config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> None:
    path = config_path()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


