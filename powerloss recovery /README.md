# ⚡ Klipper Power Loss Recovery (PLR) Configuration

This configuration modifies and implements a robust Power Loss Recovery system for Klipper, based on the approach by Travis90x. It uses a Python script (`plr.py`) and Klipper macros to save the print state (Z-height, temperatures, filename) during printing, allowing for a seamless resume after a power interruption.

-----

## 🚀 Setup and Installation

Follow these steps to integrate the Power Loss Recovery feature into your Klipper environment.

### 1\. Python Script Installation

The main logic for file generation and handling is contained in the Python script.

  * Place the `plr.py` file into your Klipper installation directory:

      * **Destination:** `/home/{your\_user\_name}/klipper/`

  * Navigate to the directory and grant execution permissions:

    ```bash
    cd /home/{your_user_name}/klipper/
    sudo chmod +x plr.py
    ```

### 2\. Klipper Configuration Files

You need to integrate the provided configuration file and enable necessary Klipper modules.

  * Place the `power_loss_recovery.cfg` file into your main Klipper configuration directory:
      * **Destination:** `/home/{your\_user\_name}/printer\_data/config/`

### 3\. Update `printer.cfg`

Add the following lines to your main `printer.cfg` file to include the macros and enable required functionality:

```cfg
# Power Loss Recovery Configuration
###############################################
[include power_loss_recovery.cfg]

[force_move]
enable_force_move: true

[save_variables]
# This file is essential for Klipper to save the Z-height and other variables
# needed for the recovery script.
filename: ~/printer_data/config/save_variables.cfg
###############################################
```

### 4\. Restart Klipper

After all files are in place and `printer.cfg` is updated, restart your Klipper firmware for the changes to take effect.

-----

## ⚙️ Slicer Configuration

To ensure the print state is correctly logged, specific G-code macros must be added to your slicer's settings.

| Macro | Location | Purpose |
| :--- | :--- | :--- |
| **`SAVE_LAST_FILE`** | Start G-code | Logs the current G-code filename and starts tracking the print state. **Must be placed at the very beginning** of the start G-code (before heating/purging). |
| **`CLEAR_LAST_FILE`** | End G-code | Clears the saved print state variables, indicating the print finished successfully. |
| **`LOG_Z`** | Layer Change | Saves the current **Z-height** to the `save_variables.cfg` file at the beginning of every new layer. |

### Slicer Setup Example (Cura)

For applications like **Cura**, you can use a post-processing script:

1.  Add the **"Insert at layer Change"** post-processing script.
2.  Set the insertion point to **"After"** (after the layer change command).
3.  Insert the following G-code: `LOG_Z`

-----

## ✅ Ready to Print

Once configured, every print will automatically track its progress. If power is lost, you can use the appropriate Klipper macro (usually `POWER_LOSS_RECOVER`) to generate a recovery file and resume the print.
