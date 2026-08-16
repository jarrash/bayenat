import hashlib

from app.services.integrity import audit_event_hash, canonical_json, sha256_file


def test_sha256_file(tmp_path):
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"bayenat-evidence")
    assert sha256_file(path) == hashlib.sha256(b"bayenat-evidence").hexdigest()


def test_canonical_json_is_stable():
    assert canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_audit_hash_changes_when_chain_changes():
    payload = {"event_type": "UPLOADED", "evidence_id": "e-1"}
    first = audit_event_hash(payload, None)
    second = audit_event_hash({"event_type": "HASHED", "evidence_id": "e-1"}, first)
    tampered = audit_event_hash({"event_type": "HASHED", "evidence_id": "e-2"}, first)
    assert first != second
    assert second != tampered
