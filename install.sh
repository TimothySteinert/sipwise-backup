#!/bin/bash

# install.sh - Installation script for sipwise-backup
# This script installs sipwise-backup Python CLI application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directories
INSTALL_BIN_DIR="/usr/local/bin"
INSTALL_LIB_DIR="/usr/local/share/sipwise-backup"
SERVICE_DIR="/etc/systemd/system"
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

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 is not installed${NC}"
    echo "Please install Python3 first: sudo apt-get install python3"
    exit 1
fi

echo -e "${GREEN}✓ Python3 found: $(python3 --version)${NC}"

# Check if required directories exist
if [ ! -d "./CLI" ]; then
    echo -e "${RED}Error: CLI directory not found${NC}"
    exit 1
fi

if [ ! -f "./CLI/main.py" ]; then
    echo -e "${RED}Error: CLI/main.py not found${NC}"
    exit 1
fi

if [ ! -d "./service" ]; then
    echo -e "${RED}Error: service directory not found${NC}"
    exit 1
fi

if [ ! -f "./service/$APP_NAME.service" ]; then
    echo -e "${RED}Error: service/$APP_NAME.service not found${NC}"
    exit 1
fi

# Create installation directory
echo "Creating installation directories..."
mkdir -p "$INSTALL_LIB_DIR"

# Copy CLI files
echo "Installing CLI application..."
cp -r ./CLI "$INSTALL_LIB_DIR/"
chmod +x "$INSTALL_LIB_DIR/CLI/main.py"

# Create wrapper script
echo "Creating wrapper script..."
cat > "$INSTALL_BIN_DIR/$APP_NAME" <<'WRAPPER_EOF'
#!/bin/bash
# Wrapper script for sipwise-backup CLI
exec python3 /usr/local/share/sipwise-backup/CLI/main.py "$@"
WRAPPER_EOF

chmod +x "$INSTALL_BIN_DIR/$APP_NAME"

# Install systemd service
echo "Installing systemd service..."
cp "./service/$APP_NAME.service" "$SERVICE_DIR/"

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service
echo "Enabling $APP_NAME service..."
systemctl enable "$APP_NAME.service"

# Start the service
echo "Starting $APP_NAME service..."
systemctl start "$APP_NAME.service"

echo ""
echo -e "${GREEN}✓ Installation completed successfully!${NC}"
echo ""
echo "The $APP_NAME service has been enabled and started."
echo ""
echo "You can now:"
echo "  1. Run the CLI: $APP_NAME"
echo "  2. Check service status: sudo systemctl status $APP_NAME"
echo "  3. View service logs: sudo journalctl -u $APP_NAME -f"
echo ""
echo "To uninstall, run: sudo ./uninstall.sh"
echo ""
