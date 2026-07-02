from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


DEFAULT_EXCLUDED_TOOLS = {
    "read_file",
    "talaria_retrieve",
    "headroom_retrieve",
}


@dataclass
class StoreEntry:
    original_content: str
    compressed_content: str
    source: str
    tool_name: str
    original_tokens: int
    compressed_tokens: int
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TalariaCompressor:
    def __init__(
        self,
        *,
        min_chars: int = 6000,
        compress_text: Callable[[str], str] | None = None,
    ) -> None:
        self.min_chars = min_chars
        self._compress_text = compress_text
        self._store: dict[str, StoreEntry] = {}
        self._compressions = 0
        self._retrievals = 0
        self._tokens_saved = 0
        self._recent_events: list[dict[str, Any]] = []

    def transform_terminal_output(
        self,
        command: str,
        output: str,
        returncode: int | None = None,
        task_id: str | None = None,
        env_type: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        if len(output) < self.min_chars:
            return None
        return self.compress_result(
            source="terminal",
            tool_name="terminal",
            original=output,
            metadata={
                "command": command,
                "returncode": returncode,
                "task_id": task_id or "",
                "env_type": env_type or "",
            },
        )

    def transform_tool_result(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        result: str | None = None,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        if not isinstance(result, str):
            return None
        if self._excluded_tool(tool_name):
            return None
        if len(result) < self.min_chars:
            return None
        return self.compress_result(
            source="tool",
            tool_name=tool_name,
            original=result,
            metadata={"args": args or {}, "task_id": task_id or ""},
        )

    def compress_result(
        self,
        *,
        source: str,
        tool_name: str,
        original: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        compressed = self._run_headroom(original)
        original_tokens = self._estimate_tokens(original)
        compressed_tokens = self._estimate_tokens(compressed)
        hash_key = self._store_original(
            original=original,
            compressed=compressed,
            source=source,
            tool_name=tool_name,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            metadata=metadata or {},
        )
        saved = max(0, original_tokens - compressed_tokens)
        self._compressions += 1
        self._tokens_saved += saved
        self._record_event(
            {
                "type": "compress",
                "source": source,
                "tool_name": tool_name,
                "hash": hash_key,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "tokens_saved": saved,
            }
        )
        return self._format_compressed_result(
            source=source,
            tool_name=tool_name,
            hash_key=hash_key,
            compressed=compressed,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            tokens_saved=saved,
        )

    def retrieve(self, hash_value: str, query: str | None = None) -> dict[str, Any]:
        hash_key = normalize_hash(hash_value)
        entry = self._store[hash_key]
        self._retrievals += 1
        self._record_event(
            {
                "type": "retrieve",
                "hash": hash_key,
                "tool_name": entry.tool_name,
                "query": query or "",
            }
        )
        if query:
            needle = query.casefold()
            matches = [
                line
                for line in entry.original_content.splitlines()
                if needle in line.casefold()
            ]
            return {
                "hash": hash_key,
                "results": matches,
                "source": "local",
                "tool_name": entry.tool_name,
            }
        return {
            "hash": hash_key,
            "original_content": entry.original_content,
            "original_tokens": entry.original_tokens,
            "tool_name": entry.tool_name,
            "source": "local",
        }

    def stats(self) -> dict[str, Any]:
        return {
            "compressions": self._compressions,
            "retrievals": self._retrievals,
            "tokens_saved": self._tokens_saved,
            "stored_items": len(self._store),
            "recent_events": list(self._recent_events[-10:]),
        }

    def clear(self) -> None:
        self._store.clear()
        self._recent_events.clear()

    def _run_headroom(self, text: str) -> str:
        if self._compress_text is not None:
            return self._compress_text(text)

        from headroom.compression.universal import (
            UniversalCompressor,
            UniversalCompressorConfig,
        )

        compressor = UniversalCompressor(
            UniversalCompressorConfig(
                use_magika=False,
                use_kompress=False,
                ccr_enabled=False,
                compression_ratio_target=0.12,
            )
        )
        return compressor.compress(text).compressed

    def _store_original(
        self,
        *,
        original: str,
        compressed: str,
        source: str,
        tool_name: str,
        original_tokens: int,
        compressed_tokens: int,
        metadata: dict[str, Any],
    ) -> str:
        digest = hashlib.sha256()
        digest.update(original.encode("utf-8"))
        digest.update(str(time.time_ns()).encode("ascii"))
        hash_key = digest.hexdigest()[:16]
        self._store[hash_key] = StoreEntry(
            original_content=original,
            compressed_content=compressed,
            source=source,
            tool_name=tool_name,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            created_at=time.time(),
            metadata=metadata,
        )
        return hash_key

    def _format_compressed_result(
        self,
        *,
        source: str,
        tool_name: str,
        hash_key: str,
        compressed: str,
        original_tokens: int,
        compressed_tokens: int,
        tokens_saved: int,
    ) -> str:
        label = "terminal" if source == "terminal" else tool_name
        payload = {
            "hash": hash_key,
            "tool_name": tool_name,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": tokens_saved,
        }
        return (
            f"Talaria compressed {label} output "
            f"(hash={hash_key}). Use talaria_retrieve with this hash for the original.\n\n"
            f"{compressed}\n\n"
            f"[talaria] {json.dumps(payload, ensure_ascii=False)}"
        )

    def _record_event(self, event: dict[str, Any]) -> None:
        event["time"] = time.time()
        self._recent_events.append(event)
        if len(self._recent_events) > 50:
            del self._recent_events[:-50]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _excluded_tool(tool_name: str) -> bool:
        return tool_name in DEFAULT_EXCLUDED_TOOLS or tool_name.startswith("code_")


def normalize_hash(raw: str) -> str:
    value = str(raw).strip().strip("<>")
    if value.startswith("ccr:"):
        value = value.removeprefix("ccr:")
    if value.startswith("hash="):
        value = value.removeprefix("hash=")
    return value.split(",", 1)[0].strip()
