#!/usr/bin/env python3
"""
restore.py - Restore Module for sipwise-backup
Handles restore operations including:
- Backup selection and download
- NGCP config restoration
- MySQL database restoration
- SQL encryption key preservation
- Integration with storage module
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple
import sys

# Import our storage module
from storage import StorageManager


class RestoreManager:
    """Manages restore operations for sipwise-backup"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the RestoreManager

        Args:
            config_path: Path to the configuration file
        """
        self.storage = StorageManager(config_path)
        self.config = self.storage.config
        self.tmp_dir = Path(self.storage.tmp_dir)
        self.ngcp_config_dir = Path("/etc/ngcp-config")
        self.source_constants = self.ngcp_config_dir / "constants.yml"
        self.tempkey_path = self.tmp_dir / "tempkey"
        self.target_key_line = 293
        self.exclude_files = {"network.yml"}

    def _run_command(self, cmd: str, ignore_errors: bool = False) -> int:
        """
        Run a shell command

        Args:
            cmd: Command to execute
            ignore_errors: If True, don't raise exception on failure

        Returns:
            Return code from command
        """
        print(f">>> {cmd}")
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0 and not ignore_errors:
            raise RuntimeError(f"Command failed ({result.returncode}): {cmd}")
        return result.returncode

    def extract_key(self) -> str:
        """
        Extract SQL encryption key from constants.yml line 293

        Returns:
            The extracted key

        Raises:
            Exception: If key cannot be extracted
        """
        try:
            with self.source_constants.open("r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise Exception(f"Cannot open {self.source_constants}")

        if self.target_key_line > len(lines):
            raise Exception(f"constants.yml only has {len(lines)} lines!")

        line = lines[self.target_key_line - 1].strip()

        if not line.startswith("key:"):
            raise Exception(
                f"Line {self.target_key_line} does not contain a key entry: {line}"
            )

        key = line.split("key:", 1)[1].strip()
        return key

    def save_key_to_temp(self, key: str):
        """
        Save the SQL encryption key to temporary file

        Args:
            key: The key to save
        """
        self.tempkey_path.parent.mkdir(parents=True, exist_ok=True)
        with self.tempkey_path.open("w") as f:
            f.write(key + "\n")
        print(f"[OK] Key saved to {self.tempkey_path}")

    def restore_key_into_constants(self):
        """
        Restore the original SQL encryption key back into constants.yml

        Raises:
            Exception: If key cannot be restored
        """
        try:
            with self.tempkey_path.open("r") as f:
                key = f.read().strip()
        except FileNotFoundError:
            raise Exception("Tempkey file missing!")

        try:
            with self.source_constants.open("r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise Exception("Restored constants.yml missing!")

        old_line = lines[self.target_key_line - 1].rstrip()

        if not old_line.strip().startswith("key:"):
            raise Exception(
                f"Line {self.target_key_line} in restored constants.yml is not a key: {old_line}"
            )

        indent = old_line.split("key:")[0]
        new_line = f"{indent}key: {key}\n"

        lines[self.target_key_line - 1] = new_line

        with self.source_constants.open("w") as f:
            f.writelines(lines)

        print("[OK] Key successfully restored into constants.yml")
        print(f"[INFO] Key: {key}")

    def restore_ngcp_config(self, restore_dir: Path):
        """
        Restore NGCP configuration from backup

        Args:
            restore_dir: Directory containing extracted backup

        Raises:
            Exception: If restoration fails
        """
        extracted_ngcp = restore_dir / "ngcp-config"
        if not extracted_ngcp.exists():
            raise Exception("Backup missing ngcp-config/")

        print("[INFO] Restoring ngcp-config...")

        for item in extracted_ngcp.iterdir():
            target = self.ngcp_config_dir / item.name

            if item.name in self.exclude_files:
                print(f"[SKIP] Preserving existing {item.name}")
                continue

            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy(item, target)

        print("[OK] ngcp-config restored")

    def restore_mysql_database(self, restore_dir: Path):
        """
        Restore MySQL database from backup

        Args:
            restore_dir: Directory containing extracted backup

        Raises:
            Exception: If restoration fails
        """
        sql_file = restore_dir / "database.sql"
        if not sql_file.exists():
            raise Exception("database.sql missing from backup!")

        # Get MySQL credentials from config
        mysql_config = self.config.get('mysql', {})
        mysql_user = mysql_config.get('user', 'root')
        mysql_password = mysql_config.get('password', '')

        print("[INFO] Restoring MySQL database...")

        # Build mysql command with credentials
        cmd = f"mysql -u {mysql_user}"
        if mysql_password:
            cmd += f" -p{mysql_password}"
        cmd += f" < '{sql_file}'"

        self._run_command(cmd)
        print("[OK] MySQL database restored")

    def apply_configuration(self):
        """
        Apply NGCP configuration using ngcpcfg

        Raises:
            Exception: If configuration apply fails
        """
        print("[INFO] Applying configuration...")
        self._run_command("ngcpcfg apply 'restored the system from backup'")
        print("[OK] Configuration applied")

    def run_restore(
        self,
        backup_filename: str,
        preserve_sql_key: bool = True,
        restore_sip_register: bool = False
    ) -> bool:
        """
        Execute a full restore operation

        Args:
            backup_filename: Name of the backup file to restore
            preserve_sql_key: If True, preserve the current SQL encryption key
            restore_sip_register: If True, restore SIP register data (makes environment live)

        Returns:
            True if successful, False otherwise
        """
        print("=" * 80)
        print("Starting Restore Process")
        print("=" * 80)
        print()

        original_key = None
        restore_dir = None

        try:
            # Step 1: Extract and save current SQL key if preserving
            if preserve_sql_key:
                print("[+] Extracting current SQL encryption key...")
                original_key = self.extract_key()
                self.save_key_to_temp(original_key)
                print()

            # Step 2: Download backup to tmp
            print(f"[+] Downloading backup: {backup_filename}")
            zip_path = self.storage.download_backup_to_tmp(backup_filename)

            if not zip_path:
                raise Exception(f"Failed to download backup: {backup_filename}")

            print(f"    Downloaded to: {zip_path}")
            print()

            # Step 3: Extract backup
            print("[+] Extracting backup...")
            restore_dir = self.tmp_dir / f"RESTORE-{Path(zip_path).stem}"

            if restore_dir.exists():
                shutil.rmtree(restore_dir)

            restore_dir.mkdir(parents=True)

            extract_path = self.storage.unzip_backup(zip_path, str(restore_dir))
            print(f"    Extracted to: {extract_path}")
            print()

            # Step 4: Restore NGCP config
            print("[+] Restoring NGCP configuration...")
            # If extracted to subdirectory, adjust path
            actual_restore_dir = Path(extract_path)
            if not (actual_restore_dir / "ngcp-config").exists():
                # Files might be directly in restore_dir
                actual_restore_dir = restore_dir

            self.restore_ngcp_config(actual_restore_dir)
            print()

            # Step 5: Restore SQL key if preserving
            if preserve_sql_key and original_key:
                print("[+] Restoring original SQL encryption key...")
                self.restore_key_into_constants()
                print()
            else:
                print("[!] Using SQL encryption key from backup")
                print()

            # Step 6: Restore MySQL database
            print("[+] Restoring MySQL database...")
            self.restore_mysql_database(actual_restore_dir)
            print()

            # Step 7: Apply configuration
            print("[+] Applying NGCP configuration...")
            self.apply_configuration()
            print()

            # Step 8: Handle SIP register restoration
            if restore_sip_register:
                print("[+] Restoring SIP register data...")
                print("[!] WARNING: This makes the environment LIVE!")
                # Placeholder for SIP register restoration
                print("[TODO] SIP register restoration not yet implemented")
                print()

            # Step 9: Cleanup
            print("[+] Cleaning up temporary files...")
            self.storage.clean_tmp()
            print()

            print("=" * 80)
            print("RESTORE COMPLETED SUCCESSFULLY")
            print("=" * 80)
            print()

            return True

        except Exception as e:
            print()
            print("=" * 80)
            print(f"RESTORE FAILED: {e}")
            print("=" * 80)
            print()

            # Cleanup on failure
            try:
                self.storage.clean_tmp()
            except:
                pass

            return False

    def get_restore_status(self) -> Dict:
        """
        Get information about available backups for restore

        Returns:
            Dictionary with restore status information
        """
        backups = self.storage.list_backups()

        return {
            'available_backups': len(backups),
            'latest_backup': self.storage.get_last_backup_time(),
            'storage_type': self.storage.get_storage_type(),
            'storage_directory': self.storage.get_storage_directory()
        }


# Convenience functions for external use
def run_restore(
    backup_filename: str,
    preserve_sql_key: bool = True,
    restore_sip_register: bool = False
) -> bool:
    """
    Run a restore operation

    Args:
        backup_filename: Name of the backup file to restore
        preserve_sql_key: If True, preserve the current SQL encryption key
        restore_sip_register: If True, restore SIP register data

    Returns:
        True if successful, False otherwise
    """
    manager = RestoreManager()
    return manager.run_restore(backup_filename, preserve_sql_key, restore_sip_register)


def get_restore_manager() -> RestoreManager:
    """
    Get a RestoreManager instance

    Returns:
        RestoreManager instance
    """
    return RestoreManager()


if __name__ == "__main__":
    # Test the restore manager
    print("Testing restore module...")
    manager = RestoreManager()
    status = manager.get_restore_status()
    print(f"Available backups: {status['available_backups']}")
    print(f"Storage type: {status['storage_type']}")
