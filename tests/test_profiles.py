from pathlib import Path

from adv_archon.core.profiles import ProfileDefinition, ProfileManager


def test_profile_manager_persists_active_profile(tmp_path: Path) -> None:
    state_file = tmp_path / "active-profile.txt"
    manager = ProfileManager(
        state_file,
        default_profile="general",
        definitions={
            "work": ProfileDefinition(
                name="work",
                description="Trabajo",
                system_hint="work",
                knowledge_roots=("~/Documents",),
                vault_roots=("~/Vault",),
            )
        },
    )

    selected = manager.set_active_profile("work")
    reloaded = ProfileManager(
        state_file,
        default_profile="general",
        definitions={
            "work": ProfileDefinition(
                name="work",
                description="Trabajo",
                system_hint="work",
                knowledge_roots=("~/Documents",),
                vault_roots=("~/Vault",),
            )
        },
    )

    assert selected == "work"
    assert reloaded.active_profile == "work"
    assert reloaded.knowledge_roots() == ("~/Documents",)
