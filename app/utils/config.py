import os
from pathlib import Path


def truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def config_roots() -> list[Path]:
    project_root = Path(__file__).resolve().parent.parent.parent
    repo_config = project_root / "config"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_config = Path(xdg_config_home).expanduser() / "smolcode"
    else:
        xdg_config = Path.home() / ".config" / "smolcode"
    return [repo_config, xdg_config]


def iter_config_files(relative_dir: str, pattern: str) -> list[Path]:
    files: list[Path] = []
    for config_root in config_roots():
        directory = config_root / relative_dir
        if not directory.exists():
            continue
        files.extend(sorted(directory.glob(pattern)))
    return files


def config_file(relative_path: str) -> Path | None:
    selected: Path | None = None
    for config_root in config_roots():
        candidate = config_root / relative_path
        if candidate.exists():
            selected = candidate
    return selected
