"""Tests for Apple TV media-player power and listener-driven regressions."""

from pyatv.const import DeviceState, FeatureName, FeatureState
import pytest

from homeassistant.components import media_player
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.asyncio


async def _one_media_player(hass: HomeAssistant) -> str:
    """Return the single Apple TV media player entity id."""
    entities = hass.states.async_entity_ids(media_player.DOMAIN)
    assert entities, "Media player entity was not created"
    return entities[0]


# --------------------------------------------------------------------
# Unified PowerState-parametrized tests
# --------------------------------------------------------------------


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_powerstate_behavior_variants(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Verify both PowerState and no-PowerState variants handle power correctly."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    # Turn off
    await atv.power.turn_off()
    await hass.async_block_till_done()
    state_off = hass.states.get(entity_id).state

    powerstate_supported = atv.features.in_state(
        FeatureState.Available, FeatureName.PowerState
    )
    if powerstate_supported:
        assert state_off == media_player.MediaPlayerState.OFF
    else:
        assert state_off in (media_player.MediaPlayerState.IDLE, None)

    # Turn on
    await atv.power.turn_on()
    await hass.async_block_till_done()
    state_on = hass.states.get(entity_id).state
    assert state_on in (
        media_player.MediaPlayerState.ON,
        media_player.MediaPlayerState.IDLE,
    )


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_off_sets_state_off(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Power off (external event) updates state to OFF."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.power.turn_off()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id).state
    if atv.features.in_state(FeatureState.Available, FeatureName.PowerState):
        assert state == media_player.MediaPlayerState.OFF
    else:
        assert state in (media_player.MediaPlayerState.IDLE, None)


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_on_restores_state(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Turning back on (external event) restores a non-OFF state."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.power.turn_off()
    await hass.async_block_till_done()

    await atv.power.turn_on()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id).state
    assert state in (
        media_player.MediaPlayerState.ON,
        media_player.MediaPlayerState.IDLE,
    )


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_spontaneous_power_off_from_playing(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Apple TV turns off while playing (no HA interaction)."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.push_updater.trigger_playing(DeviceState.Playing)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PLAYING

    await atv.power.turn_off()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id).state
    if atv.features.in_state(FeatureState.Available, FeatureName.PowerState):
        assert state == media_player.MediaPlayerState.OFF
    else:  # Without powerstate feature player remains PLAYING
        assert state == media_player.MediaPlayerState.PLAYING


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_spontaneous_power_on_after_external_off(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Apple TV turns on externally after being off."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.power.turn_off()
    await hass.async_block_till_done()
    await atv.power.turn_on()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id).state
    assert state in (
        media_player.MediaPlayerState.ON,
        media_player.MediaPlayerState.IDLE,
    )


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_listener_playing_state_update(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """HA updates entity state when pyatv.push_updater notifies playback change."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.push_updater.trigger_playing(DeviceState.Playing)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PLAYING

    await atv.push_updater.trigger_playing(DeviceState.Paused)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PAUSED


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_listener_app_update_reflects_source_change(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """HA reflects app/source updates sent via push_updater."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    state = hass.states.get(entity_id)
    attrs = state.attributes
    assert (
        "Netflix" in attrs.get("app_name", "")
        or attrs.get("source") == "Netflix"
        or (attrs.get("source_list") and "Netflix" in attrs["source_list"])
    )

    await atv.push_updater.trigger_app_update("com.google.ios.youtube", "YouTube")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    attrs = state.attributes
    assert (
        "YouTube" in attrs.get("app_name", "")
        or attrs.get("source") == "YouTube"
        or (attrs.get("source_list") and "YouTube" in attrs["source_list"])
    )


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_cycle_multiple_times(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Verify entity recovers correctly after multiple power toggles."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    for _ in range(3):
        await atv.power.turn_off()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id).state
        if atv.features.in_state(FeatureState.Available, FeatureName.PowerState):
            assert state == media_player.MediaPlayerState.OFF
        else:
            assert state in (media_player.MediaPlayerState.IDLE, None)

        await atv.power.turn_on()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state in (
            media_player.MediaPlayerState.ON,
            media_player.MediaPlayerState.IDLE,
        )


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_state_from_idle_to_playing_and_off(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Verify transition Idle → Playing → Off updates state correctly."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.push_updater.trigger_playing(DeviceState.Idle)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.IDLE

    await atv.push_updater.trigger_playing(DeviceState.Playing)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PLAYING

    await atv.power.turn_off()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id).state
    if atv.features.in_state(FeatureState.Available, FeatureName.PowerState):
        assert state == media_player.MediaPlayerState.OFF
    else:  # Without powerstate feature player remains PLAYING
        assert state == media_player.MediaPlayerState.PLAYING
