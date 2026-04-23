from adv_archon.core.config import LLMConfig
from adv_archon.core.llm import LLMRouter


def test_temporary_mode_overrides_and_restores() -> None:
    router = LLMRouter(LLMConfig(mode="cloud"))

    assert router.mode == "cloud"
    with router.temporary_mode("local"):
        assert router.mode == "local"
    assert router.mode == "cloud"
