#!/bin/bash

# install.sh - Installation script for sipwise-backup
# This script installs sipwise-backup to /usr/local/bin

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
echo "  sipwise-backup Installation"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root or with sudo${NC}"
    echo "Please run: sudo ./install.sh"
    exit 1
fi

# Check if the source file exists
if [ ! -f "./$APP_NAME" ]; then
    echo -e "${RED}Error: $APP_NAME script not found in current directory${NC}"
    exit 1
fi

echo "Installing $APP_NAME to $INSTALL_DIR..."

# Copy the script to the installation directory
cp "./$APP_NAME" "$INSTALL_DIR/$APP_NAME"

# Make it executable
chmod +x "$INSTALL_DIR/$APP_NAME"

echo -e "${GREEN}✓ Installation completed successfully!${NC}"
echo ""
echo "You can now run '$APP_NAME' from anywhere on your system."
echo ""
echo "To uninstall, run: sudo ./uninstall.sh"
echo ""
