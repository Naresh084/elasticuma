from __future__ import annotations

from pathlib import Path

from elasticuma.model_store import _physical_store_bytes


def test_store_size_counts_packed_and_hugging_face_files_without_symlink_duplicates(
    tmp_path: Path,
) -> None:
    packed = tmp_path / "packed/model.gturbo"
    blob = tmp_path / "huggingface/hub/models--x--y/blobs/hash"
    snapshot = tmp_path / "huggingface/hub/models--x--y/snapshots/revision/weight"
    packed.mkdir(parents=True)
    blob.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    (packed / "weights.bin").write_bytes(b"a" * 10)
    blob.write_bytes(b"b" * 20)
    snapshot.symlink_to(blob)
    assert _physical_store_bytes(tmp_path) == 30
