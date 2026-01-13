# sipwise-backup

A Python-based CLI application for Debian servers to manage Sipwise backups.

## Version

1.0.0

## Requirements

- Debian-based Linux server
- Python 3.x
- PyYAML (for configuration management)
- MySQL/MariaDB (for database backups)
- systemd (for service management)
- Root/sudo privileges for installation

## Installation

1. Download the distribution package which contains:
   - `sipwise-backup.zip` - The application package
   - `install.sh` - The installation script

2. Place both files in the same directory and navigate to it:
   ```bash
   cd /path/to/download/directory
   ```

3. Run the installation script with sudo:
   ```bash
   sudo ./install.sh
   ```

The installation script will:
- Check for Python 3
- Extract the application to `/opt/sipwise-backup/`
- Create a wrapper script in `/usr/bin/sipwise-backup`
- Register and enable the systemd service
- Automatically start the service

## Usage

### Running the CLI

After installation, you can run the application from anywhere:

```bash
sipwise-backup
```

### Available Menu Options

Once the CLI is running, you can use the following menu options:

- `(1) Config Menu` - Edit configuration and restart service
- `(2) Run Manual Backup` - Execute a manual backup operation
- `(3) List Backups` - View all available backups
- `(4) Restore from Backup` - Restore from a selected backup
- `(5) Make DR Instance Live` - Activate disaster recovery instance
- `(6) Exit` - Exit the application

### Running as a Service

You can also run sipwise-backup as a systemd service:

```bash
# Enable the service to start on boot
sudo systemctl enable sipwise-backup

# Start the service
sudo systemctl start sipwise-backup

# Check service status
sudo systemctl status sipwise-backup

# Stop the service
sudo systemctl stop sipwise-backup

# Disable the service
sudo systemctl disable sipwise-backup
```

## Uninstallation

To remove sipwise-backup from your system, run the uninstallation script:

```bash
sudo /opt/sipwise-backup/uninstall.sh
```

The uninstallation script will:
- Stop and disable the systemd service
- Remove the systemd service file
- Remove the wrapper script from `/usr/bin`
- Remove all application files from `/opt/sipwise-backup`

## Development

This is the initial version with basic CLI functionality. Additional features will be developed in future releases.

## File Structure

### Distribution Package
```
distribution/
├── sipwise-backup.zip       # Application package
└── install.sh               # Installation script (outside zip)
```

### Installed System
```
/opt/sipwise-backup/
├── CLI/
│   └── main.py              # Main Python CLI application
├── service/
│   └── sipwise-backup.service   # systemd service file
├── storage.py               # Storage management module
├── backup.py                # Backup operations module
├── config.yml               # Configuration file
├── requirements.txt         # Python dependencies
├── uninstall.sh             # Uninstallation script
└── README.md                # Documentation

/opt/sipwise-backup/backups/ # Default backup storage location
/opt/sipwise-backup/tmp/     # Temporary working directory

/usr/bin/
└── sipwise-backup           # Wrapper script

/etc/systemd/system/
└── sipwise-backup.service   # Registered systemd service
```

### Repository Structure
```
sipwise-backup/
├── CLI/
│   └── main.py              # Main Python CLI application
├── service/
│   └── sipwise-backup.service   # systemd service file
├── storage.py               # Storage management module
├── backup.py                # Backup operations module
├── config.yml               # Configuration file
├── requirements.txt         # Python dependencies
├── install.sh               # Installation script (not included in zip)
├── uninstall.sh             # Uninstallation script
├── .gitignore               # Git ignore file
└── README.md                # This file
```

## Architecture

### Core Modules

- **CLI/main.py**: Interactive menu interface with screen clearing and navigation
  - Config menu for editing configuration and restarting service
  - Manual backup execution
  - Backup listing and management
  - Restore operations with confirmation prompts
  - DR instance activation

- **storage.py**: Storage management module (centralized file operations)
  - Configuration reading from config.yml
  - Backup naming: `server_name-instance_type-HH-MM_DD-MM-YYYY.zip`
  - Zip/unzip operations
  - Local storage operations (save, list, delete)
  - Remote FTP storage support (structure in place)
  - Backup metadata parsing and listing
  - Temporary directory management

- **backup.py**: Backup operations module
  - NGCP config backup (`/etc/ngcp-config`)
  - Full MySQL database dumps (all databases, routines, triggers, events)
  - Integration with storage module for zip and save operations
  - Automatic cleanup of temporary files
  - Backup status reporting

- **config.yml**: YAML configuration file
  - Instance type (master/dr) and server name
  - Storage settings (local/remote)
  - MySQL credentials
  - Backup settings (automatic, retention, cleanup)
  - Sync settings for DR instances
  - Reboot scheduling

### Installation & Service

- **install.sh**: Installation script
  - Extracts zip package using Python's zipfile module
  - Installs to `/opt/sipwise-backup/`
  - Creates wrapper script in `/usr/bin/sipwise-backup`
  - Registers and enables systemd service
  - Sets proper file permissions

- **uninstall.sh**: Uninstallation script
  - Stops and disables systemd service
  - Removes all installed files and directories
  - Cleans up wrapper script and service file

- **service/sipwise-backup.service**: systemd service configuration
  - Enables running as background service
  - Auto-restart on failure
  - Journal logging integration

## Module Workflow

### Backup Workflow
1. User selects "Run Manual Backup" or automatic backup triggers
2. `backup.py` creates timestamped directory in `/opt/sipwise-backup/tmp`
3. `backup.py` copies `/etc/ngcp-config` to backup directory
4. `backup.py` dumps MySQL database to backup directory
5. `backup.py` calls `storage.py` to zip the directory
6. `storage.py` generates backup name with timestamp
7. `storage.py` saves backup to configured storage (local/remote)
8. `storage.py` cleans up temporary files

### Restore Workflow (Planned)
1. User selects "Restore from Backup"
2. `storage.py` lists available backups
3. User selects backup and confirms options
4. `storage.py` downloads/copies backup to tmp
5. `storage.py` extracts backup files
6. Restore module processes NGCP config and database
7. `storage.py` cleans up temporary files

### Storage Module Integration
All file operations route through `storage.py` for:
- Centralized configuration management
- Consistent backup naming
- Unified local and remote storage handling
- Automatic temporary file cleanup

## License

Copyright © 2026

## Support

For issues and questions, please contact your system administrator.