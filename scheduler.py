#!/usr/bin/env python3
"""
scheduler.py - Scheduler Module for sipwise-backup
Handles automatic backup scheduling, retention policy, and cleanup
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import sys

# Import our modules
from storage import StorageManager
from backup import BackupManager


class BackupScheduler:
    """Manages automatic backup scheduling and retention"""

    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the BackupScheduler

        Args:
            config_path: Path to the configuration file
        """
        self.storage = StorageManager(config_path)
        self.backup_manager = BackupManager(config_path)
        self.config = self.storage.config
        self.running = False

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

    def apply_retention_policy(self):
        """
        Apply retention policy to delete old backups

        Deletes automatic and unknown backups older than the configured retention days.
        Manual backups are exempt from retention policy.
        """
        backup_config = self.config.get('backup', {})
        retention_config = backup_config.get('retention', {})
        retention_days = retention_config.get('days', 30)

        print(f"[+] Applying retention policy (keep last {retention_days} days)")

        # Get all backups
        backups = self.storage.list_backups()

        if not backups:
            print("    No backups to process")
            return

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        print(f"    Cutoff date: {cutoff_date.strftime('%d/%m/%Y %H:%M')}")

        # Find backups to delete
        deleted_count = 0
        skipped_manual_count = 0
        for backup in backups:
            backup_date = backup['datetime']
            backup_type = backup.get('type', 'unknown')
            
            # Skip manual backups - they are exempt from retention policy
            if backup_type == 'manual':
                skipped_manual_count += 1
                continue
            
            if backup_date < cutoff_date:
                filename = backup['filename']
                print(f"    Deleting old backup: {filename}")
                if self.storage.delete_backup(filename):
                    deleted_count += 1

        if skipped_manual_count > 0:
            print(f"    Skipped {skipped_manual_count} manual backup(s) (exempt from retention)")
        if deleted_count > 0:
            print(f"    Deleted {deleted_count} old backup(s)")
        else:
            print("    No old backups to delete")

    def apply_cleanup_policy(self):
        """
        Apply cleanup policy to keep only last backup per day

        If cleanup is enabled with mode 'last_per_day':
        - Groups automatic and unknown backups by calendar day
        - Manual backups are completely excluded from cleanup
        - Skips the current day (today) - all backups are preserved
        - For previous days: keeps only the last (most recent) backup
        - Deletes all other backups from previous days
        """
        backup_config = self.config.get('backup', {})
        cleanup_config = backup_config.get('cleanup', {})
        cleanup_enabled = cleanup_config.get('enabled', False)
        cleanup_mode = cleanup_config.get('mode', 'last_per_day')

        if not cleanup_enabled:
            print("[+] Cleanup policy disabled, skipping")
            return

        if cleanup_mode != 'last_per_day':
            print(f"[+] Unknown cleanup mode: {cleanup_mode}, skipping")
            return

        print("[+] Applying cleanup policy (last per day)")

        # Get all backups
        backups = self.storage.list_backups()

        if not backups:
            print("    No backups to process")
            return

        # Filter out manual backups - they are exempt from cleanup
        auto_backups = []
        manual_count = 0
        for backup in backups:
            backup_type = backup.get('type', 'unknown')
            if backup_type == 'manual':
                manual_count += 1
            else:
                auto_backups.append(backup)

        if manual_count > 0:
            print(f"    Excluding {manual_count} manual backup(s) from cleanup")

        if not auto_backups:
            print("    No automatic backups to process")
            return

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
                print(f"    Deleting duplicate backup for {day_key}: {filename}")
                if self.storage.delete_backup(filename):
                    deleted_count += 1

        if deleted_count > 0:
            print(f"    Deleted {deleted_count} duplicate backup(s)")
        else:
            print("    No duplicate backups to delete")

    def run_scheduled_backup(self):
        """
        Run a scheduled backup and apply retention/cleanup policies
        """
        print("\n" + "=" * 80)
        print(f"SCHEDULED BACKUP - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 80)

        # Run backup with type="auto"
        result = self.backup_manager.run_backup(backup_type="auto")

        if result:
            print(f"\n[OK] Scheduled backup completed: {result}")

            # Apply retention policy
            print()
            self.apply_retention_policy()

            # Apply cleanup policy
            print()
            self.apply_cleanup_policy()

            print("\n" + "=" * 80)
            print("SCHEDULED BACKUP COMPLETE")
            print("=" * 80)
        else:
            print("\n[ERROR] Scheduled backup failed!")
            print("=" * 80)

    def run(self):
        """
        Main scheduler loop

        Service runs continuously. If automatic backups are enabled,
        it runs backups on schedule. If disabled, it idles and periodically
        checks if automatic backups have been enabled.
        """
        print("=" * 80)
        print("Sipwise Backup Scheduler Starting")
        print("=" * 80)

        self.running = True
        last_backup_time = None
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

                    print(f"Automatic backups ENABLED")
                    print(f"Frequency: Every {value} {unit} ({frequency_seconds} seconds)")
                    print(f"Next backup: {(datetime.now() + timedelta(seconds=frequency_seconds)).strftime('%d/%m/%Y %H:%M:%S')}")
                    print("=" * 80)

                # Check if it's time for a backup
                if last_backup_time is None or (current_time - last_backup_time) >= frequency_seconds:
                    # Run scheduled backup
                    self.run_scheduled_backup()
                    last_backup_time = current_time

                    # Recalculate frequency in case config changed
                    frequency_seconds = self.get_backup_frequency_seconds()

                    # Calculate next backup time
                    next_backup = datetime.now() + timedelta(seconds=frequency_seconds)
                    print(f"\nNext backup: {next_backup.strftime('%d/%m/%Y %H:%M:%S')}")

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
