#!/usr/bin/env python3
"""
scheduler.py - Scheduler Module for sipwise-backup
Handles automatic backup scheduling, retention policy, and cleanup
"""

import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import sys
import subprocess
import shutil

# Import our modules
from storage import StorageManager
from backup import BackupManager
from logger import get_logger
from emailer import get_emailer



class BackupScheduler:
    """Manages automatic backup scheduling and retention"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the BackupScheduler

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.storage = StorageManager(config_path)
        self.backup_manager = BackupManager(config_path)
        self.config = self.storage.config
        self.running = False
        self.last_reboot_month = None  # Track last reboot to prevent duplicates
        self.logger = get_logger(config_path)
        self.emailer = get_emailer(config_path)
        self.state_dir = Path("/opt/sipwise-backup/state")
        self.state_file = self.state_dir / "scheduler_state.json"
        self._ensure_state_dir()
        self.logger.info("BackupScheduler initialized")

    def _ensure_state_dir(self):
        """Ensure the state directory exists"""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        """Load scheduler state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warn(f"Could not load state file: {e}")
        return {}

    def _save_state(self, state: dict):
        """Save scheduler state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save state file: {e}")

    def is_automatic_backup_enabled(self) -> bool:
        """
        Check if automatic backups are enabled

        Returns:
            True if enabled, False otherwise
        """
        backup_config = self.config.get('backup', {})
        automatic_config = backup_config.get('automatic', {})
        return automatic_config.get('enabled', False)

    def get_backup_frequency_seconds(self) -> int:
        """
        Get backup frequency in seconds

        Returns:
            Frequency in seconds
        """
        backup_config = self.config.get('backup', {})
        automatic_config = backup_config.get('automatic', {})
        frequency_config = automatic_config.get('frequency', {})

        value = frequency_config.get('value', 1)
        unit = frequency_config.get('unit', 'hours')

        if unit == 'minutes':
            return value * 60
        elif unit == 'hours':
            return value * 60 * 60
        else:
            # Default to hours
            return value * 60 * 60

    def is_automatic_reboot_enabled(self) -> bool:
        """
        Check if automatic reboot is enabled
        
        Returns:
            True if enabled, False otherwise
        """
        reboot_config = self.config.get('reboot', {})
        return reboot_config.get('automatic', 'disabled') == 'enabled'

    def get_reboot_schedule(self) -> Dict[str, any]:
        """
        Get the reboot schedule configuration
        
        Returns:
            Dictionary with 'day_of_month' (int) and 'time' (str in HH:MM format)
        """
        reboot_config = self.config.get('reboot', {})
        schedule_config = reboot_config.get('schedule', {})
        return {
            'day_of_month': schedule_config.get('day_of_month', 1),
            'time': schedule_config.get('time', '03:00')
        }

    def should_reboot_now(self) -> bool:
        """
        Check if it's time to perform the scheduled reboot
        
        Returns:
            True if current date/time matches the reboot schedule
        """
        schedule = self.get_reboot_schedule()
        now = datetime.now()
        
        # Check if today is the scheduled day of month
        if now.day != schedule['day_of_month']:
            return False
        
        # Parse scheduled time with validation
        scheduled_time = schedule.get('time')
        if not scheduled_time:
            print("[ERROR] Reboot time not configured")
            return False
            
        try:
            scheduled_hour, scheduled_minute = map(int, scheduled_time.split(':'))
            if not (0 <= scheduled_hour <= 23 and 0 <= scheduled_minute <= 59):
                print(f"[ERROR] Invalid reboot time in config: {scheduled_time}")
                return False
        except (ValueError, AttributeError):
            print(f"[ERROR] Invalid reboot time format in config: {scheduled_time}")
            return False
        
        # Check if current time matches (within the current minute)
        if now.hour == scheduled_hour and now.minute == scheduled_minute:
            return True
        
        return False

    def perform_reboot(self):
        """
        Perform the system reboot
        """
        self.logger.warn("System reboot initiated by scheduler")
        print("\n" + "=" * 80)
        print(f"SCHEDULED REBOOT - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 80)
        
        # Save pending notification state BEFORE reboot
        # This will be checked on next startup to send success email
        state = self._load_state()
        state['pending_reboot_notification'] = time.time()
        self._save_state(state)
        self.logger.info("Saved pending reboot notification state")
        
        print("[!] Initiating system reboot...")
        print("=" * 80)
        
        # Find the reboot command path dynamically for cross-platform support
        reboot_cmd = shutil.which('reboot')
        if not reboot_cmd:
            # Try common paths as fallback
            for path in ['/sbin/reboot', '/usr/sbin/reboot']:
                if Path(path).exists():
                    reboot_cmd = path
                    break
        
        if not reboot_cmd:
            error_msg = "Reboot command not found on this system"
            self._handle_reboot_error(error_msg)
            return
        
        # Use subprocess to run the reboot command
        try:
            subprocess.run([reboot_cmd], check=True)
            # Note: Email will be sent after system comes back online
            # (pending_reboot_notification will be checked on startup)
        except subprocess.CalledProcessError as e:
            self._handle_reboot_error(f"Reboot command failed: {e}")
        except PermissionError:
            self._handle_reboot_error("Insufficient permissions to execute reboot command")
        except FileNotFoundError:
            self._handle_reboot_error("Reboot command not found")
        except Exception as e:
            self._handle_reboot_error(f"Unexpected error during reboot: {e}")
    
    def _handle_reboot_error(self, error_msg: str):
        """Helper method to handle reboot errors consistently"""
        print(f"[ERROR] {error_msg}")
        self.logger.error(error_msg)
        self.emailer.send_reboot_failure(error_message=error_msg)

    def apply_retention_policy(self) -> int:
        """
        Apply retention policy to delete old backups

        Deletes automatic and unknown backups older than the configured retention days.
        Manual backups are exempt from retention policy.
        Only applies to backups matching the current server name.
        
        Returns:
            Number of backups deleted
        """
        backup_config = self.config.get('backup', {})
        retention_config = backup_config.get('retention', {})
        retention_days = retention_config.get('days', 30)
        current_server_name = self.config.get('server_name', 'unknown-server')

        self.logger.info(f"Applying retention policy (keep last {retention_days} days)")
        print(f"[+] Applying retention policy (keep last {retention_days} days)")

        # Get all backups
        backups = self.storage.list_backups()

        if not backups:
            self.logger.debug("No backups to process")
            print("    No backups to process")
            return

        # Filter backups to only those matching current server name
        matching_backups = [b for b in backups if b.get('server_name') == current_server_name]
        other_server_count = len(backups) - len(matching_backups)
        
        if other_server_count > 0:
            self.logger.debug(f"Skipping {other_server_count} backup(s) from other servers")
            print(f"    Skipping {other_server_count} backup(s) from other servers")

        if not matching_backups:
            self.logger.debug("No backups matching current server name")
            print("    No backups matching current server name")
            return

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        self.logger.debug(f"Cutoff date: {cutoff_date.strftime('%d/%m/%Y %H:%M')}")
        print(f"    Cutoff date: {cutoff_date.strftime('%d/%m/%Y %H:%M')}")

        # Find backups to delete
        deleted_count = 0
        skipped_manual_count = 0
        for backup in matching_backups:
            backup_date = backup['datetime']
            backup_type = backup.get('type', 'unknown')
            
            # Skip manual backups - they are exempt from retention policy
            if backup_type == 'manual':
                skipped_manual_count += 1
                continue
            
            if backup_date < cutoff_date:
                filename = backup['filename']
                self.logger.debug(f"Deleting old backup: {filename}")
                print(f"    Deleting old backup: {filename}")
                if self.storage.delete_backup(filename):
                    deleted_count += 1

        if skipped_manual_count > 0:
            self.logger.debug(f"Skipped {skipped_manual_count} manual backup(s) (exempt from retention)")
            print(f"    Skipped {skipped_manual_count} manual backup(s) (exempt from retention)")
        if deleted_count > 0:
            self.logger.info(f"Deleted {deleted_count} old backup(s)")
            print(f"    Deleted {deleted_count} old backup(s)")
        else:
            self.logger.debug("No old backups to delete")
            print("    No old backups to delete")
        
        # Also apply retention to log files
        self.logger.apply_retention_policy()
        
        return deleted_count

    def apply_cleanup_policy(self) -> int:
        """
        Apply cleanup policy to keep only last backup per day

        If cleanup is enabled with mode 'last_per_day':
        - Groups automatic and unknown backups by calendar day
        - Manual backups are completely excluded from cleanup
        - Skips the current day (today) - all backups are preserved
        - For previous days: keeps only the last (most recent) backup
        - Deletes all other backups from previous days
        - Only applies to backups matching the current server name
        
        Returns:
            Number of backups deleted
        """
        backup_config = self.config.get('backup', {})
        cleanup_config = backup_config.get('cleanup', {})
        cleanup_enabled = cleanup_config.get('enabled', False)
        cleanup_mode = cleanup_config.get('mode', 'last_per_day')
        current_server_name = self.config.get('server_name', 'unknown-server')

        if not cleanup_enabled:
            self.logger.debug("Cleanup policy disabled, skipping")
            print("[+] Cleanup policy disabled, skipping")
            return 0

        if cleanup_mode != 'last_per_day':
            self.logger.warn(f"Unknown cleanup mode: {cleanup_mode}, skipping")
            print(f"[+] Unknown cleanup mode: {cleanup_mode}, skipping")
            return 0

        self.logger.info("Applying cleanup policy (last per day)")
        print("[+] Applying cleanup policy (last per day)")

        # Get all backups
        backups = self.storage.list_backups()

        if not backups:
            self.logger.debug("No backups to process")
            print("    No backups to process")
            return 0

        # Filter backups to only those matching current server name
        matching_backups = [b for b in backups if b.get('server_name') == current_server_name]
        other_server_count = len(backups) - len(matching_backups)
        
        if other_server_count > 0:
            self.logger.debug(f"Skipping {other_server_count} backup(s) from other servers")
            print(f"    Skipping {other_server_count} backup(s) from other servers")

        if not matching_backups:
            self.logger.debug("No backups matching current server name")
            print("    No backups matching current server name")
            return 0

        # Filter out manual backups - they are exempt from cleanup
        auto_backups = []
        manual_count = 0
        for backup in matching_backups:
            backup_type = backup.get('type', 'unknown')
            if backup_type == 'manual':
                manual_count += 1
            else:
                auto_backups.append(backup)

        if manual_count > 0:
            self.logger.debug(f"Excluding {manual_count} manual backup(s) from cleanup")
            print(f"    Excluding {manual_count} manual backup(s) from cleanup")

        if not auto_backups:
            self.logger.debug("No automatic backups to process")
            print("    No automatic backups to process")
            return 0

        # Group backups by date (day)
        backups_by_day = {}
        for backup in auto_backups:
            backup_date = backup['datetime']
            day_key = backup_date.strftime('%Y-%m-%d')

            if day_key not in backups_by_day:
                backups_by_day[day_key] = []

            backups_by_day[day_key].append(backup)

        # Get today's date string for comparison
        today_key = datetime.now().strftime('%Y-%m-%d')

        # For each day, keep only the last backup
        deleted_count = 0
        for day_key, day_backups in backups_by_day.items():
            # Skip the current day - only cleanup previous days
            if day_key == today_key:
                continue
            if len(day_backups) <= 1:
                # Only one backup for this day, keep it
                continue

            # Sort by datetime, newest first
            day_backups.sort(key=lambda x: x['datetime'], reverse=True)

            # Keep the first (newest), delete the rest
            backups_to_delete = day_backups[1:]

            for backup in backups_to_delete:
                filename = backup['filename']
                self.logger.debug(f"Deleting duplicate backup for {day_key}: {filename}")
                print(f"    Deleting duplicate backup for {day_key}: {filename}")
                if self.storage.delete_backup(filename):
                    deleted_count += 1

        if deleted_count > 0:
            self.logger.info(f"Deleted {deleted_count} duplicate backup(s)")
            print(f"    Deleted {deleted_count} duplicate backup(s)")
        else:
            self.logger.debug("No duplicate backups to delete")
            print("    No duplicate backups to delete")
        
        return deleted_count

    def run_scheduled_backup(self):
        """
        Run a scheduled backup and apply retention/cleanup policies
        """
        self.logger.info("Starting scheduled backup")
        print("\n" + "=" * 80)
        print(f"SCHEDULED BACKUP - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 80)

        # Run backup with type="auto", but don't send email yet
        # (scheduler will send email with maintenance info after retention/cleanup)
        result = self.backup_manager.run_backup(backup_type="auto", send_email=False)

        if result:
            self.logger.success(f"Scheduled backup completed: {result}")
            print(f"\n[OK] Scheduled backup completed: {result}")

            # Apply retention policy
            print()
            retention_deleted = self.apply_retention_policy()

            # Apply cleanup policy
            print()
            cleanup_deleted = self.apply_cleanup_policy()
            
            # Check if cleanup is enabled
            backup_config = self.config.get('backup', {})
            cleanup_config = backup_config.get('cleanup', {})
            cleanup_enabled = cleanup_config.get('enabled', False)
            
            # Send success email with maintenance info
            total_deleted = retention_deleted + cleanup_deleted
            self.emailer.send_backup_success(
                backup_filename=result,
                storage_location=self.storage.get_storage_directory(),
                retention_applied=True,
                cleanup_applied=cleanup_enabled,
                deleted_count=total_deleted
            )

            print("\n" + "=" * 80)
            print("SCHEDULED BACKUP COMPLETE")
            print("=" * 80)
        else:
            self.logger.error("Scheduled backup failed")
            print("\n[ERROR] Scheduled backup failed!")
            print("=" * 80)
            
            # Send failure email
            self.emailer.send_backup_failure(
                error_message="Backup process failed. Check logs for details.",
                stage="backup execution"
            )

    def run(self):
        """
        Main scheduler loop

        Service runs continuously. If automatic backups are enabled,
        it runs backups on schedule. If disabled, it idles and periodically
        checks if automatic backups have been enabled.
        """
        self.logger.info("Sipwise Backup Scheduler Starting")
        print("=" * 80)
        print("Sipwise Backup Scheduler Starting")
        print("=" * 80)

        self.running = True
        
        # Load state from file
        state = self._load_state()
        last_backup_time = state.get('last_backup_time')  # Can be None or timestamp
        self.last_reboot_month = state.get('last_reboot_month')
        
        # Check for pending reboot notification from before reboot
        pending_reboot_time = state.get('pending_reboot_notification')
        if pending_reboot_time:
            self.logger.info("Found pending reboot notification, sending success email")
            reboot_datetime = datetime.fromtimestamp(pending_reboot_time)
            
            # Send the success email
            self.emailer.send_reboot_success(reboot_initiated_at=reboot_datetime)
            
            # Clear the pending notification
            state.pop('pending_reboot_notification', None)
            self._save_state(state)
            self.logger.success("Reboot success notification sent")
        
        if last_backup_time:
            self.logger.info(f"Loaded last backup time from state: {datetime.fromtimestamp(last_backup_time)}")
        
        last_config_check = time.time()
        config_check_interval = 300  # Check config every 5 minutes

        while self.running:
            try:
                current_time = time.time()

                # Periodically reload config to check if settings changed
                if current_time - last_config_check >= config_check_interval:
                    self.config = self.storage._load_config()
                    last_config_check = current_time

                # Check if automatic backups are enabled
                if not self.is_automatic_backup_enabled():
                    # Automatic backups disabled - idle
                    if current_time - last_config_check < 10:  # Just checked
                        print("Automatic backups are DISABLED in config")
                        print("Service will idle and check config periodically")
                        print("=" * 80)

                    # Sleep for a minute before checking again
                    time.sleep(60)
                    continue

                # Automatic backups enabled - run scheduler
                frequency_seconds = self.get_backup_frequency_seconds()

                # Print status on first run or after config change
                if last_backup_time is None:
                    backup_config = self.config.get('backup', {})
                    automatic_config = backup_config.get('automatic', {})
                    frequency_config = automatic_config.get('frequency', {})
                    value = frequency_config.get('value', 1)
                    unit = frequency_config.get('unit', 'hours')

                    self.logger.info("Automatic backups ENABLED")
                    self.logger.debug(f"Frequency: {frequency_seconds} seconds")
                    print(f"Automatic backups ENABLED")
                    print(f"Frequency: Every {value} {unit} ({frequency_seconds} seconds)")
                    print(f"Next backup: {(datetime.now() + timedelta(seconds=frequency_seconds)).strftime('%d/%m/%Y %H:%M:%S')}")
                    print()
                    
                    # Print reboot schedule status
                    if self.is_automatic_reboot_enabled():
                        reboot_schedule = self.get_reboot_schedule()
                        print(f"Automatic reboot ENABLED")
                        print(f"Schedule: Day {reboot_schedule['day_of_month']} of each month at {reboot_schedule['time']}")
                    else:
                        print(f"Automatic reboot DISABLED")
                    print("=" * 80)

                # Check if it's time for a backup
                if last_backup_time is None or (current_time - last_backup_time) >= frequency_seconds:
                    # Run scheduled backup
                    self.run_scheduled_backup()
                    last_backup_time = current_time
                    
                    # Save state after backup (preserve pending_reboot_notification if it exists)
                    state = self._load_state()
                    state['last_backup_time'] = last_backup_time
                    state['last_reboot_month'] = self.last_reboot_month
                    self._save_state(state)

                    # Recalculate frequency in case config changed
                    frequency_seconds = self.get_backup_frequency_seconds()

                    # Calculate next backup time
                    next_backup = datetime.now() + timedelta(seconds=frequency_seconds)
                    print(f"\nNext backup: {next_backup.strftime('%d/%m/%Y %H:%M:%S')}")

                # Check for scheduled reboot
                if self.is_automatic_reboot_enabled():
                    if self.should_reboot_now():
                        # Check if we already rebooted this month
                        current_month_key = datetime.now().strftime('%Y-%m')
                        if self.last_reboot_month != current_month_key:
                            # Update tracking before reboot to prevent race condition
                            self.last_reboot_month = current_month_key
                            # Save state before reboot (preserve pending_reboot_notification if it exists)
                            state = self._load_state()
                            state['last_backup_time'] = last_backup_time
                            state['last_reboot_month'] = self.last_reboot_month
                            self._save_state(state)
                            self.perform_reboot()

                # Sleep for a minute before checking again
                time.sleep(60)

            except KeyboardInterrupt:
                print("\n\nScheduler interrupted, stopping...")
                self.running = False
                break
            except Exception as e:
                print(f"\n[ERROR] Scheduler error: {e}")
                print("Sleeping for 5 minutes before retry...")
                time.sleep(300)

        print("\n" + "=" * 80)
        print("Sipwise Backup Scheduler Stopped")
        print("=" * 80)

    def stop(self):
        """Stop the scheduler"""
        self.running = False


# Convenience functions
def run_scheduler():
    """
    Run the backup scheduler

    This is the main entry point when running as a service
    """
    scheduler = BackupScheduler()
    scheduler.run()


def apply_retention_and_cleanup():
    """
    Manually apply retention and cleanup policies without running a backup

    Useful for testing or manual cleanup
    """
    scheduler = BackupScheduler()

    print("=" * 80)
    print("Applying Retention and Cleanup Policies")
    print("=" * 80)
    print()

    scheduler.apply_retention_policy()
    print()
    scheduler.apply_cleanup_policy()

    print()
    print("=" * 80)
    print("Done")
    print("=" * 80)


if __name__ == "__main__":
    # If run directly, start the scheduler
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        # Manual cleanup mode
        apply_retention_and_cleanup()
    else:
        # Normal scheduler mode
        run_scheduler()
