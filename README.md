# sipwise-backup

A Python-based CLI application for Debian servers to manage Sipwise backups.

## Version

1.0.0

## Requirements

- Debian-based Linux server
- Python 3.x
- PyYAML (for configuration management)
- MySQL/MariaDB (for database backups)
- NGCP (Sipwise Next Generation Communications Platform)
- systemd (for service management)
- Root/sudo privileges for installation and restore operations

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
- `(5) Exit` - Exit the application

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
├── restore.py               # Restore operations module
├── logger.py                # Centralized logging module
├── config.yml               # Configuration file
├── requirements.txt         # Python dependencies
├── uninstall.sh             # Uninstallation script
└── README.md                # Documentation

/opt/sipwise-backup/backups/ # Default backup storage location
/opt/sipwise-backup/tmp/     # Temporary working directory
/opt/sipwise-backup/log/     # Daily log files (DDMMYYYY.log)

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
├── restore.py               # Restore operations module
├── logger.py                # Centralized logging module
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
  - Interactive restore options (SQL key preservation, firewall disable)

- **storage.py**: Storage management module (centralized file operations)
  - Configuration reading from config.yml
  - Backup naming: `server_name-instance_type-HH-MM_DD-MM-YYYY.zip`
  - Zip/unzip operations
  - Local storage operations (save, list, delete)
  - Remote FTP storage support with secure connections
  - Backup metadata parsing and listing
  - Temporary directory management
  - Backup download to temporary directory for restore

- **backup.py**: Backup operations module
  - NGCP config backup (`/etc/ngcp-config`)
  - Full MySQL database dumps (all databases, routines, triggers, events)
  - Integration with storage module for zip and save operations
  - Automatic cleanup of temporary files
  - Backup status reporting

- **restore.py**: Restore operations module
  - Complete backup restoration workflow
  - SQL encryption key preservation for cross-server restores
  - Firewall configuration management (optional disable)
  - Two-stage NGCP configuration application (stage1 before DB, stage2 after DB)
  - MySQL database restoration with credentials from config
  - Network configuration preservation (excludes network.yml)
  - Interactive reboot prompt after successful restore
  - Comprehensive error handling and logging
  - Automatic cleanup on success or failure

- **logger.py**: Centralized logging module
  - Daily log files in DDMMYYYY.log format
  - Multiple log levels (DEBUG, INFO, WARNING, ERROR, SUCCESS)
  - Console output with file logging
  - Command execution logging with stdout/stderr capture
  - Log retention policy matching backup retention
  - Automatic log file cleanup based on retention days

- **config.yml**: YAML configuration file
  - Instance type (master/dr) and server name
  - Storage settings (local/remote FTP)
  - MySQL credentials for backup and restore
  - Backup settings (automatic, retention, cleanup)
  - Reboot scheduling
  - Sipwise-specific configuration (line numbers for config.yml and constants.yml)

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

### Restore Workflow

**User Interaction:**
1. User selects "Restore from Backup" from CLI menu
2. System displays available backups with metadata (server name, instance type, timestamp)
3. User selects backup and confirms restore options:
   - **Preserve SQL encryption key** (Recommended for DR restores) - Default: Yes
   - **Disable firewall** (Recommended for DR servers) - Default: No

**Restore Process Steps:**
1. **Step 1**: Extract current SQL encryption key from `/etc/ngcp-config/constants.yml` line 293 (if preserving)
2. **Step 2**: Download backup from storage (local/FTP) to `/opt/sipwise-backup/tmp`
3. **Step 3**: Extract backup archive
4. **Step 4**: Restore NGCP configuration to `/etc/ngcp-config` (excludes `network.yml`)
5. **Step 5**: Restore saved SQL encryption key to `/etc/ngcp-config/constants.yml` (if preserve option selected)
6. **Step 6**: Disable firewall in `/etc/ngcp-config/config.yml` line 1578 (if option selected)
7. **Step 7**: Run `ngcpcfg apply "restore stage1"` (before database restore)
8. **Step 8**: Restore MySQL database from backup SQL dump
9. **Step 9**: Run `ngcpcfg apply "restore stage2"` (after database restore)
10. **Step 10**: Cleanup temporary files
11. Success message and interactive reboot prompt (5-second countdown, cancellable with Ctrl+C)
12. All operations logged to `/opt/sipwise-backup/log/DDMMYYYY.log`

#### Why Two-Stage Configuration Apply?

The restore process uses a two-stage `ngcpcfg apply` approach:
- **Stage 1** (before database restore): Applies configuration changes to prepare the system
- **Stage 2** (after database restore): Applies final configuration with restored database

This ensures proper synchronization between configuration and database state.

#### SQL Encryption Key Preservation

**⚠️ CRITICAL for DR restores:** When restoring from a master server backup to a DR server, you MUST enable "Preserve SQL encryption key" to prevent database startup failures.

**How it works:**
1. **Before restore**: Original key from `/etc/ngcp-config/constants.yml` (line 293) is saved to temporary file
2. **During restore**: Backup files (including constants.yml with master's key) are copied to `/etc/ngcp-config`
3. **After config restore**: Original DR server's key is restored back to `/etc/ngcp-config/constants.yml`
4. **Result**: Database starts successfully with the DR server's original encryption key

**Why this matters:**
- Each server has its own MySQL encryption key in `constants.yml`
- Master and DR servers have different encryption keys
- If you restore the master's encryption key to the DR server, MySQL will fail to start
- Key preservation ensures the DR server keeps its own encryption key while getting all other configuration

#### Firewall Management

When restoring to a different server (DR scenario), it's recommended to disable the firewall:
- Prevents connectivity issues after restore
- Modifies `/etc/ngcp-config/config.yml` at line 1578 (configurable)
- Changes `enable: yes` to `enable: no` under the firewall section
- Firewall can be manually re-enabled after verifying the restore

#### Network Configuration Preservation

The restore process ALWAYS preserves the existing `network.yml` file:
- Backup's `network.yml` is excluded from restore
- Current server's network configuration remains unchanged
- Prevents loss of network connectivity during restore

#### Comprehensive Logging

All restore operations are logged to `/opt/sipwise-backup/log/DDMMYYYY.log`:
- Each step of the restore process
- All command executions with stdout/stderr output
- Errors and warnings with full context
- Success and completion messages
- User decisions (reboot choice, etc.)

### Storage Module Integration
All file operations route through `storage.py` for:
- Centralized configuration management
- Consistent backup naming
- Unified local and remote storage handling
- Automatic temporary file cleanup

### Logging System

The application uses a centralized logging system via `logger.py`:

**Log Files:**
- Location: `/opt/sipwise-backup/log/`
- Format: `DDMMYYYY.log` (e.g., `14012026.log`)
- New log file created daily
- All operations logged with timestamps

**Log Levels:**
- **DEBUG**: Detailed diagnostic information (command output, file operations)
- **INFO**: General informational messages (operation start/completion)
- **WARNING**: Warning messages (using backup keys, skipped operations)
- **ERROR**: Error messages (command failures, exceptions)
- **SUCCESS**: Success messages (operation completed successfully)

**What Gets Logged:**
- All backup operations (start, progress, completion)
- All restore operations (each step with details)
- Command executions with full stdout/stderr output
- Configuration changes
- Errors and exceptions with full context
- User choices and decisions
- FTP operations (connect, download, upload)
- File operations (copy, move, delete)

**Log Retention:**
- Logs follow the same retention policy as backups
- Default: 30 days (configurable in `config.yml`)
- Automatic cleanup of old log files
- Retention policy applied during backup operations

**Console vs File Logging:**
- Console: INFO level and above (clean, user-friendly output)
- File: DEBUG level and above (comprehensive detailed logging)
- All console output is also logged to file
- Command stderr output logged to both console and file

## License

Copyright © 2026

## Support

For issues and questions, please contact your system administrator.