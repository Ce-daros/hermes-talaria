import importlib.util
import json
import sys
import tempfile
from pathlib import Path


plugin_dir = Path("/home/ame/.hermes/hermes-agent/plugins/hermes-talaria")
spec = importlib.util.spec_from_file_location(
    "hermes_talaria_runtime_smoke",
    plugin_dir / "__init__.py",
    submodule_search_locations=[str(plugin_dir)],
)
module = importlib.util.module_from_spec(spec)
sys.modules["hermes_talaria_runtime_smoke"] = module
spec.loader.exec_module(module)


class Ctx:
    def register_tool(self, **kwargs):
        pass

    def register_hook(self, name, handler):
        pass

    def register_command(self, name, **kwargs):
        pass

    def register_skill(self, name, path, description):
        pass


module.register(Ctx())
code_intel = sys.modules["hermes_talaria_runtime_smoke.code_intel"]

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "sample.py"
    path.write_text(
        "import os\n\n"
        "class Greeter:\n"
        "    def greet(self, name):\n"
        "        return name\n\n"
        "def make():\n"
        "    return Greeter()\n",
        encoding="utf-8",
    )
    symbols = json.loads(code_intel.code_symbols_tool(str(path)))
    print("symbol_names", [symbol["name"] for symbol in symbols["symbols"]])
    search = json.loads(code_intel.code_search_tool(str(path), preset="return_stmts"))
    print("search_count", search["match_count"])
