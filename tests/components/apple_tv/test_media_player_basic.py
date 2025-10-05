"""Basic Apple TV media player integration tests."""

import pytest

from homeassistant.components import media_player
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.asyncio


async def _one_media_player(hass: HomeAssistant) -> str:
    """Return the single Apple TV media player entity id."""
    entities = hass.states.async_entity_ids(media_player.DOMAIN)
    assert entities, "Media player entity was not created"
    return entities[0]


async def test_entity_available(hass: HomeAssistant, setup_runtime_integration) -> None:
    """Ensure entity is created and available with a sane initial state."""
    _, _ = setup_runtime_integration
    entity_id = await _one_media_player(hass)
    state = hass.states.get(entity_id)
    assert state.state in (
        media_player.MediaPlayerState.PAUSED,
        media_player.MediaPlayerState.IDLE,
        media_player.MediaPlayerState.ON,
    )


async def test_media_play_and_pause(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Verify play/pause service calls are forwarded correctly."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await hass.services.async_call(
        media_player.DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    atv.remote_control.play.assert_awaited_once()

    await hass.services.async_call(
        media_player.DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    atv.remote_control.pause.assert_awaited_once()


async def test_turn_on_off_services_affect_state(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Test that turn_on/turn_off services change entity state."""
    _, _ = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await hass.services.async_call(
        media_player.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.OFF

    await hass.services.async_call(
        media_player.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state in (
        media_player.MediaPlayerState.ON,
        media_player.MediaPlayerState.IDLE,
    )
