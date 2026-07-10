from pathlib import Path

from coa_client_extract.content_json import read_content_records

FIXTURES = Path(__file__).parent / "fixtures" / "client_content"


def test_reads_role_suggestions_with_provenance():
    records = read_content_records(FIXTURES, files={"SpellToRoleSuggestionData.json": "spell_role_suggestion"})
    assert len(records) == 2
    first = records[0]
    assert first["schema_version"] == "coa-client-content-v1"
    assert first["content_kind"] == "spell_role_suggestion"
    assert first["spell_id"] == 78
    assert first["values"]["TankScore"] == 69
    assert first["provenance"]["source_file"] == "SpellToRoleSuggestionData.json"
    assert len(first["provenance"]["file_sha256"]) == 64
    assert first["coa_attribution"]["status"] == "unknown"


def test_missing_file_is_skipped_not_fatal():
    records = read_content_records(FIXTURES, files={"DoesNotExist.json": "whatever"})
    assert records == []
