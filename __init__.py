"""The Girea System 3000 (Gira Reverse Engineered) integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .gira_ble import GiraBLEClient, GiraPassiveBluetoothDataUpdateCoordinator

PLATFORMS = ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Girea System 3000 from a config entry."""
    address = entry.data["address"]
    name = entry.data.get("name", f"Gira Shutter {address[-5:].replace(':', '')}")

    # Create the coordinator that will listen for broadcasts
    coordinator = GiraPassiveBluetoothDataUpdateCoordinator(
        hass,
        address=address,
        name=name,
    )

    # Create the client that will send commands
    client = GiraBLEClient(hass, address, name)

    # Store both client and coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    # Forward the setup to the 'cover' platform.
    # The coordinator will automatically start listening when the entity subscribes to it.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # The coordinator handles its own cleanup of the bluetooth callback.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
