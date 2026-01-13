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

# Show uninstall options
echo "Choose uninstall option:"
echo ""
echo "  1) Keep backups and logs (recommended)"
echo "     - Removes application files, service, and wrapper script"
echo "     - Keeps: $INSTALL_DIR/backups/"
echo "     - Keeps: $INSTALL_DIR/log/"
echo ""
echo "  2) Remove everything (complete uninstall)"
echo "     - Removes ALL files including backups and logs"
echo "     - WARNING: This will delete all your backup files!"
echo ""
read -p "Enter choice [1/2]: " choice

case $choice in
    1)
        KEEP_DATA=true
        echo ""
        echo -e "${YELLOW}Keeping backups and logs...${NC}"
        ;;
    2)
        KEEP_DATA=false
        echo ""
        echo -e "${RED}WARNING: This will delete ALL backup files and logs!${NC}"
        read -p "Are you sure? Type 'yes' to confirm: " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Uninstall cancelled."
            exit 0
        fi
        echo ""
        echo "Removing everything..."
        ;;
    *)
        echo -e "${RED}Invalid choice. Aborting.${NC}"
        exit 1
        ;;
esac

# Stop and disable the service if it's running
if systemctl is-active --quiet "$APP_NAME.service" 2>/dev/null; then
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

# Remove application files
if [ -d "$INSTALL_DIR" ]; then
    if [ "$KEEP_DATA" = true ]; then
        echo "Removing application files (keeping backups and logs)..."
        
        # Remove everything except backups, log, and state directories
        find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 \
            ! -name "backups" \
            ! -name "log" \
            ! -name "state" \
            -exec rm -rf {} +
        
        echo ""
        echo -e "${GREEN}✓ Application removed. Data preserved at:${NC}"
        echo "   - Backups: $INSTALL_DIR/backups/"
        echo "   - Logs: $INSTALL_DIR/log/"
        echo "   - State: $INSTALL_DIR/state/"
    else
        echo "Removing ALL application files..."
        rm -rf "$INSTALL_DIR"
    fi
fi

echo ""
echo -e "${GREEN}✓ Uninstallation completed successfully!${NC}"
echo ""

if [ "$KEEP_DATA" = true ]; then
    echo "$APP_NAME has been removed from your system."
    echo "Your backups and logs have been preserved."
    echo ""
    echo "To completely remove all data later, run:"
    echo "  sudo rm -rf $INSTALL_DIR"
else
    echo "$APP_NAME has been completely removed from your system."
fi
echo ""
