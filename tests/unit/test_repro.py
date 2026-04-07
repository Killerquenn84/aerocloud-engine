"""Tests for reproducibility ID computation."""

from __future__ import annotations

from aerocloud.repro import ReproducibilityID, canonical_input_hash, compute_id


def test_canonical_hash_is_key_order_independent() -> None:
    a = canonical_input_hash({"a": 1, "b": 2})
    b = canonical_input_hash({"b": 2, "a": 1})
    assert a == b


def test_canonical_hash_detects_value_change() -> None:
    a = canonical_input_hash({"a": 1})
    b = canonical_input_hash({"a": 2})
    assert a != b


def test_compute_id_deterministic_without_output() -> None:
    payload = {"text": "hello world", "width": 1024, "height": 1024}
    a = compute_id(payload, seed=42)
    b = compute_id(payload, seed=42)
    assert a == b
    assert a.input_hash == b.input_hash
    assert a.output_hash == b.output_hash


def test_compute_id_seed_affects_output() -> None:
    payload = {"text": "hello", "width": 512, "height": 512}
    a = compute_id(payload, seed=1)
    b = compute_id(payload, seed=2)
    assert a.input_hash == b.input_hash  # same payload
    assert a.output_hash != b.output_hash  # different seed


def test_compute_id_with_output_bytes() -> None:
    payload = {"text": "abc"}
    rid = compute_id(payload, seed=42, output_bytes=b"render-output-bytes")
    assert len(rid.output_hash) == 64  # sha256 hex
    # output_hash must be derived from bytes, not seed
    rid2 = compute_id(payload, seed=42, output_bytes=b"different-bytes")
    assert rid.output_hash != rid2.output_hash


def test_fingerprint_format() -> None:
    payload = {"x": 1}
    rid = compute_id(payload, seed=42)
    fp = rid.fingerprint
    assert ":" in fp
    assert "->" in fp
    assert rid.version in fp
    assert str(rid.seed) in fp


def test_roundtrip() -> None:
    rid = compute_id({"x": 1}, seed=42)
    payload = rid.model_dump_json()
    restored = ReproducibilityID.model_validate_json(payload)
    assert restored == rid
