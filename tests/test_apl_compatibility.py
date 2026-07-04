from __future__ import annotations

from pathlib import Path

from coa_optimizer_extensible import generate_compat_rotation_lines

FIXTURE = Path(__file__).parent / "fixtures" / "apl_build_fixture.jsonl"


def test_compat_rotation_lines_delegate_to_package_generator():
    lines = generate_compat_rotation_lines(
        entries_path=FIXTURE,
        class_name="Testclass",
        profile_name="generic",
        encounter="single_target",
        selected_names=["Poison Talent", "Builder Strike", "Power Spender"],
        role="dps",
    )

    assert any(line.startswith("actions+=/poison_talent,if=dot.poison_talent.remains<gcd") for line in lines)
    assert any(line.startswith("actions+=/power_spender,if=energy>=80") for line in lines)
    assert any(line.startswith("actions+=/builder_strike,if=energy.deficit>0") for line in lines)
