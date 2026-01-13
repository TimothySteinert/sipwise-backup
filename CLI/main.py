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
        self._storage_manager = None  # Lazy-loaded storage manager cache

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear')

    @property
    def storage_manager(self):
        """Lazy-loaded storage manager instance"""
        if self._storage_manager is None:
            self._storage_manager = StorageManager(self.config_file)
        return self._storage_manager

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
            storage = self.storage_manager
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
            storage = self.storage_manager
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
        """Handle restore confirmation process with different flows for same/different server"""
        self.clear_screen()
        self.show_banner()
        
        backup_name = backup['filename']
        backup_server = backup['server_name']
        backup_type = backup['instance_type']
        backup_date = backup['datetime'].strftime('%d/%m/%Y %H:%M')
        
        # Get current server info using cached storage manager
        current_server = self.storage_manager.config.get('server_name', '')
        current_type = self.storage_manager.config.get('instance_type', '')
        
        # Check if same server
        is_same_server = (backup_server == current_server and backup_type == current_type)
        
        if is_same_server:
            # SAME SERVER RESTORE FLOW
            self._handle_same_server_restore(backup, backup_name, backup_server, backup_type, backup_date, current_server, current_type)
        else:
            # DIFFERENT SERVER RESTORE FLOW (DR scenario)
            self._handle_different_server_restore(backup, backup_name, backup_server, backup_type, backup_date, current_server, current_type)

    def _handle_same_server_restore(self, backup, backup_name, backup_server, backup_type, backup_date, current_server, current_type):
        """Handle restore to the same server"""
        print("=" * 80)
        print("Restore Summary - Same Server")
        print("=" * 80)
        print()
        print(f"Restoring from: {backup_server} ({backup_type}) - {backup_date}")
        print(f"Restoring to:   {current_server} ({current_type})")
        print()
        print("!" * 80)
        print("WARNING: This will reboot services and stop any in-progress calls!")
        print("!" * 80)
        print()
        print("Proceed with restore? (Y/N): ", end="")
        confirm = input().strip().upper()
        
        if confirm != "Y":
            print("\nRestore cancelled.")
            input("\nPress Enter to continue...")
            return
        
        # Execute restore - same server means:
        # - No SQL key prompt (restore entire constants.yml)
        # - No firewall prompt
        # - No DR warning
        self._execute_restore(
            backup_name,
            preserve_sql_key=False,  # Restore entire constants.yml since same server
            disable_firewall=False,
            restore_sip_register=True
        )

    def _handle_different_server_restore(self, backup, backup_name, backup_server, backup_type, backup_date, current_server, current_type):
        """Handle restore to a different server (DR scenario)"""
        
        # Step 1: SQL Encryption Key Warning
        print("=" * 80)
        print("SQL Encryption Key")
        print("=" * 80)
        print()
        print("!" * 80)
        print("WARNING: When restoring to a DR server, you MUST retain the")
        print("original SQL encryption key to access encrypted database fields!")
        print("!" * 80)
        print()
        print("Preserve current SQL encryption key? (Y/N)")
        print("(Recommended: Y for DR restore)")
        print()
        print("Choice: ", end="")
        preserve_key = input().strip().upper()
        
        if preserve_key != "Y":
            print("\n" + "!" * 80)
            print("Are you SURE you want to use the SQL key from the backup?")
            print("This may cause data access issues on a DR server!")
            print("!" * 80)
            print("\nContinue without preserving key? (Y/N): ", end="")
            confirm = input().strip().upper()
            if confirm != "Y":
                print("\nRestore cancelled.")
                input("\nPress Enter to continue...")
                return
        
        preserve_sql_key = (preserve_key == "Y")
        
        # Step 2: Firewall Rules
        self.clear_screen()
        self.show_banner()
        print("=" * 80)
        print("Firewall Configuration")
        print("=" * 80)
        print()
        print("Do you want to deactivate firewall rules?")
        print()
        print("!" * 80)
        print("WARNING: Changing the server IP may result in the web UI")
        print("becoming inaccessible if firewall rules block the new IP.")
        print("!" * 80)
        print()
        print("Recommended: Y (disable firewall, then manually verify and re-enable)")
        print()
        print("Deactivate firewall? (Y/N): ", end="")
        firewall_choice = input().strip().upper()
        disable_firewall = (firewall_choice == "Y")
        
        # Step 3: Final Summary and DR Warning
        self.clear_screen()
        self.show_banner()
        
        # Get system IP using public static method
        system_ip = RestoreManager.get_system_ipv4_static()
        
        print("=" * 80)
        print("Restore Summary - DR Server")
        print("=" * 80)
        print()
        print(f"Restoring from: {backup_server} ({backup_type}) - {backup_date}")
        print(f"Restoring to:   {current_server} ({current_type})")
        print()
        print(f"SQL Key:        {'Preserve current' if preserve_sql_key else 'Use from backup'}")
        print(f"Firewall:       {'Disable' if disable_firewall else 'Keep enabled'}")
        print()
        print("!" * 80)
        print("CRITICAL DR WARNING")
        print("!" * 80)
        print()
        print("This restore will register to peers after completion.")
        print("The MASTER server must be OFFLINE before proceeding!")
        print()
        print("DO NOT PROCEED IF THIS IS NOT A DR SITUATION!")
        print()
        print("Once completed, only a SINGLE instance (either DR or Master)")
        print("can be active at any time.")
        print()
        print(f"Update DNS records to point to: {system_ip}")
        print("to allow subscribers to connect to the DR server.")
        print()
        print("!" * 80)
        print()
        print("Proceed with DR restore? (Y/N): ", end="")
        confirm = input().strip().upper()
        
        if confirm != "Y":
            print("\nRestore cancelled.")
            input("\nPress Enter to continue...")
            return
        
        # Execute restore
        self._execute_restore(
            backup_name,
            preserve_sql_key=preserve_sql_key,
            disable_firewall=disable_firewall,
            restore_sip_register=True
        )

    def _execute_restore(self, backup_name, preserve_sql_key, disable_firewall, restore_sip_register):
        """Execute the actual restore operation"""
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
                restore_sip_register=restore_sip_register,
                disable_firewall=disable_firewall
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
