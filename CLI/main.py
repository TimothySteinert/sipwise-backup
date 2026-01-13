#!/usr/bin/env python3
"""
sipwise-backup CLI Application
Main Menu Interface
Version: 1.0.0
"""

import sys
import os
import subprocess

# Add parent directory to path to import backup module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backup import BackupManager
from storage import StorageManager
from restore import RestoreManager


class SipwiseBackupCLI:
    """Main CLI class for sipwise-backup application"""
    
    # Table formatting constants
    BACKUP_TABLE_SEPARATOR_LENGTH = 77  # Length of separator line for backup tables

    def __init__(self):
        self.version = "1.0.0"
        self.running = True
        self.install_dir = "/opt/sipwise-backup"
        self.config_file = os.path.join(self.install_dir, "config.yml")

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear')

    def show_banner(self):
        """Display application banner"""
        print("=" * 40)
        print(f"   sipwise-backup CLI v{self.version}")
        print("=" * 40)
        print()

    def show_menu(self):
        """Display main menu options"""
        print("\n--- Main Menu ---")
        print("(1) Config Menu")
        print("(2) Run Manual Backup")
        print("(3) List Backups")
        print("(4) Restore from Backup")
        print("(5) Exit")
        print()

    def show_config_menu(self):
        """Display config submenu options"""
        print("\n--- Config Menu ---")
        print("(1) Edit config.yml")
        print("(2) Restart service")
        print("(3) Return to main menu")
        print()

    def get_user_choice(self):
        """Get user input for menu selection"""
        try:
            choice = input("Enter your choice: ").strip()
            return choice
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting...")
            return "exit"

    def edit_config(self):
        """Open config.yml in nano editor"""
        print(f"\nOpening {self.config_file} in nano...")
        print("Press Ctrl+X to exit nano\n")
        try:
            subprocess.run(["nano", self.config_file], check=True)
            print("\nConfig file editor closed.")
        except subprocess.CalledProcessError:
            print("\nError: Failed to open nano editor.")
        except FileNotFoundError:
            print("\nError: nano editor not found. Please install nano.")

    def restart_service(self):
        """Restart the sipwise-backup systemd service"""
        print("\nRestarting sipwise-backup service...")
        try:
            result = subprocess.run(
                ["systemctl", "restart", "sipwise-backup.service"],
                capture_output=True,
                text=True,
                check=True
            )
            print("✓ Service restarted successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to restart service.")
            print(f"You may need to run: sudo systemctl restart sipwise-backup")
        except PermissionError:
            print("Error: Permission denied. Try running:")
            print("  sudo systemctl restart sipwise-backup")

    def handle_config_menu(self):
        """Handle config menu navigation"""
        in_config_menu = True
        while in_config_menu:
            self.clear_screen()
            self.show_banner()
            self.show_config_menu()
            choice = self.get_user_choice()

            if choice == "1":
                self.edit_config()
            elif choice == "2":
                self.restart_service()
            elif choice == "3":
                in_config_menu = False
            elif choice == "exit":
                self.handle_exit()
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please select a valid option.")
                input("\nPress Enter to continue...")

        self.clear_screen()
        self.show_banner()

    def handle_manual_backup(self):
        """Handle manual backup menu"""
        self.clear_screen()
        self.show_banner()
        print("=" * 60)
        print("Manual Backup")
        print("=" * 60)
        print()

        try:
            # Create backup manager and run backup
            backup_manager = BackupManager(self.config_file)

            print("Starting manual backup...")
            print()

            result = backup_manager.run_backup(backup_type="manual")

            print()
            if result:
                print(f"✓ Backup completed successfully!")
                print(f"  Backup file: {result}")
            else:
                print("✗ Backup failed. Check the output above for errors.")

        except Exception as e:
            print()
            print(f"✗ Error during backup: {e}")

        print()
        print("Press Enter to return to main menu...")
        input()

        self.clear_screen()
        self.show_banner()

    def handle_list_backups(self):
        """Handle list backups menu"""
        try:
            storage = StorageManager(self.config_file)
            backups = storage.list_backups()
            page_size = 15
            current_page = 0
            total_pages = (len(backups) + page_size - 1) // page_size if backups else 1

            in_list_menu = True
            while in_list_menu:
                self.clear_screen()
                self.show_banner()
                print("=" * 80)
                print("Backup List")
                print("=" * 80)
                print()

                # Show last backup time
                last_backup = storage.get_last_backup_time()
                if last_backup:
                    print(f"Latest backup: {last_backup.strftime('%d/%m/%Y %H:%M')}")
                else:
                    print("Latest backup: No backups found")
                print()

                if not backups:
                    print("No backups available.")
                    print()
                else:
                    # Calculate page slice
                    start_idx = current_page * page_size
                    end_idx = min(start_idx + page_size, len(backups))
                    page_backups = backups[start_idx:end_idx]

                    # Display table header
                    print(f"{'#':<4} {'Server Name':<25} {'Type':<12} {'Backup Type':<12} {'Date & Time':<20}")
                    print("-" * self.BACKUP_TABLE_SEPARATOR_LENGTH)

                    # Display backups
                    for idx, backup in enumerate(page_backups, start=start_idx + 1):
                        server_name = backup['server_name']
                        instance_type = backup['instance_type']
                        backup_type = backup.get('type', 'unknown')
                        # Display type with capitalization
                        type_display = backup_type.capitalize() if backup_type != 'unknown' else 'Unknown'
                        dt = backup['datetime'].strftime('%d/%m/%Y %H:%M')
                        print(f"{idx:<4} {server_name:<25} {instance_type:<12} {type_display:<12} {dt:<20}")

                    print()
                    print(f"Page {current_page + 1} of {total_pages} (Total backups: {len(backups)})")
                    print()

                # Show navigation options
                print("Options:")
                if total_pages > 1:
                    if current_page > 0:
                        print("  (P) Previous page")
                    if current_page < total_pages - 1:
                        print("  (N) Next page")
                print("  (1) Return to main menu")
                print()

                choice = self.get_user_choice().upper()

                if choice == "1":
                    in_list_menu = False
                elif choice == "N" and current_page < total_pages - 1:
                    current_page += 1
                elif choice == "P" and current_page > 0:
                    current_page -= 1
                elif choice == "EXIT":
                    self.handle_exit()
                else:
                    print(f"\nInvalid choice: {choice}")
                    print("Please select a valid option.")
                    input("\nPress Enter to continue...")

        except Exception as e:
            self.clear_screen()
            self.show_banner()
            print(f"Error listing backups: {e}")
            input("\nPress Enter to return to main menu...")

        self.clear_screen()
        self.show_banner()

    def handle_restore_backup(self):
        """Handle restore backup menu"""
        try:
            storage = StorageManager(self.config_file)
            backups = storage.list_backups()

            in_restore_menu = True
            while in_restore_menu:
                self.clear_screen()
                self.show_banner()
                print("=" * 80)
                print("Restore from Backup")
                print("=" * 80)
                print()

                if not backups:
                    print("No backups available for restore.")
                    print()
                    print("(1) Return to main menu")
                    print()
                    choice = self.get_user_choice()
                    if choice == "1" or choice.upper() == "EXIT":
                        in_restore_menu = False
                    continue

                # Display available backups
                print(f"{'#':<4} {'Server Name':<25} {'Type':<12} {'Backup Type':<12} {'Date & Time':<20}")
                print("-" * self.BACKUP_TABLE_SEPARATOR_LENGTH)

                for idx, backup in enumerate(backups, start=1):
                    server_name = backup['server_name']
                    instance_type = backup['instance_type']
                    backup_type = backup.get('type', 'unknown')
                    # Display type with capitalization
                    type_display = backup_type.capitalize() if backup_type != 'unknown' else 'Unknown'
                    dt = backup['datetime'].strftime('%d/%m/%Y %H:%M')
                    print(f"{idx:<4} {server_name:<25} {instance_type:<12} {type_display:<12} {dt:<20}")

                print()
                print("(0) Return to main menu")
                print()

                choice = self.get_user_choice()

                if choice == "0":
                    in_restore_menu = False
                elif choice.upper() == "EXIT":
                    self.handle_exit()
                elif choice.isdigit() and 1 <= int(choice) <= len(backups):
                    # User selected a valid backup
                    selected_backup = backups[int(choice) - 1]
                    self.handle_restore_confirmation(selected_backup)
                else:
                    print(f"\nInvalid choice: {choice}")
                    print("Please select a valid option.")
                    input("\nPress Enter to continue...")

        except Exception as e:
            self.clear_screen()
            self.show_banner()
            print(f"Error in restore menu: {e}")
            input("\nPress Enter to return to main menu...")
            in_restore_menu = False

        self.clear_screen()
        self.show_banner()

    def handle_restore_confirmation(self, backup):
        """Handle restore confirmation process"""
        self.clear_screen()
        self.show_banner()

        backup_name = backup['filename']
        print("=" * 80)
        print("Restore Confirmation")
        print("=" * 80)
        print()
        print(f"Backup: {backup_name}")
        print(f"Server: {backup['server_name']}")
        print(f"Type: {backup['instance_type']}")
        print(f"Date: {backup['datetime'].strftime('%d/%m/%Y %H:%M')}")
        print()

        # Step 1: Confirm restore
        print("Restore this backup? (Y/N): ", end="")
        confirm = input().strip().upper()

        if confirm != "Y":
            print("\nRestore cancelled.")
            input("\nPress Enter to continue...")
            return

        # Step 2: Preserve SQL encryption key
        print("\nPreserve current SQL encryption key? (Y/N): ", end="")
        preserve_key = input().strip().upper()
        preserve_sql_key = (preserve_key == "Y")

        # Step 3: Restore SIP register data with warning
        print("\n" + "!" * 80)
        print("WARNING: THIS WILL MAKE THE ENVIRONMENT LIVE!")
        print("Ensure no other instances are running before continuing.")
        print("!" * 80)
        print("\nPress N to return to menu or Y to continue: ", end="")
        sip_register = input().strip().upper()

        if sip_register != "Y":
            print("\nRestore cancelled.")
            input("\nPress Enter to continue...")
            return

        restore_sip_register = True

        # Execute restore
        print()
        print("=" * 80)
        print("Starting restore operation...")
        print("=" * 80)
        print()

        try:
            restore_manager = RestoreManager(self.config_file)
            success = restore_manager.run_restore(
                backup_name,
                preserve_sql_key=preserve_sql_key,
                restore_sip_register=restore_sip_register
            )

            print()
            if success:
                print("✓ Restore completed successfully!")
            else:
                print("✗ Restore failed. Check the output above for errors.")

        except Exception as e:
            print()
            print(f"✗ Error during restore: {e}")

        print()
        print("Press Enter to return to main menu...")
        input()

    def handle_exit(self):
        """Handle exit command"""
        print("\nExiting sipwise-backup...")
        self.running = False
        sys.exit(0)

    def handle_choice(self, choice):
        """Process user menu choice"""
        if choice == "1":
            self.handle_config_menu()
        elif choice == "2":
            self.handle_manual_backup()
        elif choice == "3":
            self.handle_list_backups()
        elif choice == "4":
            self.handle_restore_backup()
        elif choice == "5":
            self.handle_exit()
        elif choice == "exit":
            self.handle_exit()
        else:
            print(f"\nInvalid choice: {choice}")
            print("Please select a valid option.")
            input("\nPress Enter to continue...")
            self.clear_screen()
            self.show_banner()

    def run(self):
        """Main application loop"""
        self.clear_screen()
        self.show_banner()

        while self.running:
            self.show_menu()
            choice = self.get_user_choice()
            self.handle_choice(choice)


def main():
    """Entry point for the application"""
    try:
        # Always run in interactive CLI mode
        cli = SipwiseBackupCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
