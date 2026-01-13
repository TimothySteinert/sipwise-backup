#!/bin/bash

# install.sh - Installation script for sipwise-backup
# This script extracts and installs sipwise-backup Python CLI application to /opt

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
ZIP_FILE="$APP_NAME.zip"

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

# Check if zip file exists in current directory
if [ ! -f "./$ZIP_FILE" ]; then
    echo -e "${RED}Error: $ZIP_FILE not found in current directory${NC}"
    echo "Please ensure $ZIP_FILE is in the same directory as this install script."
    exit 1
fi

echo -e "${GREEN}✓ Found $ZIP_FILE${NC}"
echo ""

# Remove existing installation if present
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Warning: Existing installation found at $INSTALL_DIR${NC}"
    echo "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Extract zip file to installation directory using Python
echo "Extracting $ZIP_FILE to $INSTALL_DIR..."
python3 -c "import zipfile; zipfile.ZipFile('./$ZIP_FILE').extractall('$INSTALL_DIR')"

# Create log directory
echo "Creating log directory..."
mkdir -p "$INSTALL_DIR/log"
chmod 755 "$INSTALL_DIR/log"

# Create state directory
echo "Creating state directory..."
mkdir -p "$INSTALL_DIR/state"
chmod 755 "$INSTALL_DIR/state"

# Set executable permissions
echo "Setting file permissions..."
chmod +x "$INSTALL_DIR/CLI/main.py"
chmod 755 "$INSTALL_DIR/uninstall.sh"

# Create wrapper script
echo "Creating wrapper script..."
cat > "$INSTALL_BIN_DIR/$APP_NAME" <<WRAPPER_EOF
#!/bin/bash
# Wrapper script for sipwise-backup CLI
exec python3 $INSTALL_DIR/CLI/main.py "\$@"
WRAPPER_EOF

chmod +x "$INSTALL_BIN_DIR/$APP_NAME"

# Install systemd service
echo "Installing systemd service..."
cp "$INSTALL_DIR/service/$APP_NAME.service" "$SERVICE_DIR/"

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
echo "Installation location: $INSTALL_DIR"
echo "The $APP_NAME service has been enabled and started."
echo ""
echo "You can now:"
echo "  1. Run the CLI: $APP_NAME"
echo "  2. Check service status: sudo systemctl status $APP_NAME"
echo "  3. View service logs: sudo journalctl -u $APP_NAME -f"
echo ""
echo "To uninstall, run: sudo $INSTALL_DIR/uninstall.sh"
echo ""
