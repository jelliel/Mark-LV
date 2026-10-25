"""
Where the research engine keeps its things, and how wide it is allowed to run.

Every value is read from the same `config/api_keys.json` the rest of the app
uses, so there is no second settings file to lose. The keys are optional: a
install that never touches them gets the defaults below, and a default that
cannot be created is simply created on first use.

    research_dir              folder for runs, agents and skills
    research_max_parallel     readers working at the same time (default 4)
    research_language         "auto" follows the topic, or pin "fr"/"en"/…
    research_voice_summary    speak the headline when a run finishes
    research_max_page_chars   how much of one page a reader is given
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

DEFAULT_FOLDER = "Theologicus Research"

DEFAULTS = {
    "research_max_parallel": 4,
    "research_language": "auto",
    "research_voice_summary": True,
    "research_max_page_chars": 4000,
    # The theology vault starts a run when a question has no coverage.
    "theology_auto_research": True,
    "theology_auto_research_depth": "standard",
    "theology_auto_research_language": "auto",
    "theology_auto_research_cooldown": 1800,
}


def config_data() -> dict:
    """The app's config file, or an empty dict. Never raises."""
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def setting(name: str, default=None):
    """A user setting if it is set, otherwise the default, otherwise `default`.

    An empty string counts as unset: a blank field in a settings dialog should
    mean "use yours", not "use nothing".

    A setting may live at the top of the file, or in a plugin's own settings
    namespace — the settings UI stores what a plugin declares under
    `plugin_config[<namespace>]`, and the engine reads those by name too, so
    a plugin that owns a knob does not need the app to know about it."""
    data = config_data()
    value = data.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        plugins = data.get("plugin_config")
        if isinstance(plugins, dict):
            for namespace in sorted(plugins):
                values = plugins.get(namespace)
                if not isinstance(values, dict):
                    continue
                candidate = values.get(name)
                if candidate is None or (isinstance(candidate, str)
                                         and not candidate.strip()):
                    continue
                value = candidate
                break
    if value is None or (isinstance(value, str) and not value.strip()):
        value = DEFAULTS.get(name, default)
    return value


def research_root() -> Path:
    """The folder holding every run, plus the user's own agents and skills.

    In Documents rather than next to the app, for the same reason the theology
    vault is: an update replaces the app folder, and a report the user asked for
    is not part of the installation."""
    override = setting("research_dir")
    root = Path(str(override)).expanduser() if override else \
        Path.home() / "Documents" / DEFAULT_FOLDER
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[Research] cannot create {root}: {e}")
    return root


def runs_dir(root: Path | None = None) -> Path:
    path = (root or research_root()) / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def agents_dir(root: Path | None = None) -> Path:
    path = (root or research_root()) / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def skills_dir(root: Path | None = None) -> Path:
    path = (root or research_root()) / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_skills_dir() -> Path:
    """Skills that ship with the app, in Theologicus Research/skills' shadow.

    A user skill with the same name wins — that is how you tune one of these
    without forking the repository."""
    return Path(__file__).resolve().parent / "skills"
