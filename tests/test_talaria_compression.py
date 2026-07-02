import json

from compression import TalariaCompressor


def test_terminal_output_below_threshold_is_unchanged():
    compressor = TalariaCompressor(min_chars=50)

    result = compressor.transform_terminal_output(
        command="printf hi",
        output="short output",
        returncode=0,
        task_id="t1",
        env_type="local",
    )

    assert result is None
    assert compressor.stats()["compressions"] == 0


def test_terminal_output_above_threshold_is_compressed_and_retrievable():
    compressor = TalariaCompressor(
        min_chars=20,
        compress_text=lambda text: "line 1\nline 2",
    )
    original = "\n".join(f"line {i}" for i in range(30))

    result = compressor.transform_terminal_output(
        command="find .",
        output=original,
        returncode=0,
        task_id="t1",
        env_type="local",
    )

    assert result is not None
    assert "Talaria compressed terminal output" in result
    assert "talaria_retrieve" in result
    assert "hash=" in result
    marker = result.split("hash=", 1)[1].split(")", 1)[0]
    assert compressor.retrieve(marker)["original_content"] == original
    assert compressor.stats()["compressions"] == 1


def test_transform_tool_result_excludes_read_file_and_talaria_tools():
    compressor = TalariaCompressor(min_chars=5)

    assert compressor.transform_tool_result("read_file", {}, "abcdef", "t1") is None
    assert compressor.transform_tool_result("talaria_retrieve", {}, "abcdef", "t1") is None
    assert compressor.transform_tool_result("code_symbols", {}, "abcdef", "t1") is None

    assert compressor.stats()["compressions"] == 0


def test_transform_tool_result_compresses_large_non_excluded_result():
    compressor = TalariaCompressor(
        min_chars=20,
        compress_text=lambda text: '{"items": 2}',
    )
    result = json.dumps({"items": [{"id": i, "name": f"item-{i}"} for i in range(50)]})

    transformed = compressor.transform_tool_result(
        tool_name="web_extract",
        args={"url": "https://example.test"},
        result=result,
        task_id="t1",
    )

    assert transformed is not None
    assert "Talaria compressed web_extract output" in transformed
    assert '{"items": 2}' in transformed
    assert compressor.stats()["tokens_saved"] > 0


def test_retrieve_accepts_marker_shapes_and_query_filters_lines():
    compressor = TalariaCompressor(min_chars=10, compress_text=lambda text: "summary")
    transformed = compressor.compress_result(
        source="terminal",
        tool_name="terminal",
        original="alpha\nbeta target\ngamma target\ndelta",
        metadata={"command": "grep target"},
    )
    marker = transformed.split("hash=", 1)[1].split(")", 1)[0]

    assert compressor.retrieve(f"<<ccr:{marker}>>")["original_content"].startswith("alpha")
    queried = compressor.retrieve(f"hash={marker}", query="target")
    assert queried["results"] == ["beta target", "gamma target"]
    assert compressor.stats()["retrievals"] == 2
