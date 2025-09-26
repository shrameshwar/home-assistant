"""Tests for Yardian sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pyyardian.async_client import YardianDeviceState

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


class FakeYardianClient:
    """Fake AsyncYardianClient with minimal sensor data."""

    def __init__(self, *_: object, **__: object) -> None:
        """Create async mocks for actions used by the integration."""
        self.stop_irrigation = AsyncMock()
        self.start_irrigation = AsyncMock()

    async def fetch_device_state(self) -> YardianDeviceState:
        """Return fake device state with three zones and one active."""
        zones = [["Zone 1", 1], ["Zone 2", 0], ["Zone 3", 1]]
        active_zones = {0}
        return YardianDeviceState(zones=zones, active_zones=active_zones)

    async def fetch_oper_info(self) -> dict[str, object]:
        """Return fake operation info used by sensors."""
        return {
            "iRainDelay": 3600,
            "iSensorDelay": 5,
            "iWaterHammerDuration": 2,
            "region": "US",
        }


def _mock_entry() -> MockConfigEntry:
    """Return a configured Yardian config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "access_token": "abc",
            "name": "Yardian",
            "yid": "yid123",
            "model": "PRO1902",
            "serialNumber": "SN1",
        },
        title="Yardian Smart Sprinkler",
        unique_id="yid123",
    )


@pytest.mark.asyncio
async def test_sensor_states(hass: HomeAssistant) -> None:
    """Verify main Yardian sensors report expected values."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    rain_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "yid123-rain-delay")
    assert rain_id is not None
    rain_state = hass.states.get(rain_id)
    assert rain_state is not None
    assert rain_state.state == "3600"
    assert rain_state.attributes.get("device_class") == "duration"
    assert rain_state.attributes.get("unit_of_measurement") == "s"

    zone_count_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, "yid123-active-zone-count"
    )
    assert zone_count_id is not None
    zone_count_state = hass.states.get(zone_count_id)
    assert zone_count_state is not None
    assert zone_count_state.state == "1"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "yid123")})
    assert device is not None
    assert device.serial_number == "SN1"


@pytest.mark.asyncio
async def test_diagnostic_sensors(hass: HomeAssistant) -> None:
    """Diagnostic sensors are disabled by default but report values when enabled."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    diag_sensor_uids = (
        "yid123-sensor-delay",
        "yid123-water-hammer-duration",
        "yid123-region",
    )

    for uid in diag_sensor_uids:
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
        assert entity_id is not None
        reg_entry = ent_reg.async_get(entity_id)
        assert reg_entry is not None
        assert reg_entry.disabled
        assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert reg_entry.entity_category is EntityCategory.DIAGNOSTIC
        ent_reg.async_update_entity(entity_id, disabled_by=None)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    for uid in diag_sensor_uids:
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
        state = hass.states.get(entity_id)
        assert state is not None

    sensor_delay = hass.states.get(
        ent_reg.async_get_entity_id("sensor", DOMAIN, "yid123-sensor-delay")
    )
    assert sensor_delay is not None
    assert sensor_delay.state == "5"
    assert sensor_delay.attributes.get("device_class") == "duration"
    assert sensor_delay.attributes.get("unit_of_measurement") == "s"

    water_hammer = hass.states.get(
        ent_reg.async_get_entity_id("sensor", DOMAIN, "yid123-water-hammer-duration")
    )
    assert water_hammer is not None
    assert water_hammer.state == "2"
    assert water_hammer.attributes.get("device_class") == "duration"
    assert water_hammer.attributes.get("unit_of_measurement") == "s"

    region = hass.states.get(
        ent_reg.async_get_entity_id("sensor", DOMAIN, "yid123-region")
    )
    assert region is not None
    assert region.state == "US"
