# sipwise-backup

A CLI application for Debian servers to manage Sipwise backups.

## Version

1.0.0

## Requirements

- Debian-based Linux server
- Bash shell
- Root/sudo privileges for installation

## Installation

1. Navigate to the sipwise-backup directory:
   ```bash
   cd /path/to/sipwise-backup
   ```

2. Run the installation script with sudo:
   ```bash
   sudo ./install.sh
   ```

The application will be installed to `/usr/local/bin/` and will be available system-wide.

## Usage

After installation, you can run the application from anywhere:

```bash
sipwise-backup
```

### Available Commands

Once the CLI is running, you can use the following commands:

- `exit` - Exit the application
- `help` - Show available commands

## Uninstallation

To remove sipwise-backup from your system:

1. Navigate to the sipwise-backup directory:
   ```bash
   cd /path/to/sipwise-backup
   ```

2. Run the uninstallation script with sudo:
   ```bash
   sudo ./uninstall.sh
   ```

## Development

This is the initial version with basic CLI functionality. Additional features will be developed in future releases.

## File Structure

```
sipwise-backup/
├── sipwise-backup    # Main CLI application
├── install.sh        # Installation script
├── uninstall.sh      # Uninstallation script
└── README.md         # This file
```

## License

Copyright © 2026

## Support

For issues and questions, please contact your system administrator.