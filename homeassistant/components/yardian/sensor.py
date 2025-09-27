"""Sensors for Yardian integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class YardianSensorEntityDescription(SensorEntityDescription):
    """Entity description for Yardian sensors."""

    unique_id_suffix: str
    value_fn: Callable[[YardianUpdateCoordinator], StateType]


def _rain_delay_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return remaining rain delay in seconds."""
    state = coordinator.data
    if state is None:
        return None
    oper_info = getattr(state, "oper_info", {}) or {}
    val = oper_info.get("iRainDelay")
    if isinstance(val, int):
        return max(0, val)
    return None


def _active_zone_count_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return number of active zones."""
    state = coordinator.data
    if state is None:
        return None
    return len(state.active_zones)


def _sensor_delay_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return sensor delay duration in seconds."""
    state = coordinator.data
    if state is None:
        return None
    oper_info = getattr(state, "oper_info", {}) or {}
    val = oper_info.get("iSensorDelay")
    if isinstance(val, int):
        if val > 365 * 24 * 3600:
            now = int(dt_util.utcnow().timestamp())
            return max(0, val - now)
        return max(0, val)
    return None


def _water_hammer_duration_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return water hammer duration in seconds."""
    state = coordinator.data
    if state is None:
        return None
    oper_info = getattr(state, "oper_info", {}) or {}
    val = oper_info.get("iWaterHammerDuration")
    if isinstance(val, int):
        return val
    return None


def _region_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return controller region label."""
    state = coordinator.data
    if state is None:
        return None
    oper_info = getattr(state, "oper_info", {}) or {}
    val = oper_info.get("region")
    if isinstance(val, str) and val:
        return val
    return None


SENSOR_DESCRIPTIONS: tuple[YardianSensorEntityDescription, ...] = (
    YardianSensorEntityDescription(
        key="rain_delay",
        translation_key="rain_delay",
        unique_id_suffix="rain-delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rain_delay_value,
    ),
    YardianSensorEntityDescription(
        key="active_zone_count",
        translation_key="active_zone_count",
        unique_id_suffix="active-zone-count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_active_zone_count_value,
    ),
    YardianSensorEntityDescription(
        key="sensor_delay",
        translation_key="sensor_delay",
        unique_id_suffix="sensor-delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_sensor_delay_value,
    ),
    YardianSensorEntityDescription(
        key="water_hammer_duration",
        translation_key="water_hammer_duration",
        unique_id_suffix="water-hammer-duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_water_hammer_duration_value,
    ),
    YardianSensorEntityDescription(
        key="region",
        translation_key="region",
        unique_id_suffix="region",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_region_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yardian sensors."""
    coordinator: YardianUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        YardianSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class YardianSensor(CoordinatorEntity[YardianUpdateCoordinator], SensorEntity):
    """Representation of a Yardian sensor defined by description."""

    entity_description: YardianSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YardianUpdateCoordinator,
        description: YardianSensorEntityDescription,
    ) -> None:
        """Initialize the Yardian sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.yid}_{description.unique_id_suffix}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> StateType:
        """Return the value provided by the description."""
        return self.entity_description.value_fn(self.coordinator)
