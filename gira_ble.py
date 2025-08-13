"""Bluetooth LE communication for Gira System 3000 devices."""
import asyncio
import logging
from typing import Any

from bleak import BleakClient, BleakError, BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.active_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, LOGGER

# Define the correct GATT Characteristic UUID.
GIRA_COMMAND_CHARACTERISTIC_UUID = "97696341-f77a-43ae-8c35-09f0c5245308"

# --- Constants for Gira Command Generation ---
# Basic command structure prefix
COMMAND_PREFIX = bytearray.fromhex("F6032001")

# Suffix constant often preceding the actual value
COMMAND_SUFFIX = bytearray.fromhex("1001")

# Property IDs for different command types
PROPERTY_ID_MOVE = 0xFF # For Up/Down commands
PROPERTY_ID_STOP = 0xFD # For Stop command
PROPERTY_ID_STEP = 0xFE # For Step Up/Down commands
PROPERTY_ID_SET_POSITION = 0xFC # For Absolute Position (Percentage)

# Values for commands
VALUE_UP = 0x00
VALUE_DOWN = 0x01
VALUE_STOP = 0x00 # Stop command uses 0x00 as its value


# --- Constants for Gira Broadcast Parsing ---
GIRA_MANUFACTURER_ID = 1412
# The correct, full prefix for a position broadcast
BROADCAST_PREFIX = bytearray.fromhex("F7032001F61001")


class GiraPassiveBluetoothDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator for receiving passive BLE broadcasts from Gira shutters."""

    def __init__(self, hass: HomeAssistant, address: str, name: str):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            address=address,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=False,
        )
        self._device_name = name  # Store name separately since 'name' property is read-only
        self.last_update_success = True  # We are available until we are not
        self.data = None  # Initialize data attribute
        LOGGER.debug("Created coordinator instance for %s (%s)", name, address)
        
        # Add additional debug logging
        LOGGER.debug("Coordinator address: %s, mode: %s, connectable: %s", 
                    address, bluetooth.BluetoothScanningMode.ACTIVE, False)

    async def async_start(self) -> None:
        """Start the coordinator if it's not already started."""
        LOGGER.debug("Starting coordinator for %s (%s)", self._device_name, self.address)
        # The parent class should handle the actual startup
        if hasattr(self, '_async_start') and callable(self._async_start):
            await self._async_start()
        else:
            LOGGER.debug("No _async_start method found, coordinator should start automatically")

    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        LOGGER.debug("Handle unavailable for %s (%s)", self._device_name, self.address)
        self.last_update_success = False
        self.async_update_listeners()

    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        LOGGER.debug(
            "Handle bluetooth event for %s (%s) - Change: %s, RSSI: %s, Device: %s", 
            self._device_name, 
            self.address, 
            change,
            service_info.rssi,
            service_info.device.address
        )
        
        # Check if this event is for our device
        if service_info.device.address.upper() != self.address.upper():
            LOGGER.debug(
                "Ignoring event from different device: %s (expected: %s)",
                service_info.device.address,
                self.address
            )
            return

        manufacturer_data = service_info.manufacturer_data.get(GIRA_MANUFACTURER_ID)
        LOGGER.debug(
            "Manufacturer data for %s (%s): %s", 
            self._device_name, 
            self.address, 
            manufacturer_data.hex() if manufacturer_data else "None"
        )

        if not manufacturer_data:
            LOGGER.debug("No manufacturer data found for manufacturer ID %s", GIRA_MANUFACTURER_ID)
            return

        # Debug: Show what we're looking for vs what we got
        LOGGER.debug("Looking for broadcast prefix: %s", BROADCAST_PREFIX.hex())
        LOGGER.debug("In manufacturer data: %s", manufacturer_data.hex())

        # Check if the BROADCAST_PREFIX is anywhere within the manufacturer_data
        try:
            # Find the starting index of the broadcast prefix
            prefix_index = manufacturer_data.find(BROADCAST_PREFIX)
            LOGGER.debug("Prefix found at index: %s", prefix_index)
        except (ValueError, AttributeError) as e:
            LOGGER.debug("Error searching for broadcast prefix: %s", e)
            return

        # Ensure we have enough bytes after the prefix to read the position
        if prefix_index == -1:
            LOGGER.debug("Broadcast prefix not found in manufacturer data")
            return
            
        if len(manufacturer_data) < prefix_index + len(BROADCAST_PREFIX) + 1:
            LOGGER.debug("Not enough data after broadcast prefix")
            return

        # Extract the position byte, which is 1 byte after the prefix
        position_byte = manufacturer_data[prefix_index + len(BROADCAST_PREFIX)]
        ha_position = round(100 * (255 - position_byte) / 255)

        LOGGER.info(
            "Gira broadcast received from %s. Raw data: %s, Position byte: %s, HA Position: %s%%",
            self._device_name,
            manufacturer_data.hex(),
            position_byte,
            ha_position,
        )
        
        # Update the data and notify listeners
        self.last_update_success = True
        self.async_set_updated_data(ha_position)


def _generate_command(property_id: int, value: int) -> bytearray:
    """Generates the full command byte array from its parts."""
    return (
        COMMAND_PREFIX
        + property_id.to_bytes(1, 'big')
        + COMMAND_SUFFIX
        + value.to_bytes(1, 'big')
    )

def generate_position_command(percentage: int) -> bytearray:
    """Generates the command for setting absolute blinds position."""
    if not 0 <= percentage <= 100:
        raise ValueError("Percentage must be between 0 and 100.")
    return _generate_command(PROPERTY_ID_SET_POSITION, percentage)


class GiraBLEClient:
    """Manages the Bluetooth LE connection and command sending for a Gira device."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the client."""
        self.hass = hass
        self.address = address
        self.name = name
        self._client: BleakClient | None = None
        self._is_connecting = asyncio.Lock()

    async def send_command(self, command: bytearray) -> None:
        """
        Connect to the device, send a command, and then disconnect.
        This is a single-shot, connect-on-demand method.
        """
        async with self._is_connecting:
            if self._client and self._client.is_connected:
                LOGGER.debug("Client already connected, sending command directly.")
                try:
                    # Log the command before sending it
                    LOGGER.debug("Sending command: %s", command.hex())
                    # Changed response to False
                    await self._client.write_gatt_char(GIRA_COMMAND_CHARACTERISTIC_UUID, command, response=False)
                    return
                except (BleakError, asyncio.TimeoutError) as e:
                    LOGGER.warning("Failed to send command to connected device: %s", e)
                    # Fall through to attempt a reconnect
                    await self._client.disconnect()
                    self._client = None
            
            LOGGER.debug("Attempting to connect to %s (%s) to send command.", self.name, self.address)
            
            device = bluetooth.async_ble_device_from_address(self.hass, self.address)
            if not device:
                LOGGER.error("Device %s (%s) not found in Home Assistant's Bluetooth devices.", self.name, self.address)
                raise UpdateFailed(f"Device {self.name} not found.")

            client = None
            try:
                client = await establish_connection(
                    BleakClient, 
                    device, 
                    self.name,
                    timeout=10,
                    max_attempts=3
                )
                self._client = client
                LOGGER.info("Successfully connected to %s (%s) and sending command.", self.name, self.address)

                # Log the command before sending it
                LOGGER.debug("Sending command: %s", command.hex())

                # Send the command, reponse=True is crucial
                await client.write_gatt_char(GIRA_COMMAND_CHARACTERISTIC_UUID, command, response=True)

                LOGGER.info("Command sent successfully to %s.", self.name)
            except (BleakError, asyncio.TimeoutError) as e:
                LOGGER.error("Failed to connect or send command to %s (%s): %s", self.name, self.address, e)
                raise UpdateFailed(f"Failed to connect and send command to {self.name}: {e}") from e
            finally:
                if client and client.is_connected:
                    LOGGER.info("Disconnecting from %s (%s) after sending command.", self.name, self.address)
                    await client.disconnect()
                self._client = None

    async def send_up_command(self) -> None:
        """Send the command to raise the shutter."""
        await self.send_command(_generate_command(PROPERTY_ID_MOVE, VALUE_UP))

    async def send_down_command(self) -> None:
        """Send the command to lower the shutter."""
        await self.send_command(_generate_command(PROPERTY_ID_MOVE, VALUE_DOWN))

    async def send_stop_command(self) -> None:
        """Send the command to stop the shutter."""
        await self.send_command(_generate_command(PROPERTY_ID_STOP, VALUE_STOP))

    async def send_step_up_command(self) -> None:
        """Send the command to step the shutter up."""
        await self.send_command(_generate_command(PROPERTY_ID_STEP, VALUE_UP))

    async def send_step_down_command(self) -> None:
        """Send the command to step the shutter down."""
        await self.send_command(_generate_command(PROPERTY_ID_STEP, VALUE_DOWN))

    async def set_absolute_position(self, percentage: int) -> None:
        """Set the absolute position of the blinds (0-100%)."""
        command = generate_position_command(percentage)
        await self.send_command(command)
