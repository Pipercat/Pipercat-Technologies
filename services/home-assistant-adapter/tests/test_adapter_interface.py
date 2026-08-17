import pytest

from home_assistant_adapter import HomeAssistantAdapter


def test_cannot_instantiate_abstract_adapter():
    with pytest.raises(TypeError):
        HomeAssistantAdapter()  # type: ignore[abstract]


def test_concrete_subclass_must_implement_all_methods():
    class Incomplete(HomeAssistantAdapter):
        async def import_devices(self):
            return []

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]
