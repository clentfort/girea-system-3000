> [!IMPORTANT]
> **Maintenance update — continued development has moved**
>
> This repository is no longer the primary development location for this integration.
>
> The original maintainer has stepped back from active development, and ongoing maintenance is now
> being continued independently in the following repository:
>
> **➡️ [Continue to the actively maintained fork](https://github.com/stho/girea-system-3000)**
>
> ### What does this mean?
>
> - **Development and releases:** New fixes, features, and releases are published in the maintained
>   fork.
> - **Bug reports and feature requests:** Please open new issues in the fork's issue tracker.
> - **Installation and updates:** See the fork's README for the current installation instructions
>   and migration guide.
> - **Existing installations:** Your current installation is not automatically migrated. Please follow the migration instructions before switching to the fork.
>
> This repository remains available as a historical reference. Thank you to the original maintainer and all contributors for their work on this project.

# Girea System 3000

This is a custom component for Home Assistant to integrate the Gira System 3000 devices via
espHome bluetooth proxy or other bluetooth adapters.

Currently just the shutter controller "Jal+Schaltuhr" are implemented and tested.

> [!NOTE]
> Code was generated with Gemini 2.5 Flash support.

## Installation

### Option 1: HACS (Recommended)

1. **Prerequisite:** Ensure that HACS is installed and configured ([HACS Documentation](https://hacs.xyz)).
2. **Add Repository:** Add this repository as a custom repository in HACS.
3. **Download:** Search for and install the **"Girea System 3000"** integration.
4. **Restart:** Restart Home Assistant to apply the changes.

### Option 2: Manual Installation

1. **Download:** Download the latest release from the Releases page.
2. **Extract & Copy:** Unpack the archive and copy the contents of the root directory into the
   `custom_components/girea_system_3000` directory of your Home Assistant installation.
3. **Restart:** Restart Home Assistant to load the new integration.


## Setup

First, you need to retrieve the Bluetooth MAC address of your device manually:

1. **Enter Pairing Mode:** Put your "Jal+Schaltuhr" shutter controller into pairing mode.
2. **Scan for the Device:** Open the Bluetooth monitoring tool in Home Assistant to find the
   controller's MAC address.
   * *Note on range:* Ensure your Bluetooth adapter is **very close** to the Gira switch during this
     step so it can be detected. This proximity is **only required for the initial pairing process**;
     for regular switch commands later on, the adapter does not need to remain close to the switch.
3. **Record the Address:** Note down the MAC address for the next step.

Once you have the MAC address, follow these steps to add it to Home Assistant:

1. **Add the Device:** In Home Assistant, add a new device to the **Girea System 3000 integration**
   using the recorded MAC address and assign a name to it. **Important:** The shutter controller
   must still be in pairing mode during this configuration step.
2. **Finalize Pairing:** Put the device into pairing mode one last time, then press any button
   (e.g., Up or Down) on the cover integration dashboard to complete the connection.


## Known issues

- There is still a little delay between pushing the button in the home assistant ui and actual start
  of the shutter movement.
