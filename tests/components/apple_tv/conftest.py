"""Fixtures for Apple TV integration tests (config flow + runtime)."""

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pyatv import conf
from pyatv.const import (
    DeviceState,
    FeatureName,
    FeatureState,
    PairingRequirement,
    PowerState,
    Protocol,
)
from pyatv.support import http
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component as real_setup_component

from .common import MockPairingHandler, airplay_service, create_conf, mrp_service

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True, name="mock_scan")
def mock_scan_fixture() -> Generator[AsyncMock]:
    """Mock pyatv.scan."""
    with patch("homeassistant.components.apple_tv.config_flow.scan") as mock_scan:

        async def _scan(
            loop, timeout=5, identifier=None, protocol=None, hosts=None, aiozc=None
        ):
            if not mock_scan.hosts:
                mock_scan.hosts = hosts
            return mock_scan.result

        mock_scan.result = []
        mock_scan.hosts = None
        mock_scan.side_effect = _scan
        yield mock_scan


@pytest.fixture(name="dmap_pin")
def dmap_pin_fixture() -> Generator[MagicMock]:
    """Mock random PIN generation."""
    with patch("homeassistant.components.apple_tv.config_flow.randrange") as mock_pin:
        mock_pin.side_effect = lambda start, stop: 1111
        yield mock_pin


@pytest.fixture
def pairing() -> Generator[AsyncMock]:
    """Mock pyatv.pair with handler returning a MockPairingHandler."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            handler = MockPairingHandler(
                await http.create_session(session), config.get_service(protocol)
            )
            handler.always_fail = mock_pair.always_fail
            return handler

        mock_pair.always_fail = False
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture
def pairing_mock() -> Generator[AsyncMock]:
    """Simplified pairing mock."""
    with patch("homeassistant.components.apple_tv.config_flow.pair") as mock_pair:

        async def _pair(config, protocol, loop, session=None, **kwargs):
            return mock_pair

        async def _begin():
            pass

        async def _close():
            pass

        mock_pair.close.side_effect = _close
        mock_pair.begin.side_effect = _begin
        mock_pair.pin = lambda pin: None
        mock_pair.side_effect = _pair
        yield mock_pair


@pytest.fixture
def full_device(mock_scan: AsyncMock, dmap_pin: MagicMock) -> AsyncMock:
    """Device with MRP, DMAP, and AirPlay services."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "MRP Device",
            mrp_service(),
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                pairing_requirement=PairingRequirement.Mandatory,
            ),
            airplay_service(),
        )
    )
    return mock_scan


@pytest.fixture
def mrp_device(mock_scan: AsyncMock) -> AsyncMock:
    """Multiple MRP devices."""
    mock_scan.result.extend(
        [
            create_conf(
                "127.0.0.1",
                "MRP Device",
                mrp_service(),
            ),
            create_conf(
                "127.0.0.2",
                "MRP Device 2",
                mrp_service(unique_id="unrelated"),
            ),
        ]
    )
    return mock_scan


@pytest.fixture
def airplay_with_disabled_mrp(mock_scan: AsyncMock) -> AsyncMock:
    """AirPlay device with MRP disabled."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "AirPlay Device",
            mrp_service(enabled=False),
            conf.ManualService(
                "airplayid",
                Protocol.AirPlay,
                7777,
                {},
                pairing_requirement=PairingRequirement.Mandatory,
            ),
        )
    )
    return mock_scan


@pytest.fixture
def dmap_device(mock_scan: AsyncMock) -> AsyncMock:
    """DMAP device without credentials."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                credentials=None,
                pairing_requirement=PairingRequirement.Mandatory,
            ),
        )
    )
    return mock_scan


@pytest.fixture
def dmap_device_with_credentials(mock_scan: AsyncMock) -> AsyncMock:
    """DMAP device with credentials."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                credentials="dummy_creds",
                pairing_requirement=PairingRequirement.NotNeeded,
            ),
        )
    )
    return mock_scan


@pytest.fixture
def airplay_device_with_password(mock_scan: AsyncMock) -> AsyncMock:
    """AirPlay device requiring password."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "AirPlay Device",
            conf.ManualService(
                "airplayid", Protocol.AirPlay, 7777, {}, requires_password=True
            ),
        )
    )
    return mock_scan


@pytest.fixture
def dmap_with_requirement(
    mock_scan: AsyncMock, pairing_requirement: PairingRequirement
) -> AsyncMock:
    """DMAP device with specific pairing requirement."""
    mock_scan.result.append(
        create_conf(
            "127.0.0.1",
            "DMAP Device",
            conf.ManualService(
                "dmapid",
                Protocol.DMAP,
                6666,
                {},
                pairing_requirement=pairing_requirement,
            ),
        )
    )
    return mock_scan


class DummyPower:
    """Simulate pyatv.power with listener callbacks and async on/off."""

    def __init__(self) -> None:
        """Initialize power state and listener."""
        self.listener = None
        self.power_state = PowerState.On

    async def _notify(self, old: PowerState, new: PowerState) -> None:
        """Notify all listeners asynchronously."""
        if self.listener and hasattr(self.listener, "powerstate_update"):
            self.listener.powerstate_update(old, new)
        # Yield control so hass can process state updates
        await asyncio.sleep(0)

    async def turn_off(self) -> None:
        """Simulate turning off the device."""
        old = self.power_state
        self.power_state = PowerState.Off
        await self._notify(old, self.power_state)

    async def turn_on(self) -> None:
        """Simulate turning on the device."""
        old = self.power_state
        self.power_state = PowerState.On
        await self._notify(old, self.power_state)


class DummyPushUpdater:
    """Simulate pyatv.push_updater with listener behavior."""

    def __init__(self) -> None:
        """Initialize push updater state and listener."""
        self.listener = None
        self.is_active = True
        self.playing_state = SimpleNamespace(
            device_state=DeviceState.Paused,
            content_identifier="abc123",
            position=42,
            total_time=300,
            media_type=None,
            title="Demo Song",
            artist="Mock Artist",
            album="Mock Album",
            series_name=None,
            season_number=None,
            episode_number=None,
            repeat=None,
            shuffle=None,
        )

    def start(self) -> None:
        """Start the push updater."""
        self.is_active = True

    def stop(self) -> None:
        """Stop the push updater."""
        self.is_active = False

    async def trigger_playing(self, new_state: DeviceState) -> None:
        """Simulate a playstatus update event."""
        self.playing_state.device_state = new_state
        if self.listener and hasattr(self.listener, "playstatus_update"):
            self.listener.playstatus_update(self, self.playing_state)

    async def trigger_app_update(self, identifier="com.netflix.app", name="Netflix"):
        """Simulate an app/source change event."""
        if self.listener and hasattr(self.listener, "app_update"):
            self.listener.app_update(self, identifier, name)


@pytest.fixture
def dummy_atv_runtime() -> AsyncMock:
    """Unified dummy Apple TV device mock with runtime listener-capable subsystems."""
    atv = AsyncMock()

    # Power
    atv.power = DummyPower()

    # Remote control with async methods
    atv.remote_control = AsyncMock()
    for name in (
        "play",
        "pause",
        "stop",
        "next",
        "previous",
        "play_pause",
        "set_position",
        "set_repeat",
        "set_shuffle",
    ):
        setattr(atv.remote_control, name, AsyncMock())
    # Audio control
    atv.audio = AsyncMock()
    atv.audio.volume = 50.0
    atv.audio.muted = False

    async def set_volume(level):
        atv.audio.volume = level

    async def set_muted(state):
        atv.audio.muted = state

    atv.audio.set_volume = AsyncMock(side_effect=set_volume)
    atv.audio.set_muted = AsyncMock(side_effect=set_muted)
    atv.audio.volume_up = AsyncMock()
    atv.audio.volume_down = AsyncMock()

    # Metadata / state
    atv.metadata = SimpleNamespace(
        device_id="dummyid",
        app=SimpleNamespace(name="Netflix", identifier="com.netflix.app"),
        artwork_id="dummy_art_id",
        artwork=AsyncMock(
            return_value=SimpleNamespace(bytes=b"fake", mimetype="image/png")
        ),
    )
    atv.metadata.app = SimpleNamespace(name="Netflix", identifier="com.netflix.app")
    atv.apps = AsyncMock()
    atv.apps.app_list = AsyncMock(
        return_value=[
            SimpleNamespace(name="Netflix", identifier="com.netflix.app"),
            SimpleNamespace(name="YouTube", identifier="com.google.ios.youtube"),
        ]
    )
    atv.device_info = SimpleNamespace(name="Dummy TV")
    atv.features = AsyncMock()

    all_feats = {f: SimpleNamespace(state=FeatureState.Available) for f in FeatureName}

    atv.features.in_state = lambda state, feature: True
    atv.features.all_features = lambda: all_feats
    # Push updater
    atv.push_updater = DummyPushUpdater()

    async def _close():
        return None

    atv.close = _close
    return atv


# --------------------------------------------------------------------------------------
# Fixture to bootstrap a runtime integration
# --------------------------------------------------------------------------------------


@pytest.fixture
async def setup_runtime_integration(
    hass: HomeAssistant, dummy_atv_runtime, request: pytest.FixtureRequest
) -> tuple[MockConfigEntry, AsyncMock]:
    """Set up Apple TV integration using runtime dummy (for media_player tests)."""

    powerstate_enabled = getattr(request, "param", True)

    # Modify dummy to simulate missing PowerState feature
    if not powerstate_enabled:

        def _in_state(state, feature):
            return feature != FeatureName.PowerState

        dummy_atv_runtime.features.in_state = _in_state

    async def _fake_setup_component(hass, domain, config):
        """Intercept setup_component calls."""
        if domain == "zeroconf":
            return True
        return await real_setup_component(hass, domain, config)

    async def _fake_connect_once(self, raise_missing_credentials=True):
        """Simulate Apple TV connecting successfully."""
        atv = dummy_atv_runtime
        self.atv = atv
        self.close = atv.close
        # Notify any entities listening for connection
        for listener in getattr(self, "listeners", []):
            if hasattr(listener, "async_device_connected"):
                listener.async_device_connected(atv)
        return True

    with (
        patch(
            "homeassistant.components.apple_tv.AppleTVManager.connect",
            return_value=dummy_atv_runtime,
        ),
        patch(
            "homeassistant.components.apple_tv.async_unload_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.apple_tv.media_player.AppleTVManager.connect",
            return_value=dummy_atv_runtime,
        ),
        patch(
            "homeassistant.components.apple_tv.AppleTVManager._connect_once",
            new=_fake_connect_once,
        ),
        patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.zeroconf.async_get_async_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.setup.async_setup_component",
            side_effect=_fake_setup_component,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Dummy TV",
            data={
                "address": "127.0.0.1",
                "host": "127.0.0.1",
                "identifier": "dummyid",
                "name": "Dummy TV",
                "credentials": {"3": "abc123", "1": "xyz789"},
            },
            unique_id="dummyid_runtime"
            + ("_nopower" if not powerstate_enabled else ""),
        )
        entry.add_to_hass(hass)

        # Run normal setup (this will call our _fake_connect_once)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Ensure domain data exists
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        # Try to find all entities for this integration and connect them
        for entity_id in hass.states.async_entity_ids("media_player"):
            comp = hass.data["entity_components"]["media_player"]
            entity_obj = comp.get_entity(entity_id)
            if entity_obj and hasattr(entity_obj, "async_device_connected"):
                entity_obj.async_device_connected(dummy_atv_runtime)

        await hass.async_block_till_done()
        dummy_atv_runtime.power.power_state = PowerState.On
        await dummy_atv_runtime.power._notify(PowerState.Off, PowerState.On)
        await dummy_atv_runtime.push_updater.trigger_playing(DeviceState.Idle)
        await hass.async_block_till_done()
        return entry, dummy_atv_runtime
