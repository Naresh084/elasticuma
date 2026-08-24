from __future__ import annotations

import json
from pathlib import Path

import pytest

from elasticuma.adapters import CommandResultAdapter


def test_adapter_parses_one_unambiguous_result(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "decode_tps": 12.5,
                "text": "hello",
                "token_ids": [1, 2],
                "expert_hit_rate": 0.75,
            }
        ),
        encoding="utf-8",
    )
    stdout = tmp_path / "stdout"
    stderr = tmp_path / "stderr"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    parsed = CommandResultAdapter().parse(
        stdout_path=stdout,
        stderr_path=stderr,
        result_path=result_path,
    )
    assert parsed.decode_tps == 12.5
    assert parsed.output_sha256 is not None
    assert parsed.token_ids_sha256 is not None


def test_adapter_rejects_ambiguous_stdout(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout"
    stderr = tmp_path / "stderr"
    stdout.write_text(
        'ELASTICUMA_RESULT={"decode_tps":1}\nELASTICUMA_RESULT={"decode_tps":2}\n',
        encoding="utf-8",
    )
    stderr.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="expected one"):
        CommandResultAdapter().parse(
            stdout_path=stdout,
            stderr_path=stderr,
            result_path=tmp_path / "missing.json",
        )
