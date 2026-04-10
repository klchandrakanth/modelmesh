import os
from modelmesh.config.settings import Settings

def test_settings_defaults():
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.ollama_base_url == "http://localhost:11434"

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("MODELMESH_PORT", "9000")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = Settings()
    assert s.port == 9000
    assert s.openai_api_key == "sk-test"
