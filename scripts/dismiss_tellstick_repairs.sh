#!/bin/bash
#
# Dismiss TellStick Repair Issues
# 
# This script automatically dismisses repair warnings for the deprecated TellStick add-on.
# The TellStick add-on was removed from the official repository but remains functional.
#
# Usage:
#   ./dismiss_tellstick_repairs.sh
#
# The script will:
# 1. Query the resolution center for all current issues
# 2. Find TellStick-related issues (detached_addon_removed, deprecated_addon)
# 3. Automatically dismiss them by UUID
#
# Note: This script requires SSH access to the Home Assistant host (root@192.168.1.75)

echo "Checking for TellStick repair issues..."

# Get all resolution issues in JSON format
ISSUES=$(ssh root@192.168.1.75 "ha resolution info --raw-json" 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to Home Assistant host"
    exit 1
fi

# Extract TellStick-related issue UUIDs
TELLSTICK_UUIDS=$(echo "$ISSUES" | jq -r '.data.issues[] | select(.reference == "core_tellstick") | .uuid' 2>/dev/null)

if [ -z "$TELLSTICK_UUIDS" ]; then
    echo "✓ No TellStick repair issues found"
    exit 0
fi

# Dismiss each issue
COUNT=0
while IFS= read -r UUID; do
    if [ -n "$UUID" ]; then
        echo "Dismissing issue: $UUID"
        ssh root@192.168.1.75 "ha resolution issue dismiss $UUID" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            ((COUNT++))
            echo "  ✓ Dismissed"
        else
            echo "  ✗ Failed to dismiss"
        fi
    fi
done <<< "$TELLSTICK_UUIDS"

echo ""
echo "✓ Dismissed $COUNT TellStick repair issue(s)"
