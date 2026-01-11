# Girea System 3000

This is a custom component for Home Assistant to integrate the Gira System 3000 devices via
espHome bluetooth proxy or other bluetooth adapters.

Currently just the shutter controller "Jal+Schaltuhr" are implemented and tested.

> [!NOTE]
> Code was generated with Gemini 2.5 Flash support.

### Installation:

#### HACS

- Ensure that HACS is installed
- Add this repository as a custom repository
- Search for and install the "Girea System 3000" integration
- Restart Home Assistant

#### Manual installation

- Download the latest release
- Unpack the release and copy the custom_components/danfoss_ally directory into the 
  custom_components directory of your Home Assistant installation
- Restart Home Assistant

## Setup

First of all you need to get the bluetooth address manually:

- Fristly bring the shutter controller "Jal+Schaltuhr" in pairing mode to scan the bluetooth MAC 
  address and find it in the bluetooth monitoring in Home Assistant
- Note the MAC address down for setting it up in the Home Assistant integration
- Add a new Device to the Girea integration using its MAC address and give it a name. It is important
  having the shutter contrller in paring mode during setup in the integration
- Finally push any button on the cover integration (up/down) while the device is in pairing mode
  again

## Known issues

- There is still a little delay between pushing the button in the home assistant ui and actual start
  of the shutter movement.