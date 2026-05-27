from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from chess_coach.config import load_config, ConfigError


class TestLoadConfig:
    def test_load_valid_config(self, temp_config: Path, sample_config: dict):
        result = load_config(str(temp_config))
        assert result == sample_config

    def test_load_nonexistent_path(self):
        with pytest.raises(ConfigError):
            load_config("nonexistent.yaml")

    def test_load_invalid_yaml(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("{ invalid: unclosed")
        with pytest.raises(ConfigError):
            load_config(str(p))

    def test_load_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(ConfigError):
            load_config(str(p))

    def test_engine_defaults_filled(self, temp_config: Path):
        cfg = load_config(str(temp_config))
        assert "engine" in cfg
        assert cfg["engine"]["path"] == "stockfish.exe"
        assert isinstance(cfg["engine"]["threads"], int)
        assert cfg["engine"]["threads"] >= 1
        assert isinstance(cfg["engine"]["hash"], int)
        assert cfg["engine"]["hash"] >= 16

    def test_display_defaults_filled(self, temp_config: Path):
        cfg = load_config(str(temp_config))
        assert "display" in cfg
        assert cfg["display"]["dark_square"].startswith("#")
        assert cfg["display"]["light_square"].startswith("#")
        assert isinstance(cfg["display"]["arrow_opacity"], (int, float))

    def test_config_valid_types(self, temp_config: Path):
        cfg = load_config(str(temp_config))
        engine = cfg["engine"]
        assert isinstance(engine["path"], str)
        assert isinstance(engine["threads"], int)
        assert isinstance(engine["hash"], int)
        assert isinstance(engine["movetime"], int)
        assert isinstance(engine["web_movetime"], (int, float))

    def test_missing_engine_fallback(self, tmp_path: Path):
        p = tmp_path / "partial.yaml"
        yaml_content = {"display": {"dark_square": "#000"}}
        with open(p, "w") as f:
            yaml.dump(yaml_content, f)
        with pytest.raises(ConfigError):
            load_config(str(p))

    def test_path_object_support(self, temp_config: Path, sample_config: dict):
        result = load_config(temp_config)
        assert result == sample_config

    def test_display_opacity_invalid_type(self, tmp_path: Path):
        p = tmp_path / "bad_opacity.yaml"
        import yaml
        cfg = {
            "engine": {"path": "sf", "threads": 2, "hash": 64},
            "display": {"arrow_opacity": "not_a_number", "arrow_color": "#00FF00",
                        "dark_square": "#B58", "light_square": "#F0D"},
        }
        with open(p, "w") as f:
            yaml.dump(cfg, f)
        with pytest.raises(ConfigError):
            load_config(str(p))

    def test_display_opacity_bool_rejected(self, tmp_path: Path):
        p = tmp_path / "bool_opacity.yaml"
        import yaml
        cfg = {
            "engine": {"path": "sf", "threads": 2, "hash": 64},
            "display": {"arrow_opacity": True, "arrow_color": "#00FF00",
                        "dark_square": "#B58", "light_square": "#F0D"},
        }
        with open(p, "w") as f:
            yaml.dump(cfg, f)
        with pytest.raises(ConfigError):
            load_config(str(p))

    def test_display_color_invalid_type(self, tmp_path: Path):
        p = tmp_path / "bad_color.yaml"
        import yaml
        cfg = {
            "engine": {"path": "sf", "threads": 2, "hash": 64},
            "display": {"dark_square": 12345, "light_square": "#F0D9B5",
                        "arrow_color": "#00FF00", "arrow_opacity": 0.6},
        }
        with open(p, "w") as f:
            yaml.dump(cfg, f)
        with pytest.raises(ConfigError):
            load_config(str(p))


class TestConfigError:
    def test_config_error_is_exception(self):
        err = ConfigError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"

    def test_config_error_with_path(self):
        err = ConfigError("file not found: config.yaml")
        assert "config.yaml" in str(err)
