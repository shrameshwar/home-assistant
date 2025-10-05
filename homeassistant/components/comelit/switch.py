"""Support for switches."""

from __future__ import annotations

from typing import Any, cast

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import IRRIGATION, OTHER, STATE_OFF, STATE_ON

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ComelitConfigEntry, ComelitSerialBridge
from .entity import ComelitBridgeBaseEntity
from .utils import bridge_api_call, list_new_devices

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

BRIDGE_DEVICE_TYPES = (IRRIGATION, OTHER)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit switches."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    entities: list[ComelitSwitchEntity] = []

    for dev_type in BRIDGE_DEVICE_TYPES:
        entities.extend(
            ComelitSwitchEntity(coordinator, device, config_entry.entry_id)
            for device in coordinator.data[dev_type].values()
        )
    async_add_entities(entities)

    known_devices: dict[str, set[int]] = {
        dev_type: set() for dev_type in BRIDGE_DEVICE_TYPES
    }

    def _check_device() -> None:
        for dev_type in BRIDGE_DEVICE_TYPES:
            if new_devices := list_new_devices(
                coordinator.data[dev_type], known_devices[dev_type]
            ):
                async_add_entities(
                    ComelitSwitchEntity(coordinator, device, config_entry.entry_id)
                    for device in coordinator.data[dev_type].values()
                    if device.index in new_devices
                )

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


class ComelitSwitchEntity(ComelitBridgeBaseEntity, SwitchEntity):
    """Switch device."""

    _attr_name = None

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init switch entity."""
        super().__init__(coordinator, device, config_entry_entry_id)
        self._attr_unique_id = f"{config_entry_entry_id}-{device.type}-{device.index}"
        if device.type == OTHER:
            self._attr_device_class = SwitchDeviceClass.OUTLET

    @bridge_api_call
    async def _switch_set_state(self, state: int) -> None:
        """Set desired switch state."""
        await self.coordinator.api.set_device_status(
            self._device.type, self._device.index, state
        )
        self.coordinator.data[self._device.type][self._device.index].status = state
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch_set_state(STATE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._switch_set_state(STATE_OFF)

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return (
            self.coordinator.data[self._device.type][self._device.index].status
            == STATE_ON
        )
