#!/usr/bin/env python3
"""
storage.py - Storage Module for sipwise-backup
Handles all storage and filesystem operations including:
- Reading/writing backup files
- Zipping/unzipping operations
- Local and FTP storage
- Backup naming and listing
"""

import os
import yaml
import zipfile
import shutil
from datetime import datetime
from ftplib import FTP, error_perm
from typing import List, Dict, Optional, Tuple

from logger import get_logger


class StorageManager:
    """Manages all storage operations for sipwise-backup"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the StorageManager

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.tmp_dir = "/opt/sipwise-backup/tmp"
        self._ensure_tmp_dir()
        self.logger = get_logger(config_path)

    def _load_config(self) -> Dict:
        """
        Load configuration from config.yml

        Returns:
            Dictionary containing configuration data
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            raise Exception(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing configuration file: {e}")

    def _ensure_tmp_dir(self):
        """Ensure the temporary directory exists"""
        os.makedirs(self.tmp_dir, exist_ok=True)

    def _ftp_connect(self) -> FTP:
        """
        Connect to FTP server using config credentials
        
        Returns:
            FTP connection object
            
        Raises:
            Exception: If connection fails
        """
        remote_config = self.config.get('storage', {}).get('remote', {})
        hostname = remote_config.get('hostname')
        port = remote_config.get('port', 21)
        username = remote_config.get('username', '')
        password = remote_config.get('password', '')
        directory = remote_config.get('directory', '/backups/sipwise')
        
        if not hostname:
            raise Exception("FTP hostname not configured in config.yml")
        
        self.logger.debug(f"Connecting to FTP server: {hostname}:{port}")
        ftp = FTP()
        ftp.connect(hostname, port)
        ftp.login(username, password)
        
        # Create directory if it doesn't exist and navigate to it
        try:
            ftp.cwd(directory)
        except error_perm:
            # Try to create the directory path
            self._ftp_mkdirs(ftp, directory)
            ftp.cwd(directory)
        
        return ftp

    def _ftp_mkdirs(self, ftp: FTP, path: str):
        """Create directories recursively on FTP server"""
        dirs = path.strip('/').split('/')
        current = ''
        for d in dirs:
            current += '/' + d
            try:
                ftp.cwd(current)
            except error_perm:
                ftp.mkd(current)

    def get_storage_type(self) -> str:
        """
        Get the configured storage type

        Returns:
            Storage type: 'local' or 'remote'
        """
        return self.config.get('storage', {}).get('type', 'local')

    def get_storage_directory(self) -> str:
        """
        Get the configured storage directory based on storage type

        Returns:
            Storage directory path
        """
        storage_type = self.get_storage_type()
        storage_config = self.config.get('storage', {})

        if storage_type == 'local':
            return storage_config.get('local', {}).get('directory', '/var/backups/sipwise')
        else:  # remote
            return storage_config.get('remote', {}).get('directory', '/backups/sipwise')

    def generate_backup_name(self, backup_type: str = "auto", extension: str = '.zip') -> str:
        """
        Generate a backup filename using the format:
        server_name-instance_type-backup_type-date(HH:MM/DD/MM/YYYY)

        Args:
            backup_type: Type of backup ("auto" or "manual")
            extension: File extension (default: .zip)

        Returns:
            Formatted backup filename
        """
        server_name = self.config.get('server_name', 'unknown-server')
        instance_type = self.config.get('instance_type', 'unknown')

        # Format: HH:MM/DD/MM/YYYY -> HH-MM_DD-MM-YYYY
        now = datetime.now()
        date_str = now.strftime("%H-%M_%d-%m-%Y")

        return f"{server_name}-{instance_type}-{backup_type}-{date_str}{extension}"

    def parse_backup_name(self, filename: str) -> Optional[Dict]:
        """
        Parse a backup filename to extract metadata

        Args:
            filename: Backup filename to parse

        Returns:
            Dictionary with server_name, instance_type, type, and datetime, or None if invalid
        """
        try:
            # Remove extension
            name_without_ext = os.path.splitext(filename)[0]

            # Split by hyphens
            parts = name_without_ext.split('-')

            # Minimum parts needed:
            # Old format: server-instance-HH-MM_DD-MM-YYYY
            #   Example: "myserver-master-14-30_13-01-2026" = 6 parts
            # New format: server-instance-auto-HH-MM_DD-MM-YYYY
            #   Example: "myserver-master-auto-14-30_13-01-2026" = 7 parts
            if len(parts) < 6:
                return None

            # Try to detect if backup_type is present (auto/manual)
            # Time is always the last 4 parts: HH, MM_DD, MM, YYYY
            backup_type = "unknown"
            
            # Check if the 5th part from the end is 'auto' or 'manual'
            if len(parts) >= 7 and parts[-5] in ['auto', 'manual']:
                # New format with backup type
                backup_type = parts[-5]
                server_instance_parts = parts[:-5]  # everything before backup_type
            else:
                # Old format without backup type
                server_instance_parts = parts[:-4]  # everything before time
            
            # Extract server_name and instance_type from server_instance_parts
            instance_type = server_instance_parts[-1] if server_instance_parts else 'unknown'
            server_name = '-'.join(server_instance_parts[:-1]) if len(server_instance_parts) > 1 else 'unknown'
            
            # Parse time parts: HH, MM_DD, MM, YYYY
            time_parts = parts[-4:]
            hour = time_parts[0]
            minute_day = time_parts[1].split('_')
            
            # Expect MM_DD format with underscore
            if len(minute_day) != 2:
                # Malformed filename - missing underscore in MM_DD
                return None
            
            minute = minute_day[0]
            day = minute_day[1]
            month = time_parts[2]
            year = time_parts[3]

            # Create datetime object
            dt = datetime.strptime(f"{year}-{month}-{day} {hour}:{minute}", "%Y-%m-%d %H:%M")

            return {
                'server_name': server_name,
                'instance_type': instance_type,
                'type': backup_type,
                'datetime': dt,
                'filename': filename
            }
        except Exception:
            return None

    def zip_directory(self, source_dir: str, output_filename: str) -> str:
        """
        Zip a directory into a backup file

        Args:
            source_dir: Directory to zip (typically tmp directory)
            output_filename: Name for the output zip file

        Returns:
            Path to the created zip file
        """
        zip_path = os.path.join(self.tmp_dir, output_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)

        return zip_path

    def unzip_backup(self, zip_path: str, destination_dir: Optional[str] = None) -> str:
        """
        Unzip a backup file

        Args:
            zip_path: Path to the zip file
            destination_dir: Directory to extract to (default: tmp_dir)

        Returns:
            Path to the extracted directory
        """
        if destination_dir is None:
            destination_dir = self.tmp_dir

        extract_path = os.path.join(destination_dir, 'extracted')
        os.makedirs(extract_path, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_path)

        return extract_path

    def save_backup_local(self, zip_path: str) -> bool:
        """
        Save a backup file to local storage

        Args:
            zip_path: Path to the zip file to save

        Returns:
            True if successful, False otherwise
        """
        try:
            storage_dir = self.get_storage_directory()
            os.makedirs(storage_dir, exist_ok=True)

            filename = os.path.basename(zip_path)
            destination = os.path.join(storage_dir, filename)

            shutil.copy2(zip_path, destination)
            return True
        except Exception as e:
            print(f"Error saving backup locally: {e}")
            return False

    def save_backup_remote(self, zip_path: str) -> bool:
        """
        Save a backup file to remote FTP storage

        Args:
            zip_path: Path to the zip file to save

        Returns:
            True if successful, False otherwise
        """
        try:
            ftp = self._ftp_connect()
            filename = os.path.basename(zip_path)
            
            self.logger.debug(f"Uploading {filename} to FTP server")
            with open(zip_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
            
            ftp.quit()
            self.logger.success(f"Backup uploaded to FTP: {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving backup to FTP: {e}")
            return False

    def save_backup(self, zip_path: str) -> bool:
        """
        Save a backup file to configured storage location

        Args:
            zip_path: Path to the zip file to save

        Returns:
            True if successful, False otherwise
        """
        storage_type = self.get_storage_type()
        
        self.logger.debug(f"Saving backup: {os.path.basename(zip_path)}")

        if storage_type == 'local':
            result = self.save_backup_local(zip_path)
            if result:
                self.logger.success(f"Backup saved to {self.get_storage_directory()}")
            else:
                self.logger.error(f"Failed to save backup to local storage")
            return result
        else:  # remote
            result = self.save_backup_remote(zip_path)
            if result:
                self.logger.success(f"Backup saved to remote storage")
            else:
                self.logger.error(f"Failed to save backup to remote storage")
            return result

    def list_backups(self) -> List[Dict]:
        """
        List all available backups from storage

        Returns:
            List of dictionaries containing backup metadata
        """
        storage_type = self.get_storage_type()

        if storage_type == 'local':
            return self._list_backups_local()
        else:  # remote
            return self._list_backups_remote()

    def _list_backups_local(self) -> List[Dict]:
        """
        List backups from local storage

        Returns:
            List of backup metadata dictionaries
        """
        backups = []
        storage_dir = self.get_storage_directory()

        if not os.path.exists(storage_dir):
            return backups

        for filename in os.listdir(storage_dir):
            if filename.endswith('.zip'):
                metadata = self.parse_backup_name(filename)
                if metadata:
                    file_path = os.path.join(storage_dir, filename)
                    metadata['path'] = file_path
                    metadata['size'] = os.path.getsize(file_path)
                    backups.append(metadata)

        # Sort by datetime, newest first
        backups.sort(key=lambda x: x['datetime'], reverse=True)
        return backups

    def _list_backups_remote(self) -> List[Dict]:
        """
        List backups from remote FTP storage

        Returns:
            List of backup metadata dictionaries
        """
        backups = []
        try:
            ftp = self._ftp_connect()
            
            # List files in directory
            files = ftp.nlst()
            
            for filename in files:
                if filename.endswith('.zip'):
                    metadata = self.parse_backup_name(filename)
                    if metadata:
                        # Get file size
                        try:
                            size = ftp.size(filename)
                        except:
                            size = 0
                        metadata['size'] = size
                        metadata['path'] = filename  # Remote path is just filename
                        backups.append(metadata)
            
            ftp.quit()
            
            # Sort by datetime, newest first
            backups.sort(key=lambda x: x['datetime'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error listing backups from FTP: {e}")
        
        return backups

    def get_backup_by_name(self, filename: str) -> Optional[str]:
        """
        Get the full path to a backup file by filename

        Args:
            filename: Name of the backup file

        Returns:
            Full path to the backup file, or None if not found
        """
        storage_type = self.get_storage_type()
        storage_dir = self.get_storage_directory()

        if storage_type == 'local':
            file_path = os.path.join(storage_dir, filename)
            if os.path.exists(file_path):
                return file_path

        return None

    def download_backup_to_tmp(self, filename: str) -> Optional[str]:
        """
        Download/copy a backup to the tmp directory

        Args:
            filename: Name of the backup file

        Returns:
            Path to the backup in tmp directory, or None if failed
        """
        storage_type = self.get_storage_type()

        if storage_type == 'local':
            source = self.get_backup_by_name(filename)
            if source:
                destination = os.path.join(self.tmp_dir, filename)
                shutil.copy2(source, destination)
                return destination
        else:
            # Download from FTP
            return self._download_backup_ftp(filename)

        return None

    def _download_backup_ftp(self, filename: str) -> Optional[str]:
        """Download backup from FTP to tmp directory"""
        try:
            ftp = self._ftp_connect()
            
            local_path = os.path.join(self.tmp_dir, filename)
            
            self.logger.debug(f"Downloading {filename} from FTP")
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f'RETR {filename}', f.write)
            
            ftp.quit()
            self.logger.success(f"Downloaded backup from FTP: {filename}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Error downloading backup from FTP: {e}")
            return None

    def clean_tmp(self):
        """Remove all files from the tmp directory"""
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
            self._ensure_tmp_dir()

    def get_last_backup_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the most recent backup

        Returns:
            Datetime of the last backup, or None if no backups exist
        """
        backups = self.list_backups()
        if backups:
            return backups[0]['datetime']
        return None

    def delete_backup(self, filename: str) -> bool:
        """
        Delete a backup file from storage

        Args:
            filename: Name of the backup file to delete

        Returns:
            True if successful, False otherwise
        """
        storage_type = self.get_storage_type()
        
        if storage_type == 'local':
            return self.delete_backup_local(filename)
        else:
            return self.delete_backup_remote(filename)

    def delete_backup_local(self, filename: str) -> bool:
        """Delete a backup from local storage"""
        try:
            file_path = self.get_backup_by_name(filename)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug(f"Deleted backup: {filename}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete backup: {e}")
            print(f"Error deleting backup: {e}")
            return False

    def delete_backup_remote(self, filename: str) -> bool:
        """Delete a backup from remote FTP storage"""
        try:
            ftp = self._ftp_connect()
            
            self.logger.debug(f"Deleting {filename} from FTP")
            ftp.delete(filename)
            
            ftp.quit()
            self.logger.success(f"Deleted backup from FTP: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting backup from FTP: {e}")
            return False
    
    def test_ftp_connection(self) -> Tuple[bool, str]:
        """
        Test FTP connection with current configuration
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        self.logger.info("Testing FTP connection")
        
        try:
            remote_config = self.config.get('storage', {}).get('remote', {})
            hostname = remote_config.get('hostname')
            port = remote_config.get('port', 21)
            username = remote_config.get('username', '')
            directory = remote_config.get('directory', '/backups/sipwise')
            
            if not hostname:
                error_msg = "FTP hostname not configured in config.yml"
                self.logger.error(f"FTP test failed: {error_msg}")
                return False, error_msg
            
            self.logger.debug(f"Testing FTP connection to {hostname}:{port}")
            
            print(f"Testing FTP connection to {hostname}:{port}...")
            print(f"Username: {username}")
            print(f"Directory: {directory}")
            print()
            
            # Attempt connection
            print("[1/4] Connecting to FTP server...")
            ftp = self._ftp_connect()
            print("      ✓ Connected successfully")
            
            # Test directory listing
            print("[2/4] Testing directory listing...")
            files = []
            ftp.retrlines('LIST', files.append)
            print(f"      ✓ Listed {len(files)} item(s) in directory")
            
            # Test permissions (try to get current directory)
            print("[3/4] Verifying permissions...")
            current_dir = ftp.pwd()
            print(f"      ✓ Current directory: {current_dir}")
            
            # Disconnect
            print("[4/4] Disconnecting...")
            ftp.quit()
            print("      ✓ Disconnected successfully")
            
            print()
            success_msg = f"FTP connection test successful! Connected to {hostname}:{port}"
            self.logger.success("FTP connection test completed successfully")
            return True, success_msg
            
        except Exception as e:
            error_msg = f"FTP connection test failed: {str(e)}"
            print(f"\n✗ {error_msg}")
            self.logger.error(f"FTP test failed: {e}")
            return False, error_msg


# Convenience functions for external use
def get_storage_manager() -> StorageManager:
    """
    Get a StorageManager instance

    Returns:
        StorageManager instance
    """
    return StorageManager()


if __name__ == "__main__":
    # Test the storage manager
    sm = StorageManager()
    print(f"Storage type: {sm.get_storage_type()}")
    print(f"Storage directory: {sm.get_storage_directory()}")
    print(f"Sample backup name: {sm.generate_backup_name()}")
    print(f"Tmp directory: {sm.tmp_dir}")
