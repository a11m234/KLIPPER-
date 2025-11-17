# This file should be kept in /home/{pc name}/klipper/ with the name plr.py
# after that run sudo chmod +x ./plr.py

import argparse
import os
import sys
import re
import time

# --- Configuration ---
# This path must match where your Klipper G-code files are stored.
SD_PATH = os.path.expanduser("~/printer_data/gcodes")
PLR_GCODE_FILENAME = "plr.gcode"
TEMP_FILE = "/tmp/plrtmpA.txt" # Using a safer, static name for the temp file

def find_first_motion_after_z_log(gcode_lines, z_height):
    """
    Locates the first motion command (G0/G1) line in the original G-code
    that occurs after the last recorded Z-height.
    """
    z_log_line_index = -1
    z_height_str = f"Z{z_height}"

    # 1. Find the last line containing the logged Z-height (where the print stopped)
    for i, line in enumerate(gcode_lines):
        # The BASH script looks for 'Z' followed by the Z-height value.
        # It's usually near the GCODE_MACRO LOG_Z call.
        if z_height_str in line:
            z_log_line_index = i

    if z_log_line_index == -1:
        print(f"Error: Could not find Z log position (Z{z_height}) in original file.", file=sys.stderr)
        return -1, ""

    # 2. Find the SET_KINEMATIC_POSITION Z=... value just before the log
    # This logic is extremely complex in BASH, finding the last Z movement
    # before the Z-log line. We will simplify and assume the Z-height is the target.
    # The BASH script's Z-finding logic is:
    # cat /tmp/plrtmpA.$$ | sed -e '1,/Z'${1}'/ d' | sed -ne '/ Z/,$ p' | grep -m 1 ' Z' | sed -ne 's/.* Z\([^ ]*\)/SET_KINEMATIC_POSITION Z=\1/p'
    # This finds the Z value on the LAST G1/G0 line BEFORE the LOG_Z command.

    kinematic_pos_z = ""
    # Search backwards from the log line
    for i in range(z_log_line_index - 1, -1, -1):
        line = gcode_lines[i]
        # Look for the last G1/G0 Z value.
        match = re.search(r'[Gg][01].*Z([-+]?\d*\.?\d+)', line)
        if match:
            # Found the Z value from the last motion command
            kinematic_pos_z = match.group(1)
            break

    # 3. Find the starting index for the remaining G-code
    start_resume_index = z_log_line_index + 1

    # The BASH logic copies from the start of the file *until* the Z-log line,
    # then finds the first Z movement after that, and finally copies all lines
    # after the Z-log point.

    return start_resume_index, kinematic_pos_z


def generate_resume_file(z_height, gcode_file, print_temp, bed_temp):
    """Main function to generate the plr.gcode resume file."""

    # Define file paths
    original_gcode_path = os.path.join(SD_PATH, gcode_file.strip("'"))
    resume_gcode_path = os.path.join(SD_PATH, PLR_GCODE_FILENAME)

    if not os.path.exists(original_gcode_path):
        print(f"Error: Original G-code file not found at {original_gcode_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Read the original G-code file
    try:
        with open(original_gcode_path, 'r') as f:
            gcode_lines = f.readlines()
    except IOError as e:
        print(f"Error reading {original_gcode_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Find the resume point
    start_resume_index, kinematic_pos_z = find_first_motion_after_z_log(gcode_lines, z_height)

    if start_resume_index == -1:
        # Error was already printed by find_first_motion_after_z_log
        sys.exit(1)

    # 3. Open the output file for writing
    with open(resume_gcode_path, 'w') as out_f:
        # --- BASH Logic Replication: Thumbnail Check ---
        has_thumbnail = any("thumbnail" in line for line in gcode_lines)

        if has_thumbnail:
            # BASH 'else' branch: Copy header/thumbnail block
            print("; --- Resuming Print (Thumbnail Path) ---", file=out_f)

            # Find the header block start and end (from BASH logic: '/thumbnail end/ p')
            header_start_index = 0
            header_end_index = -1

            for i, line in enumerate(gcode_lines):
                if "thumbnail end" in line:
                    header_end_index = i
                    break

            if header_end_index != -1:
                # Copy lines from start to (including) 'thumbnail end'
                for line in gcode_lines[header_start_index:header_end_index + 1]:
                    out_f.write(line)

            # Add extra lines/temp commands from BASH logic
            out_f.write(";\n")


        else:
            # BASH 'if' branch: No thumbnail
            print("; --- Resuming Print (No Thumbnail Path) ---", file=out_f)
        # --- Bed Temperature Restoration (Lines 44-48) ---
        out_f.write("; --- Bed Temperature Restoration (from metadata) ---\n")

        # Logic to find material_bed_temperature in metadata comments (usually near ';End of Gcode')
        metadata_content = "".join(gcode_lines).split(';End of Gcode')[-1]
        # 1. Regex Match for Initial Layer Temp
        # Group 2 will contain the temperature value
        bed_temp_match_inital = re.search(r'(hot_plate_temp_initial_layer)\s*=\s*(\d*\.?\d+)', metadata_content)

        # 2. Regex Match for Standard Bed Temp
        # Group 2 will contain the temperature value
        bed_temp_match = re.search(r'(hot_plate_temp|material_bed_temperature)\s*=\s*(\d*\.?\d+)', metadata_content)

        meta_bed_temp = None # Initialize the temperature variable

        # Logic: Check Z-height to decide which temperature to use
        if z_height < 0.6:
            # We are still on the first layer (or very close), prioritize initial layer temp
            if bed_temp_match_inital:
                # CORRECTED: Use group(2) to get the temperature value (the number)
                meta_bed_temp = bed_temp_match_inital.group(2)
            elif bed_temp_match:
                # Fallback to standard temp if initial temp isn't specified
                # CORRECTED: Use group(2) to get the temperature value (the number)
                meta_bed_temp = bed_temp_match.group(2)
        else:
            # Print is well underway, use the standard printing temperature
            if bed_temp_match:
                # CORRECTED: Use group(2) to get the temperature value (the number)
                meta_bed_temp = bed_temp_match.group(2)
            # If no match, meta_bed_temp remains None

        # 3. Apply Temperature or Fallback to Saved Variable
        if meta_bed_temp is not None:
            # Use the temperature found via metadata logic
            out_f.write(f"M140 S{meta_bed_temp} ; Set Bed Temp (from metadata logic)\n")
        else:
            # Fallback to the saved variable ($4) if metadata parsing failed
            out_f.write(f"M140 S{bed_temp} ; Set Bed Temp (from saved variable)\n")

        out_f.write(f"M104 S{print_temp} ; Set for Extruder Temp\n")

        # --- SET_KINEMATIC_POSITION Z command ---
        # This is the line that tells Klipper the exact physical Z height
        if kinematic_pos_z:
            out_f.write(f"SET_KINEMATIC_POSITION Z={kinematic_pos_z}\n")

        # --- Universal Homing/Setup Commands (Lines 21-25) ---
        out_f.write("; --- Universal Homing and Setup ---\n")
        out_f.write('BED_MESH_PROFILE LOAD="default"\n ')
        out_f.write("G91 ; Set relative positioning\n")
        out_f.write("G1 Z15 ; Move Z up 5mm\n")
        out_f.write("G90 ; Set absolute positioning\n")
        out_f.write("G28 X Y ; Home X and Y axes\n")
        out_f.write("M83 ; Set extruder to relative mode\n")

        # --- Extruder Temperature Restoration (Lines 29-30) ---
        out_f.write("; --- wait for bed & Extruder Temperature ---\n")
        if meta_bed_temp is not None:
         out_f.write(f"M190 S{meta_bed_temp} ; wait bed Temp\n")
        else:
         out_f.write(f"M190 S{bed_temp} ; wait bed Temp\n")
        out_f.write(f"M109 S{print_temp} ; wait for Extruder Temp\n")



        # --- Fan Speed (M106) Restoration (Line 38) ---
        out_f.write("; --- Fan Speed Restoration ---\n")
        # Find the first M106 before the Z-log point
        fan_command = ""
        for line in gcode_lines[:start_resume_index]:
            if line.strip().startswith("M106"):
                fan_command = line.strip()
                break # BASH logic uses 'head -1' which is the first match
        if fan_command:
            out_f.write(f"{fan_command} ; Restore Fan Speed\n")

        # --- Z-Axis Restore (Lines 62-64) ---
        out_f.write("; --- Z-Axis Restore ---\n")
        out_f.write("G91 ; Relative positioning\n")
        out_f.write("G1 Z-15 ; Move Z back down 5mm\n")
        out_f.write("G90 ; Absolute positioning\n")

        # --- Copy Remaining G-code (Line 67) ---
        out_f.write("; --- Remaining Print G-code ---\n")

        # The BASH logic is very complex here, finding the correct line to start copying.
        # We start copying from the index determined earlier.
        for line in gcode_lines[start_resume_index:]:
            # We want to exclude the LOG_Z and previous commands themselves
            if not line.strip().startswith(('G28', 'G92', 'M106', 'M104', 'M140', 'M190', 'M109')):
                out_f.write(line)

    # 4. Final step: sleep (from BASH)
    time.sleep(5)
    print(f"Success: Resume file '{PLR_GCODE_FILENAME}' created at {resume_gcode_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate a Klipper Power Loss Resume G-code file.")

    # Arguments correspond to positional parameters $1, $2, $3, $4
    parser.add_argument("z_height", type=float, help="The Z-height where the print was logged (power_resume_z).")
    parser.add_argument("gcode_file", type=str, help="The name of the original G-code file (last_file).")
    parser.add_argument("print_temp", type=float, help="The saved extruder target temperature (print_temp).")
    bed_temp=60.0
    try:
        args = parser.parse_args()
        generate_resume_file(args.z_height, args.gcode_file, args.print_temp, bed_temp)
    except SystemExit as e:
        # Avoid exiting if argparse fails to allow the Klipper system to continue.
        # Errors are already printed to stderr by argparse.
        if e.code != 0:
            sys.exit(1)
