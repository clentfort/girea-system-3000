"""The Girea System 3000 (Gira Reverse Engineered) integration."""
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# We will define a 'bluetooth' module (like generic_bt's bluetooth.py)
# to handle the actual BLE communication.
from .const import DOMAIN, LOGGER
from .gira_ble import GiraBLEClient # This will be our custom BLE client class

# List of platforms (entity types) your integration will support.
# For roller shutters, we need the 'cover' platform.
PLATFORMS = ["cover"] # [2]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Girea System 3000 from a config entry."""
    LOGGER.debug("Setting up Girea System 3000 integration from config entry: %s", entry.entry_id)

    # The device's Bluetooth address and name will be stored in the config entry's data
    # by the config_flow.py when a device is discovered or manually added.
    address = entry.data["address"]
    name = entry.data.get("name", f"Gira Shutter {address[-5:].replace(':', '')}") # Provide a default name

    # Instantiate our custom GiraBLEClient.
    # This client will manage the BLE connection and send commands.
    # We pass the Home Assistant instance (hass) and the device details.
    gira_client = GiraBLEClient(hass, address, name)

    # Store the client instance in hass.data so other platforms (like cover.py) can access it.
    # This is a common pattern for sharing a single device connection across multiple entities.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = gira_client

    # Register a callback to handle incoming BLE broadcasts
    # This will call our GiraBLEClient's handler whenever a broadcast is received
    # from the specific device address.
    unsubscribe_callback = bluetooth.async_register_callback(
        hass,
        gira_client.handle_broadcast,
        bluetooth.BluetoothCallbackMatcher(address=address),
        bluetooth.BluetoothScanningMode.PASSIVE,
    )

    # Store the unsubscribe callback in runtime_data to be cleaned up on unload
    entry.runtime_data = unsubscribe_callback


    # Forward the setup to the 'cover' platform.
    # This tells Home Assistant to load the 'cover.py' file for this integration.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading Girea System 3000 integration for config entry: %s", entry.entry_id)

    # Unload platforms first. This will call `async_unload_platform` in `cover.py`.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Unsubscribe from the Bluetooth callback
        if entry.runtime_data:
            entry.runtime_data()

        # Clean up the client instance from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
