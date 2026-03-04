# TellStick Repair Issue Management

## Problem
The TellStick add-on has been removed from the official Home Assistant repository, causing persistent repair warnings. However, the add-on remains functional and you want to continue using it.

## Solution
Use the `dismiss_tellstick_repairs.sh` script to automatically dismiss these warnings.

## Quick Usage

```bash
cd /config/scripts
./dismiss_tellstick_repairs.sh
```

## What It Does

The script:
1. Connects to the Home Assistant Supervisor via SSH
2. Queries the resolution center for all issues
3. Identifies TellStick-related warnings:
   - `detached_addon_removed` - Add-on removed from repository
   - `deprecated_addon` - Add-on is deprecated
4. Automatically dismisses them by their UUID

## When to Run

Run this script when you see TellStick repair warnings in Home Assistant. This typically happens after:
- Home Assistant Supervisor updates
- System reboots
- Add-on restarts

## Manual Alternative

If you prefer to dismiss issues manually:

```bash
# 1. List all issues and find TellStick UUIDs
ssh root@192.168.1.75 "ha resolution info"

# 2. Dismiss each UUID
ssh root@192.168.1.75 "ha resolution issue dismiss <UUID>"
```

## Requirements

- SSH access to Home Assistant host (root@192.168.1.75)
- `jq` installed (for JSON parsing)

## Notes

- The script is safe to run multiple times
- If no TellStick issues exist, it will report success and exit
- UUIDs change each time the issue appears, so you cannot hardcode them
- The TellStick add-on will continue to function normally despite being deprecated
