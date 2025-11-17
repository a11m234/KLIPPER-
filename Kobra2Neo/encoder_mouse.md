That code is fully compatible with a Raspberry Pi Zero 2 W, as it uses standard Python libraries and the GPIO header.

The main issue isn't the code itself, but **permissions** and **dependencies**. For this script to work, you need to:

1.  Install the required libraries.
2.  Give your user account permission to create virtual input devices.

I've taken your code and improved it slightly to be more robust, more intuitive (Clockwise = Right/Down), and to handle fast encoder spins correctly. I also added `print` statements so you can see what's happening.

### Improved Script (`mouse_encoder.py`)

This version fixes the mouse direction (so clockwise moves right/down) and correctly uses the `steps` value to allow for "acceleration" if you spin the knob fast.

```python
#!/usr/bin/env python3
from gpiozero import RotaryEncoder, Button
from evdev import UInput, ecodes as e
import time
import signal
import sys

# === Configurable Variables ===
pin_a = 27      # Encoder A Pin (BCM)
pin_b = 17      # Encoder B Pin (BCM)
pin_button = 22 # Encoder Switch (SW) Pin (BCM)
hold_time = 0.5 # Time to hold for a left click
movement_amount = 10 # Multiplier for mouse movements (higher = faster)
# Note: Most encoder modules need an internal pull-up resistor.
# If your button doesn't work, try pull_up=False
button_pull_up = True 

# Mode: 0 for X-axis, 1 for Y-axis
mode = 0

# === Initialize UInput device ===
try:
    capabilities = {
        e.EV_KEY: [e.BTN_LEFT], # Only need left click
        e.EV_REL: [e.REL_X, e.REL_Y],
    }
    # Create a device named "EncoderMouse"
    ui = UInput(capabilities, name="EncoderMouse")
    print("Virtual mouse device created.")
except Exception as err:
    print(f"--- ERROR ---")
    print(f"Could not create UInput device: {err}")
    print("Please run the setup steps to grant permissions for /dev/uinput")
    print("You may need to reboot after setup.")
    sys.exit(1)


def button_hold():
    global mode
    # This toggles the mode *back* to what it was before the
    # initial "when_pressed" event, effectively "canceling" the mode
    # switch and performing a left click instead.
    mode = 1 - mode 
    print(f"Button Held: Left Click! (Mode is {mode})")
    
    # Send a left click
    ui.write(e.EV_KEY, e.BTN_LEFT, 1) # Press
    ui.syn()
    time.sleep(0.05) # Click duration
    ui.write(e.EV_KEY, e.BTN_LEFT, 0) # Release
    ui.syn()

def button_pressed():
    global mode
    mode = 1 - mode  # Toggle between 0 (X-axis) and 1 (Y-axis)
    axis = "Y-axis" if mode == 1 else "X-axis"
    print(f"Button Pressed: Mode toggled to {mode} ({axis})")

def move_mouse():
    global encoder, movement_amount
    
    # Read and reset steps in one go.
    # 'steps' will be positive for CW, negative for CCW.
    steps = encoder.steps
    encoder.steps = 0 

    # Calculate total movement. This handles fast spins correctly.
    total_move = steps * movement_amount

    if total_move == 0:
        return # No movement

    if mode == 0: # X-axis
        # CW (steps > 0) -> move right (positive)
        # CCW (steps < 0) -> move left (negative)
        ui.write(e.EV_REL, e.REL_X, total_move)
        print(f"Move X: {total_move}")
    elif mode == 1: # Y-axis
        # CW (steps > 0) -> move down (positive)
        # CCW (steps < 0) -> move up (negative)
        ui.write(e.EV_REL, e.REL_Y, total_move)
        print(f"Move Y: {total_move}")
    
    # Synchronize to apply the movement
    ui.syn()

# === Main script ===
try:
    # Set up GPIO devices
    # max_steps=0 means it can rotate infinitely
    encoder = RotaryEncoder(pin_a, pin_b, max_steps=0) 
    encoder.when_rotated = move_mouse

    # pull_up=True is usually required for common encoder modules
    button = Button(pin_button, pull_up=button_pull_up)
    button.hold_time = hold_time
    button.when_held = button_hold
    button.when_pressed = button_pressed

    print("Encoder and button initialized. Script is running.")
    print(f"Initial mode: 0 (X-axis)")
    print("Press Ctrl+C to exit.")

    # Keep the script running
    signal.pause()

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    # Clean up the virtual device on exit
    ui.close()
    print("Virtual mouse device closed.")

```

-----

### ⚙️ How to Set Up and Run This on Your Pi

Follow these steps in your Raspberry Pi Zero 2 W's terminal (e.g., via SSH).

**Step 1: Install Dependencies**
First, install the `gpiozero` and `evdev` libraries for Python 3.

```bash
sudo apt update
sudo apt install python3-gpiozero python3-evdev
```

**Step 2: Set `uinput` Permissions**
By default, only the `root` user can create virtual devices. You need to create a new user group (e.g., `uinput`) and give it permission.

```bash
# 1. Create a new group called 'uinput' (it might already exist)
sudo groupadd uinput || echo "Group 'uinput' already exists"

# 2. Add your current user (e.g., 'pi') to this new group
#    ($USER is a variable for your username)
sudo usermod -aG uinput $USER

# 3. Create a 'udev' rule to give this group write access
echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
```

**Step 3: Reboot**
This is the easiest way to make sure the new group and udev rules are applied.

```bash
sudo reboot
```

**Step 4: Run the Script**
After the Pi reboots, log back in.

1.  Save the improved code above as a file named `mouse_encoder.py`.
2.  Make it executable (optional, but good practice):
    `chmod +x mouse_encoder.py`
3.  Run it:
    `python3 mouse_encoder.py`

You should see the "Virtual mouse device created" message, and turning the knob should now move your mouse cursor\!

**Step 5: (Optional) Run on Boot**
If you want this to run automatically when your Pi (e.g., your Klipper host) starts, you can use `crontab`:

1.  Open the crontab editor:
    `crontab -e`

2.  Add this line to the bottom of the file, making sure to use the **full path** to your script:

    ```
    @reboot /usr/bin/python3 /home/pi/mouse_encoder.py &
    ```

    *(Replace `/home/pi/` with the correct path if you saved it elsewhere.)*

3.  Save and exit. It will now run on every reboot.
