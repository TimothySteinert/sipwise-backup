#!/bin/bash

# uninstall.sh - Uninstallation script for sipwise-backup
# This script removes sipwise-backup Python CLI application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directories
INSTALL_DIR="/opt/sipwise-backup"
INSTALL_BIN_DIR="/usr/bin"
SERVICE_DIR="/etc/systemd/system"
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

# Stop and disable the service if it's running
if systemctl is-active --quiet "$APP_NAME.service"; then
    echo "Stopping $APP_NAME service..."
    systemctl stop "$APP_NAME.service"
fi

if systemctl is-enabled --quiet "$APP_NAME.service" 2>/dev/null; then
    echo "Disabling $APP_NAME service..."
    systemctl disable "$APP_NAME.service"
fi

# Remove systemd service file
if [ -f "$SERVICE_DIR/$APP_NAME.service" ]; then
    echo "Removing systemd service..."
    rm -f "$SERVICE_DIR/$APP_NAME.service"
    systemctl daemon-reload
fi

# Remove wrapper script
if [ -f "$INSTALL_BIN_DIR/$APP_NAME" ]; then
    echo "Removing wrapper script..."
    rm -f "$INSTALL_BIN_DIR/$APP_NAME"
fi

# Remove application directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing application files..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo -e "${GREEN}✓ Uninstallation completed successfully!${NC}"
echo ""
echo "$APP_NAME has been removed from your system."
echo ""
