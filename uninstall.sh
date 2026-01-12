#!/bin/bash

# uninstall.sh - Uninstallation script for sipwise-backup
# This script removes sipwise-backup from /usr/local/bin

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="/usr/local/bin"
APP_NAME="sipwise-backup"

echo "======================================"
echo "  sipwise-backup Uninstallation"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root or with sudo${NC}"
    echo "Please run: sudo ./uninstall.sh"
    exit 1
fi

# Check if the application is installed
if [ ! -f "$INSTALL_DIR/$APP_NAME" ]; then
    echo -e "${YELLOW}Warning: $APP_NAME is not installed in $INSTALL_DIR${NC}"
    echo "Nothing to uninstall."
    exit 0
fi

echo "Removing $APP_NAME from $INSTALL_DIR..."

# Remove the script
rm -f "$INSTALL_DIR/$APP_NAME"

echo -e "${GREEN}✓ Uninstallation completed successfully!${NC}"
echo ""
echo "$APP_NAME has been removed from your system."
echo ""
