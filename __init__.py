from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__:
    from .compression import TalariaCompressor
    from .retrieve import (
        TALARIA_COMPRESS_SCHEMA,
        TALARIA_RETRIEVE_SCHEMA,
        TALARIA_STATS_SCHEMA,
        handle_compress,
        handle_retrieve,
        handle_stats,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from compression import TalariaCompressor
    from retrieve import (
        TALARIA_COMPRESS_SCHEMA,
        TALARIA_RETRIEVE_SCHEMA,
        TALARIA_STATS_SCHEMA,
        handle_compress,
        handle_retrieve,
        handle_stats,
    )


CODE_TOOLS = [
    "code_symbols",
    "code_search",
    "code_refactor",
    "code_definition",
    "code_references",
    "code_diagnostics",
    "code_callers",
    "code_callees",
    "code_capsule",
    "code_workspace_summary",
    "code_impact",
    "code_tests_for_symbol",
    "code_query",
    "code_rename",
    "code_workspace_symbols",
    "code_hover",
    "code_type_definition",
    "code_signatures",
    "code_action",
]

TALARIA_TOOLS = ["talaria_retrieve", "talaria_stats", "talaria_compress"]
ALL_TOOLS = TALARIA_TOOLS + CODE_TOOLS

_compressor = TalariaCompressor()


def _handle_talaria_slash(raw_args: str) -> str:
    subcommand = raw_args.strip() or "status"
    if subcommand == "status":
        stats = _compressor.stats()
        return (
            "[talaria] Status\n"
            f"  Compressions: {stats['compressions']}\n"
            f"  Retrievals: {stats['retrievals']}\n"
            f"  Tokens saved: {stats['tokens_saved']}\n"
            f"  Stored items: {stats['stored_items']}"
        )
    if subcommand == "clear":
        _compressor.clear()
        return "[talaria] Store cleared."
    return "Usage: /talaria status|clear"


def _on_session_end(**_: Any) -> None:
    _compressor.clear()
    if __package__:
        from .code_intel import persist_symbol_cache, clear_symbol_cache
    else:
        from code_intel import persist_symbol_cache, clear_symbol_cache

    persist_symbol_cache()
    clear_symbol_cache()


def _install_toolset() -> None:
    import toolsets

    toolsets.TOOLSETS["talaria"] = {
        "description": "Tool-output compression and AST/LSP code intelligence.",
        "tools": ALL_TOOLS,
        "includes": [],
    }
    for name in ALL_TOOLS:
        if name not in toolsets._HERMES_CORE_TOOLS:
            toolsets._HERMES_CORE_TOOLS.append(name)
    for preset in ["hermes-acp", "hermes-api-server"]:
        if preset in toolsets.TOOLSETS:
            tools = toolsets.TOOLSETS[preset]["tools"]
            for name in ALL_TOOLS:
                if name not in tools:
                    tools.append(name)


def _register_code_intel() -> None:
    if __package__:
        from . import code_intel
        from .lsp_bridge import register_lsp_tools
    else:
        import code_intel
        from lsp_bridge import register_lsp_tools

    loaded = code_intel.load_symbol_cache()
    if loaded:
        import logging

        logging.getLogger("hermes-talaria").info(
            "Restored %d Talaria symbol cache entries", loaded
        )
    register_lsp_tools()


def register(ctx) -> None:
    _install_toolset()

    skill_path = Path(__file__).parent / "skills" / "native-code-intelligence.md"
    if skill_path.exists():
        ctx.register_skill(
            name="native-code-intelligence",
            path=skill_path,
            description="Native tree-sitter, ast-grep, and LSP code intelligence tools.",
        )

    ctx.register_tool(
        name="talaria_retrieve",
        toolset="talaria",
        schema=TALARIA_RETRIEVE_SCHEMA,
        handler=lambda args, **kw: handle_retrieve(_compressor, args, **kw),
    )
    ctx.register_tool(
        name="talaria_stats",
        toolset="talaria",
        schema=TALARIA_STATS_SCHEMA,
        handler=lambda args, **kw: handle_stats(_compressor, args, **kw),
    )
    ctx.register_tool(
        name="talaria_compress",
        toolset="talaria",
        schema=TALARIA_COMPRESS_SCHEMA,
        handler=lambda args, **kw: handle_compress(_compressor, args, **kw),
    )

    _register_code_intel()

    ctx.register_hook("transform_terminal_output", _compressor.transform_terminal_output)
    ctx.register_hook("transform_tool_result", _compressor.transform_tool_result)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_command(
        "talaria",
        handler=_handle_talaria_slash,
        description="Show or clear Talaria compression state.",
    )
