import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ha_harmony_pushkit"


def test_manifest_allows_ui_config_flow():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["config_flow"] is True


def test_config_flow_module_defines_domain_flow_handler():
    config_flow_file = INTEGRATION / "config_flow.py"

    assert config_flow_file.exists()

    module = ast.parse(config_flow_file.read_text(encoding="utf-8"))
    classes = {node.name: node for node in module.body if isinstance(node, ast.ClassDef)}

    assert "HaHarmonyPushKitConfigFlow" in classes
    assert any(
        keyword.arg == "domain" and isinstance(keyword.value, ast.Name) and keyword.value.id == "DOMAIN"
        for keyword in classes["HaHarmonyPushKitConfigFlow"].keywords
    )


def test_integration_supports_config_entry_setup():
    init_file = INTEGRATION / "__init__.py"
    module = ast.parse(init_file.read_text(encoding="utf-8"))

    async_functions = {node.name for node in module.body if isinstance(node, ast.AsyncFunctionDef)}

    assert "async_setup_entry" in async_functions

def test_integration_supports_config_entry_unload():
    init_file = INTEGRATION / "__init__.py"
    module = ast.parse(init_file.read_text(encoding="utf-8"))

    async_functions = {node.name for node in module.body if isinstance(node, ast.AsyncFunctionDef)}

    assert "async_unload_entry" in async_functions
