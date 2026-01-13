#!/usr/bin/env python3
"""
backup.py - Backup Module for sipwise-backup
Handles backup operations including:
- NGCP config backup
- MySQL database dumps
- Integration with storage module
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

# Import our storage module
from storage import StorageManager
from logger import get_logger
from emailer import get_emailer


class BackupManager:
    """Manages backup operations for sipwise-backup"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the BackupManager

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.storage = StorageManager(config_path)
        self.config = self.storage.config
        self.tmp_dir = Path(self.storage.tmp_dir)
        self.ngcp_config_path = Path("/etc/ngcp-config")
        self.logger = get_logger(config_path)

    def _run_command(self, cmd: str) -> str:
        """
        Run a shell command and return output

        Args:
            cmd: Command to execute

        Returns:
            Command output as string

        Raises:
            RuntimeError: If command fails
        """
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}\n{proc.stderr}")
        return proc.stdout

    def _get_mysql_credentials(self) -> Dict[str, str]:
        """
        Get MySQL credentials from config

        Returns:
            Dictionary with mysql_user and mysql_password
        """
        mysql_config = self.config.get('mysql', {})

        return {
            'user': mysql_config.get('user', 'root'),
            'password': mysql_config.get('password', '')
        }

    def _create_backup_directory(self) -> Path:
        """
        Create a timestamped backup directory in tmp

        Returns:
            Path to the created backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.tmp_dir / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def _backup_ngcp_config(self, backup_dir: Path) -> bool:
        """
        Copy NGCP config directory to backup

        Args:
            backup_dir: Directory to backup to

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.ngcp_config_path.exists():
                self.logger.warn(f"NGCP config not found at {self.ngcp_config_path}")
                print(f"Warning: NGCP config not found at {self.ngcp_config_path}")
                return False

            self.logger.debug(f"Backing up NGCP config from {self.ngcp_config_path}")
            print(f"[+] Copying {self.ngcp_config_path}/")
            dest = backup_dir / "ngcp-config"
            shutil.copytree(self.ngcp_config_path, dest)
            self.logger.success("NGCP config backup completed")
            return True
        except Exception as e:
            self.logger.error(f"NGCP config backup failed: {e}")
            print(f"Error backing up NGCP config: {e}")
            return False

    def _dump_mysql_database(self, backup_dir: Path) -> bool:
        """
        Dump full MySQL database to backup directory

        Args:
            backup_dir: Directory to save dump to

        Returns:
            True if successful, False otherwise
        """
        try:
            credentials = self._get_mysql_credentials()
            sql_file = backup_dir / "database.sql"

            self.logger.debug("Starting MySQL database dump")
            print("[+] Dumping full MySQL database...")
            print("    (all databases, routines, triggers, events)")

            # Build mysqldump command
            cmd = (
                f"mysqldump --all-databases --routines --triggers --events "
                f"-u {credentials['user']}"
            )

            # Add password if provided
            if credentials['password']:
                cmd += f" -p{credentials['password']}"

            # Redirect output to file
            cmd += f" > {sql_file}"

            self._run_command(cmd)
            self.logger.success("MySQL database dump completed")
            print(f"    Saved to: {sql_file}")
            return True
        except Exception as e:
            self.logger.error(f"MySQL dump failed: {e}")
            print(f"Error dumping MySQL database: {e}")
            return False

    def run_backup(self, backup_type: str = "auto") -> Optional[str]:
        """
        Execute a full backup operation

        This performs the following steps:
        1. Create temporary backup directory
        2. Copy NGCP config
        3. Dump MySQL database
        4. Zip backup directory
        5. Save to configured storage
        6. Clean up temporary files

        Args:
            backup_type: Type of backup ("auto" or "manual")

        Returns:
            Backup filename if successful, None otherwise
        """
        self.logger.info(f"Starting {backup_type} backup")
        print("=" * 60)
        print("Starting Backup Process")
        print("=" * 60)
        
        emailer = get_emailer(self.config_path)
        current_stage = "initialization"

        try:
            # Step 1: Create backup directory
            current_stage = "initialization"
            backup_dir = self._create_backup_directory()
            print(f"[+] Working directory: {backup_dir}")

            # Step 2: Backup NGCP config
            current_stage = "NGCP config backup"
            ngcp_success = self._backup_ngcp_config(backup_dir)
            if not ngcp_success:
                print("Warning: NGCP config backup failed, continuing...")

            # Step 3: Dump MySQL database
            current_stage = "MySQL database dump"
            mysql_success = self._dump_mysql_database(backup_dir)
            if not mysql_success:
                raise Exception("MySQL dump failed - aborting backup")

            # Step 4: Generate backup name and zip
            current_stage = "creating backup archive"
            backup_filename = self.storage.generate_backup_name(backup_type=backup_type)
            print(f"[+] Creating backup archive: {backup_filename}")

            zip_path = self.storage.zip_directory(
                str(backup_dir),
                backup_filename
            )
            print(f"    Backup size: {os.path.getsize(zip_path) / (1024*1024):.2f} MB")

            # Step 5: Save to storage
            current_stage = "saving to storage"
            print(f"[+] Saving backup to {self.storage.get_storage_type()} storage...")
            save_success = self.storage.save_backup(zip_path)

            if not save_success:
                raise Exception("Failed to save backup to storage")

            print(f"    Saved to: {self.storage.get_storage_directory()}")

            # Step 6: Clean up
            print("[+] Cleaning up temporary files...")
            self.storage.clean_tmp()

            print("=" * 60)
            print(f"[OK] Backup completed successfully: {backup_filename}")
            print("=" * 60)

            return backup_filename

        except Exception as e:
            print("=" * 60)
            print(f"[ERROR] Backup failed: {e}")
            print("=" * 60)

            # Clean up on failure
            try:
                self.storage.clean_tmp()
            except:
                pass
            
            # Send failure email only for automatic backups
            if backup_type == "auto":
                self.logger.error(f"Backup failed at stage '{current_stage}': {e}")
                emailer.send_backup_failure(
                    error_message=str(e),
                    stage=current_stage
                )

            return None

    def get_backup_status(self) -> Dict:
        """
        Get current backup status information

        Returns:
            Dictionary with backup status information
        """
        last_backup = self.storage.get_last_backup_time()
        backups = self.storage.list_backups()

        return {
            'last_backup_time': last_backup,
            'total_backups': len(backups),
            'storage_type': self.storage.get_storage_type(),
            'storage_directory': self.storage.get_storage_directory()
        }


# Convenience function for external use
def run_backup() -> Optional[str]:
    """
    Run a backup operation

    Returns:
        Backup filename if successful, None otherwise
    """
    manager = BackupManager()
    return manager.run_backup()


def get_backup_manager() -> BackupManager:
    """
    Get a BackupManager instance

    Returns:
        BackupManager instance
    """
    return BackupManager()


if __name__ == "__main__":
    # Test the backup manager
    print("Testing backup module...")
    result = run_backup()

    if result:
        print(f"\nBackup successful: {result}")
    else:
        print("\nBackup failed!")
