"""Exercise this checkout through real Hermes discovery, never installed plugins."""
from pathlib import Path
import inspect
import shutil

import pytest


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1]
    home = tmp_path / "hermes-home"
    plugin = home / "plugins" / "model-providers" / "xkiro"
    plugin.mkdir(parents=True)
    for name in ("__init__.py", "plugin.yaml"):
        shutil.copy2(source / name, plugin / name)
    (home / "config.yaml").write_text("plugins:\n  enabled: [xkiro-provider]\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    from providers import get_provider_profile
    from providers.base import ProviderProfile

    chat = get_provider_profile("xkiro")
    anthropic = get_provider_profile("xkiro-anthropic")
    for profile in (chat, anthropic):
        assert isinstance(profile, ProviderProfile)
        loaded = Path(inspect.getfile(type(profile))).resolve()
        assert loaded == (plugin / "__init__.py").resolve()
        assert loaded.read_bytes() == (source / "__init__.py").read_bytes()
    return chat, anthropic
