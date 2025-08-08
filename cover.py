"""Platform for the Girea System 3000 cover integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER
from .gira_ble import GiraBLEClient, GiraPassiveBluetoothDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Girea System 3000 cover from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: GiraPassiveBluetoothDataUpdateCoordinator = data["coordinator"]
    client: GiraBLEClient = data["client"]

    # Add the Gira shutter as a Home Assistant Cover entity
    async_add_entities([GireaSystem3000Cover(coordinator, client, config_entry)])


class GireaSystem3000Cover(
    CoordinatorEntity[GiraPassiveBluetoothDataUpdateCoordinator], CoverEntity
):
    """Representation of a Gira System 3000 Cover."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
    )
    _attr_assumed_state = False

    def __init__(
        self,
        coordinator: GiraPassiveBluetoothDataUpdateCoordinator,
        client: GiraBLEClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=client.name,
            connections={(config_entry.entry_id, client.address)},
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self._client.send_up_command()
        except UpdateFailed:
            self._attr_available = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self._client.send_down_command()
        except UpdateFailed:
            self._attr_available = False
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self._client.send_stop_command()
        except UpdateFailed:
            self._attr_available = False
            self.async_write_ha_state()

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.coordinator.data

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data == 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug(
            "Cover entity received update. New position: %s",
            self.coordinator.data,
        )
        # This is called when the coordinator has new data.
        # The parent class `CoordinatorEntity` will handle writing the state to HA.
        self.async_write_ha_state()
