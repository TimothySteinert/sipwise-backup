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
import re
import shutil
import subprocess
import socket
from pathlib import Path
from typing import Optional, Dict, Tuple
import sys

# Import our storage module
from storage import StorageManager
from logger import get_logger


class RestoreManager:
    """Manages restore operations for sipwise-backup"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the RestoreManager

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.storage = StorageManager(config_path)
        self.config = self.storage.config
        self.tmp_dir = Path(self.storage.tmp_dir)
        self.ngcp_config_dir = Path("/etc/ngcp-config")
        self.source_constants = self.ngcp_config_dir / "constants.yml"
        self.tempkey_path = self.tmp_dir / "tempkey"
        self.logger = get_logger(config_path)
        
        # Get Sipwise config line numbers from config (with defaults for backward compatibility)
        sipwise_config = self.config.get('sipwise', {})
        constants_config = sipwise_config.get('constants_yml', {})
        config_yml_config = sipwise_config.get('config_yml', {})
        
        self.target_key_line = constants_config.get('sql_encryption_key_line', 293)
        self.firewall_enable_line = config_yml_config.get('firewall_enable_line', 1568)
        
        # Path to ngcp config.yml (different from our app's config.yml)
        self.ngcp_config_yml = self.ngcp_config_dir / "config.yml"
        
        self.exclude_files = {"network.yml"}
        
        # Compile regex pattern for firewall validation (done once at init)
        # Pattern matches: optional whitespace, 'enable:', optional whitespace, yes/no
        self.firewall_enable_pattern = re.compile(r'^\s*enable:\s*(yes|no)\s*$')

    def _run_command(self, cmd: str, ignore_errors: bool = False, log_description: str = None) -> int:
        """
        Run a shell command

        Args:
            cmd: Command to execute
            ignore_errors: If True, don't raise exception on failure
            log_description: Optional description for logging

        Returns:
            Return code from command
        """
        log_msg = log_description or cmd
        self.logger.debug(f"Running command: {cmd}")
        print(f">>> {cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        # Log stdout if present
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line:
                    self.logger.debug(f"  stdout: {line}")

        # Log stderr if present
        if result.stderr:
            for line in result.stderr.strip().split('\n'):
                if line:
                    self.logger.error(f"  stderr: {line}")
                    print(f"[ERROR] {line}")

        if result.returncode != 0:
            error_msg = f"Command failed ({result.returncode}): {cmd}"
            self.logger.error(error_msg)
            if not ignore_errors:
                raise RuntimeError(error_msg)
        else:
            self.logger.debug(f"Command completed successfully: {log_msg}")

        return result.returncode

    def get_current_server_info(self) -> Dict[str, str]:
        """
        Get current server name and instance type from config
        
        Returns:
            Dictionary with 'server_name' and 'instance_type'
        """
        return {
            'server_name': self.config.get('server_name', ''),
            'instance_type': self.config.get('instance_type', '')
        }

    def is_same_server(self, backup_server_name: str, backup_instance_type: str) -> bool:
        """
        Check if the backup is from the same server
        
        Args:
            backup_server_name: Server name from backup filename
            backup_instance_type: Instance type from backup filename
            
        Returns:
            True if both server name and instance type match
        """
        current = self.get_current_server_info()
        return (
            current['server_name'] == backup_server_name and
            current['instance_type'] == backup_instance_type
        )

    def get_system_ipv4(self) -> str:
        """
        Get the primary IPv4 address of the system
        
        Returns:
            IPv4 address string or 'unknown' if cannot determine
        """
        return self.get_system_ipv4_static()
    
    @staticmethod
    def get_system_ipv4_static() -> str:
        """
        Static method to get the primary IPv4 address of the system
        Can be called without creating a RestoreManager instance.
        
        Returns:
            IPv4 address string or 'unknown' if cannot determine
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                return ip
            finally:
                s.close()
        except Exception:
            return "unknown"

    def disable_firewall_in_config(self):
        """
        Disable firewall in the /etc/ngcp-config/config.yml

        Modifies the firewall enable setting from 'yes' to 'no'
        This should be called AFTER restore_ngcp_config() has copied files to /etc/ngcp-config

        Raises:
            Exception: If modification fails
        """
        config_file = self.ngcp_config_yml

        if not config_file.exists():
            raise Exception(f"config.yml missing from {self.ngcp_config_dir}!")

        self.logger.warn("Disabling firewall in configuration")
        print(f"[INFO] Disabling firewall in config.yml (line {self.firewall_enable_line})...")

        with config_file.open("r") as f:
            lines = f.readlines()

        if len(lines) < self.firewall_enable_line:
            error_msg = f"config.yml has fewer than {self.firewall_enable_line} lines (has {len(lines)} lines)"
            self.logger.error(error_msg)
            raise Exception(error_msg)

        old_line = lines[self.firewall_enable_line - 1].rstrip()

        # Verify this is the firewall enable line using pre-compiled regex
        if not self.firewall_enable_pattern.match(old_line):
            error_msg = f"Line {self.firewall_enable_line} does not appear to be firewall enable setting: {old_line}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # Get the indentation and replace value
        # Use split with limit=1 to handle edge cases like colons in values or comments
        indent = old_line.split("enable:", 1)[0]
        new_line = f"{indent}enable: no\n"

        lines[self.firewall_enable_line - 1] = new_line

        with config_file.open("w") as f:
            f.writelines(lines)

        self.logger.success(f"Firewall disabled in {config_file}")
        print(f"[OK] Firewall disabled (changed from '{old_line.strip()}' to 'enable: no')")

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

        # Extract indentation and rebuild line with preserved formatting
        # Use split with limit=1 to handle edge cases like colons in key values
        indent = old_line.split("key:", 1)[0]
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

        self.logger.debug("Restoring NGCP configuration")
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

        self.logger.debug("Restoring MySQL database")
        print("[INFO] Restoring MySQL database...")

        # Build mysql command with credentials
        cmd = f"mysql -u {mysql_user}"
        if mysql_password:
            cmd += f" -p{mysql_password}"
        cmd += f" < '{sql_file}'"

        self._run_command(cmd)
        self.logger.success("MySQL database restored successfully")
        print("[OK] MySQL database restored")

    def apply_configuration(self, stage: str = ""):
        """
        Apply NGCP configuration using ngcpcfg

        Args:
            stage: Optional stage identifier (e.g., "stage1", "stage2")

        Raises:
            Exception: If configuration apply fails
        """
        stage_msg = f" ({stage})" if stage else ""
        commit_msg = f"restored the system from backup{' - ' + stage if stage else ''}"

        print(f"[INFO] Applying configuration{stage_msg}...")
        self.logger.info(f"Running ngcpcfg apply: {commit_msg}")

        self._run_command(
            f"ngcpcfg apply '{commit_msg}'",
            log_description=f"ngcpcfg apply {stage if stage else 'final'}"
        )

        self.logger.success(f"Configuration applied successfully{stage_msg}")
        print(f"[OK] Configuration applied{stage_msg}")

    def run_restore(
        self,
        backup_filename: str,
        preserve_sql_key: bool = True,
        disable_firewall: bool = False
    ) -> bool:
        """
        Execute a full restore operation

        Args:
            backup_filename: Name of the backup file to restore
            preserve_sql_key: If True, preserve the current SQL encryption key
            disable_firewall: If True, disable firewall in the restored config

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Starting restore from backup: {backup_filename}")
        self.logger.info(f"Options: preserve_sql_key={preserve_sql_key}, disable_firewall={disable_firewall}")
        print("=" * 80)
        print("Starting Restore Process")
        print("=" * 80)
        print()

        original_key = None
        restore_dir = None

        try:
            # Step 1: Extract and save current SQL key if preserving
            if preserve_sql_key:
                print("[+] Step 1: Extracting current SQL encryption key from /etc/ngcp-config/constants.yml...")
                self.logger.info("Extracting current SQL encryption key for preservation")
                original_key = self.extract_key()
                self.save_key_to_temp(original_key)
                self.logger.debug(f"Saved encryption key to temp file: {self.tempkey_path}")
                print()

            # Step 2: Download backup to tmp
            print(f"[+] Step 2: Downloading backup: {backup_filename}")
            self.logger.info(f"Downloading backup file: {backup_filename}")
            zip_path = self.storage.download_backup_to_tmp(backup_filename)

            if not zip_path:
                error_msg = f"Failed to download backup: {backup_filename}"
                self.logger.error(error_msg)
                raise Exception(error_msg)

            self.logger.success(f"Downloaded backup to: {zip_path}")
            print(f"    Downloaded to: {zip_path}")
            print()

            # Step 3: Extract backup
            print("[+] Step 3: Extracting backup archive...")
            self.logger.info("Extracting backup archive")
            restore_dir = self.tmp_dir / f"RESTORE-{Path(zip_path).stem}"

            if restore_dir.exists():
                shutil.rmtree(restore_dir)

            restore_dir.mkdir(parents=True)

            extract_path = self.storage.unzip_backup(zip_path, str(restore_dir))
            self.logger.success(f"Extracted backup to: {extract_path}")
            print(f"    Extracted to: {extract_path}")
            print()

            # Step 4: Restore NGCP config (excluding network.yml)
            print("[+] Step 4: Restoring NGCP configuration to /etc/ngcp-config...")
            self.logger.info("Restoring NGCP configuration (excluding network.yml)")

            # If extracted to subdirectory, adjust path
            actual_restore_dir = Path(extract_path)
            if not (actual_restore_dir / "ngcp-config").exists():
                # Files might be directly in restore_dir
                actual_restore_dir = restore_dir

            self.restore_ngcp_config(actual_restore_dir)
            self.logger.success("NGCP configuration restored")
            print()

            # Step 5: Restore SQL key if preserving (modifies /etc/ngcp-config/constants.yml)
            if preserve_sql_key and original_key:
                print("[+] Step 5: Restoring original SQL encryption key to /etc/ngcp-config/constants.yml...")
                self.logger.info("Restoring original SQL encryption key")
                self.restore_key_into_constants()
                self.logger.success("SQL encryption key restored")
                print()
            else:
                print("[!] Step 5: Using SQL encryption key from backup (NOT recommended for DR restore)")
                self.logger.warn("Using SQL encryption key from backup - this may cause database startup failures on different servers")
                print()

            # Step 6: Disable firewall if requested (modifies /etc/ngcp-config/config.yml)
            if disable_firewall:
                print("[+] Step 6: Disabling firewall in /etc/ngcp-config/config.yml...")
                self.logger.info("Disabling firewall in configuration")
                self.disable_firewall_in_config()
                print()
            else:
                print("[!] Step 6: Firewall settings unchanged (using backup settings)")
                self.logger.info("Firewall settings not modified - using backup settings")
                print()

            # Step 7: Apply configuration - STAGE 1
            print("[+] Step 7: Applying NGCP configuration (Stage 1)...")
            self.logger.info("Applying NGCP configuration - Stage 1 (before database restore)")
            self.apply_configuration("stage1")
            print()

            # Step 8: Restore MySQL database
            print("[+] Step 8: Restoring MySQL database...")
            self.logger.info("Restoring MySQL database")
            self.restore_mysql_database(actual_restore_dir)
            print()

            # Step 9: Apply configuration - STAGE 2
            print("[+] Step 9: Applying NGCP configuration (Stage 2)...")
            self.logger.info("Applying NGCP configuration - Stage 2 (after database restore)")
            self.apply_configuration("stage2")
            print()

            # Step 10: Cleanup
            print("[+] Cleaning up temporary files...")
            self.logger.info("Cleaning up temporary files")
            self.storage.clean_tmp()
            self.logger.success("Temporary files cleaned up")
            print()

            print("=" * 80)
            print("✓ RESTORE COMPLETED SUCCESSFULLY")
            print("=" * 80)
            self.logger.success("Restore completed successfully")

            # Prompt for reboot
            print()
            print("[!] IMPORTANT: A system reboot is recommended to complete the restore.")
            self.logger.warn("System reboot recommended to complete restore")
            response = input("Would you like to reboot now? [y/N]: ").strip().lower()

            if response in ['y', 'yes']:
                print("[!] Rebooting system in 5 seconds...")
                self.logger.info("User requested immediate reboot")
                print("    Press Ctrl+C to cancel...")
                try:
                    import time
                    time.sleep(5)
                    self.logger.info("Initiating system reboot")
                    self._run_command("reboot", ignore_errors=True)
                except KeyboardInterrupt:
                    print()
                    print("[!] Reboot cancelled by user")
                    self.logger.info("Reboot cancelled by user")
            else:
                print("[!] Reboot skipped. Please reboot manually when ready.")
                self.logger.info("User chose to skip immediate reboot")

            print()
            return True

        except Exception as e:
            error_msg = str(e)
            print()
            print("=" * 80)
            print(f"✗ RESTORE FAILED: {error_msg}")
            print("=" * 80)
            print()

            # Log the full error
            self.logger.error(f"Restore failed: {error_msg}")

            # Cleanup on failure
            try:
                self.logger.info("Attempting cleanup after failure")
                self.storage.clean_tmp()
            except Exception as cleanup_error:
                self.logger.error(f"Cleanup failed: {cleanup_error}")

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
    disable_firewall: bool = False
) -> bool:
    """
    Run a restore operation

    Args:
        backup_filename: Name of the backup file to restore
        preserve_sql_key: If True, preserve the current SQL encryption key
        disable_firewall: If True, disable firewall in the restored config

    Returns:
        True if successful, False otherwise
    """
    manager = RestoreManager()
    return manager.run_restore(backup_filename, preserve_sql_key, disable_firewall)


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
