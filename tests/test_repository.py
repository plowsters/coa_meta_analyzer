from pathlib import Path

import pytest

from coa_meta.repository import RepositoryLoadError, TalentRepository


FIXTURE = Path(__file__).parent / "fixtures" / "legal_build_fixture.jsonl"


def test_repository_loads_nodes_by_class_and_name():
    repo = TalentRepository.from_entries(FIXTURE)

    nodes = repo.nodes_for_class("Testclass")

    assert len(nodes) == 6
    assert repo.node_by_name("Testclass", "poison talent").entry_id == 102
    assert repo.node_by_name("Testclass", "unlocked free poison").entry_id == 104
    assert repo.node_by_id(101).class_name == "Testclass"


def test_repository_rejects_wrong_schema_version(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(FIXTURE.read_text().replace("coa-normalized-v1", "old-version", 1), encoding="utf-8")

    with pytest.raises(RepositoryLoadError, match="schema_version"):
        TalentRepository.from_entries(bad)
