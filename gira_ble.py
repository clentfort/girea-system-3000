"""Bluetooth LE communication for Gira System 3000 devices."""
import asyncio
import logging
from typing import Any

from bleak import BleakClient, BleakError, BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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


def parse_gira_broadcast(service_info: BluetoothServiceInfoBleak) -> int | None:
    """
    Parses Gira broadcast data to extract the shutter position.

    :param service_info: Bluetooth service information.
    :return: The shutter position as a percentage (0-100), or None if not found.
    """
    manufacturer_data = service_info.manufacturer_data.get(GIRA_MANUFACTURER_ID)

    if not manufacturer_data:
        # Not a Gira device
        return None

    # Check for the correct broadcast prefix and a total length of 8 bytes
    if not manufacturer_data.startswith(BROADCAST_PREFIX) or len(manufacturer_data) != 8:
        LOGGER.debug(
            "Ignoring Gira broadcast with invalid data: %s", manufacturer_data.hex()
        )
        return None

    # The position is the 8th byte (index 7)
    position_byte = manufacturer_data[7]

    # Convert the device's position (0x00=open, 0xFF=closed) to HA's percentage (100=open, 0=closed)
    # The calculation is: ha_pos = 100 * (255 - device_pos) / 255
    ha_position = round(100 * (255 - position_byte) / 255)

    LOGGER.debug(
        "Gira broadcast received. Raw position: %s, Converted HA position: %s%%",
        hex(position_byte),
        ha_position,
    )

    return ha_position


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

        # Create a DataUpdateCoordinator for managing state updates from broadcasts
        self.coordinator = DataUpdateCoordinator[int](
            hass,
            LOGGER,
            name=f"Gira Shutter {name}",
            # No need for a specific update method here, as updates
            # will be pushed from the Bluetooth callback.
        )

    def handle_broadcast(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """
        Handle a BLE broadcast advertisement.
        This is called from the central Bluetooth callback.
        """
        LOGGER.debug("Handling Gira broadcast: %s", service_info)
        position = parse_gira_broadcast(service_info)
        if position is not None:
            LOGGER.debug("Updating coordinator with new position: %s%%", position)
            # Update the coordinator with the new position
            self.coordinator.async_set_update_data(position)
        else:
            LOGGER.debug("No valid position data found in broadcast.")

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

    async def set_ventilation_position(self) -> None:
        """Set the blinds to the ventilation position (50%)."""
        await self.send_command(generate_position_command(50))
