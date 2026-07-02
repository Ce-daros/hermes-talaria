import importlib.util
import sys
import types
from pathlib import Path


def load_plugin():
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    install_hermes_stubs()
    spec = importlib.util.spec_from_file_location(
        "hermes_talaria_plugin",
        plugin_path,
        submodule_search_locations=[str(plugin_path.parent)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["hermes_talaria_plugin"] = module
    spec.loader.exec_module(module)
    return module


def install_hermes_stubs():
    registry_mod = types.ModuleType("tools.registry")

    class Registry:
        def __init__(self):
            self.entries = {}

        def register(self, **kwargs):
            self.entries[kwargs["name"]] = kwargs

    registry_mod.registry = Registry()
    tools_pkg = types.ModuleType("tools")
    tools_pkg.registry = registry_mod
    sys.modules["tools"] = tools_pkg
    sys.modules["tools.registry"] = registry_mod

    toolsets_mod = types.ModuleType("toolsets")
    toolsets_mod.TOOLSETS = {}
    toolsets_mod._HERMES_CORE_TOOLS = []
    sys.modules["toolsets"] = toolsets_mod


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, handler):
        self.hooks[name] = handler

    def register_command(self, name, **kwargs):
        self.commands[name] = kwargs

    def register_skill(self, name, path, description):
        self.skills[name] = {"path": path, "description": description}


def test_register_exposes_talaria_tools_and_transform_hooks():
    plugin = load_plugin()
    ctx = FakeContext()

    plugin.register(ctx)

    assert "talaria_retrieve" in ctx.tools
    assert "talaria_stats" in ctx.tools
    assert "talaria_compress" in ctx.tools
    assert "transform_terminal_output" in ctx.hooks
    assert "transform_tool_result" in ctx.hooks
    assert "on_session_end" in ctx.hooks


def test_talaria_retrieve_schema_accepts_optional_query():
    plugin = load_plugin()
    ctx = FakeContext()

    plugin.register(ctx)

    schema = ctx.tools["talaria_retrieve"]["schema"]
    assert schema["parameters"]["required"] == ["hash"]
    assert "query" in schema["parameters"]["properties"]
