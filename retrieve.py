from __future__ import annotations

import json
from typing import Any


TALARIA_RETRIEVE_SCHEMA = {
    "name": "talaria_retrieve",
    "description": (
        "Retrieve original content behind a Talaria compression marker. "
        "Pass the hash from 'hash=...' or '<<ccr:...>>'. Optional query returns matching lines."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "hash": {"type": "string", "description": "Compression hash."},
            "query": {
                "type": "string",
                "description": "Optional text to search inside the original content.",
            },
        },
        "required": ["hash"],
    },
}


TALARIA_STATS_SCHEMA = {
    "name": "talaria_stats",
    "description": "Show Talaria compression and retrieval stats for this session.",
    "parameters": {"type": "object", "properties": {}},
}


TALARIA_COMPRESS_SCHEMA = {
    "name": "talaria_compress",
    "description": "Compress a large text block and store the original for talaria_retrieve.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Text to compress."},
            "tool_name": {
                "type": "string",
                "description": "Optional source label for the content.",
            },
        },
        "required": ["content"],
    },
}


def handle_retrieve(compressor: Any, args: dict[str, Any], **_: Any) -> str:
    result = compressor.retrieve(args["hash"], query=args.get("query"))
    return json.dumps(result, ensure_ascii=False)


def handle_stats(compressor: Any, args: dict[str, Any], **_: Any) -> str:
    return json.dumps(compressor.stats(), ensure_ascii=False)


def handle_compress(compressor: Any, args: dict[str, Any], **_: Any) -> str:
    result = compressor.compress_result(
        source="manual",
        tool_name=args.get("tool_name") or "talaria_compress",
        original=args["content"],
        metadata={},
    )
    return json.dumps({"compressed": result}, ensure_ascii=False)
