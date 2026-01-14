#!/bin/bash

# install.sh - Installation script for sipwise-backup
# This script extracts and installs sipwise-backup Python CLI application to /opt

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directories
INSTALL_DIR="/opt/sipwise-backup"
INSTALL_BIN_DIR="/usr/bin"
SERVICE_DIR="/etc/systemd/system"
APP_NAME="sipwise-backup"
ZIP_FILE="$APP_NAME.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Check for required Python modules
echo "Checking Python dependencies..."

# Test if smtplib is available (should be built-in)
if ! python3 -c "import smtplib" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Python smtplib not available. Email notifications may not work.${NC}"
fi

# Test if email.mime is available (should be built-in)
if ! python3 -c "from email.mime.text import MIMEText" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Python email module not available. Email notifications may not work.${NC}"
fi

echo -e "${GREEN}✓ Python dependencies checked${NC}"

# Check if zip file exists in current directory
if [ ! -f "$SCRIPT_DIR/$ZIP_FILE" ]; then
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
python3 -c "import zipfile; zipfile.ZipFile('$SCRIPT_DIR/$ZIP_FILE').extractall('$INSTALL_DIR')"

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
echo -e "${GREEN}✓ Base installation completed successfully!${NC}"
echo ""

# Configuration Phase
echo "======================================"
echo "  Configuration Setup"
echo "======================================"
echo ""

# Ask if Master or DR server
while true; do
    echo -e "${BLUE}Is this a Master or DR Server?${NC}"
    echo "1) Master"
    echo "2) DR"
    read -p "Enter choice [1-2]: " server_type_choice

    case $server_type_choice in
        1)
            SERVER_TYPE="master"
            break
            ;;
        2)
            SERVER_TYPE="dr"
            break
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter 1 or 2.${NC}"
            ;;
    esac
done

echo ""

# Variables for later use
USE_BACKUP_CONFIG=false
USE_TEMPLATE=false
CONFIG_FILE="$INSTALL_DIR/config.yml"

if [ "$SERVER_TYPE" = "master" ]; then
    # Master server configuration
    echo -e "${BLUE}Master Server Configuration${NC}"
    echo ""
    read -p "Enter server name: " SERVER_NAME

    # Update config.yml with server name and instance type using sed
    echo "Updating configuration..."

    # Update instance_type
    sed -i "s/^instance_type:.*/instance_type: master/" "$CONFIG_FILE"

    # Update server_name
    sed -i "s/^server_name:.*/server_name: $SERVER_NAME/" "$CONFIG_FILE"

    echo -e "${GREEN}✓ Configuration updated${NC}"
    echo ""

else
    # DR server configuration
    echo -e "${BLUE}DR Server Configuration${NC}"
    echo ""

    # Check if backup config.yml exists
    if [ -f "$SCRIPT_DIR/config.yml" ]; then
        read -p "Backup config.yml found. Do you want to install from backup config.yml? (y/n): " use_backup
        if [[ "$use_backup" =~ ^[Yy]$ ]]; then
            echo "Copying backup config.yml..."
            cp "$SCRIPT_DIR/config.yml" "$INSTALL_DIR/config.yml"
            USE_BACKUP_CONFIG=true
            echo -e "${GREEN}✓ Backup config.yml installed${NC}"
        fi
        echo ""
    fi

    # Check if setup.template exists
    if [ -f "$SCRIPT_DIR/setup.template" ]; then
        read -p "Setup template found. Do you want to install from template? (y/n): " use_template
        if [[ "$use_template" =~ ^[Yy]$ ]]; then
            USE_TEMPLATE=true
            echo -e "${GREEN}✓ Template will be processed after configuration${NC}"
        fi
        echo ""
    fi

    # Ask for server name
    read -p "Enter server name: " SERVER_NAME
    echo ""

    # Update config.yml with server name and instance type using sed
    echo "Updating server configuration..."

    # Update instance_type
    sed -i "s/^instance_type:.*/instance_type: dr/" "$CONFIG_FILE"

    # Update server_name
    sed -i "s/^server_name:.*/server_name: $SERVER_NAME/" "$CONFIG_FILE"

    echo -e "${GREEN}✓ Server configuration updated${NC}"
    echo ""

    # Process template if selected
    if [ "$USE_TEMPLATE" = true ]; then
        echo "======================================"
        echo "  Processing Setup Template"
        echo "======================================"
        echo ""

        TEMPLATE_FILE="$SCRIPT_DIR/setup.template"

        # Parse template and extract values using Python with correct argument passing
        echo "Parsing template file..."

        # Extract passwords from template
        CDREXPORT_PASSWORD=$(python3 -c "
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
system_users = template.get('system_users', {})
cdrexport = system_users.get('cdrexport', {})
password = cdrexport.get('password', '')
print(password)
")

        ROOT_PASSWORD=$(python3 -c "
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
system_users = template.get('system_users', {})
root = system_users.get('root', {})
password = root.get('password', '')
print(password)
")

        MYSQL_ROOT_PASSWORD=$(python3 -c "
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
mysql = template.get('mysql', {})
password = mysql.get('root_password', '')
print(password)
")

        # Set system user passwords
        if [ -n "$CDREXPORT_PASSWORD" ]; then
            echo "Setting password for cdrexport user..."
            if id "cdrexport" &>/dev/null; then
                echo "cdrexport:$CDREXPORT_PASSWORD" | chpasswd
                echo -e "${GREEN}✓ cdrexport password set${NC}"
            else
                echo -e "${YELLOW}Warning: cdrexport user does not exist, skipping${NC}"
            fi
        fi

        if [ -n "$ROOT_PASSWORD" ]; then
            echo "Setting password for root user..."
            echo "root:$ROOT_PASSWORD" | chpasswd
            echo -e "${GREEN}✓ root password set${NC}"
        fi

        echo ""

        # Set MySQL root password
        if [ -n "$MYSQL_ROOT_PASSWORD" ]; then
            echo "Setting MySQL root password..."
            if command -v mysql &> /dev/null; then
                mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';" 2>/dev/null || true
                echo -e "${GREEN}✓ MySQL root password set${NC}"
            else
                echo -e "${YELLOW}Warning: MySQL not found, skipping MySQL password setup${NC}"
            fi
        fi

        echo ""

        # Create MySQL users from template
        echo "Creating MySQL users from template..."
        python3 << 'PYEOF'
import yaml
import subprocess

template_file = '$TEMPLATE_FILE'
mysql_root_password = '$MYSQL_ROOT_PASSWORD'

with open(template_file, 'r') as f:
    template = yaml.safe_load(f)

mysql_config = template.get('mysql', {})
users = mysql_config.get('users', [])

for user in users:
    username = user.get('username')
    password = user.get('password')
    privileges = user.get('privileges', 'ALL PRIVILEGES')
    host = user.get('host', 'localhost')

    if username and password:
        print(f"Creating MySQL user: {username}@{host}")

        # Create user
        create_cmd = f"CREATE USER IF NOT EXISTS '{username}'@'{host}' IDENTIFIED BY '{password}';"
        subprocess.run(['mysql', '-e', create_cmd], stderr=subprocess.DEVNULL, check=False)

        # Grant privileges
        grant_cmd = f"GRANT {privileges} ON *.* TO '{username}'@'{host}';"
        subprocess.run(['mysql', '-e', grant_cmd], stderr=subprocess.DEVNULL, check=False)

        # Flush privileges
        flush_cmd = "FLUSH PRIVILEGES;"
        subprocess.run(['mysql', '-e', flush_cmd], stderr=subprocess.DEVNULL, check=False)

        print(f"✓ User {username}@{host} created with {privileges}")
PYEOF

        echo ""

        # Update config.yml with MySQL credentials from template using sed
        echo "Updating config.yml with MySQL credentials from template..."

        # Extract first MySQL user from template
        MYSQL_USER=$(python3 -c "
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
mysql_config = template.get('mysql', {})
users = mysql_config.get('users', [])
if users:
    print(users[0].get('username', ''))
")

        MYSQL_PASSWORD=$(python3 -c "
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
mysql_config = template.get('mysql', {})
users = mysql_config.get('users', [])
if users:
    print(users[0].get('password', ''))
")

        if [ -n "$MYSQL_USER" ] && [ -n "$MYSQL_PASSWORD" ]; then
            # Use sed to update MySQL user and password while preserving formatting
            # This uses a more complex sed command to find and replace in the mysql section
            sed -i "/^mysql:/,/^[^ ]/ s/^  user:.*/  user: $MYSQL_USER/" "$CONFIG_FILE"
            sed -i "/^mysql:/,/^[^ ]/ s/^  password:.*/  password: $MYSQL_PASSWORD/" "$CONFIG_FILE"

            echo -e "${GREEN}✓ Config updated with MySQL user: $MYSQL_USER${NC}"
        fi

        echo -e "${GREEN}✓ Template processing completed${NC}"
        echo ""
    fi
fi

echo ""
echo "======================================"
echo -e "${GREEN}✓ Installation completed successfully!${NC}"
echo "======================================"
echo ""
echo "Installation location: $INSTALL_DIR"
echo "Server type: $SERVER_TYPE"
echo "Server name: $SERVER_NAME"
echo ""
echo -e "${YELLOW}Please review the configuration file and adjust required settings:${NC}"
echo "  Configuration file: $INSTALL_DIR/config.yml"
echo ""
echo "You can now:"
echo "  1. Run the CLI: $APP_NAME"
echo "  2. Check service status: sudo systemctl status $APP_NAME"
echo "  3. View service logs: sudo journalctl -u $APP_NAME -f"
echo ""
echo "To uninstall, run: sudo $INSTALL_DIR/uninstall.sh"
echo ""
