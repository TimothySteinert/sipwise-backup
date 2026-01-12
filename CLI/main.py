#!/usr/bin/env python3
"""
sipwise-backup CLI Application
Main Menu Interface
Version: 1.0.0
"""

import sys
import os
import subprocess


class SipwiseBackupCLI:
    """Main CLI class for sipwise-backup application"""

    def __init__(self):
        self.version = "1.0.0"
        self.running = True
        self.install_dir = "/opt/sipwise-backup"
        self.config_file = os.path.join(self.install_dir, "config.yml")

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
        print("(5) Make DR Instance Live")
        print("(6) Exit")
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
            self.show_config_menu()
            choice = self.get_user_choice()

            if choice == "1":
                self.edit_config()
            elif choice == "2":
                self.restart_service()
            elif choice == "3":
                print("\nReturning to main menu...")
                in_config_menu = False
            elif choice == "exit":
                self.handle_exit()
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please select a valid option.")

    def handle_manual_backup(self):
        """Handle manual backup menu"""
        in_backup_menu = True
        while in_backup_menu:
            print("\n" + "=" * 40)
            print("Later this will show progress of requested manual backup")
            print("=" * 40)
            print("\n(1) Return to main menu")
            print()

            choice = self.get_user_choice()

            if choice == "1":
                print("\nReturning to main menu...")
                in_backup_menu = False
            elif choice == "exit":
                self.handle_exit()
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please select a valid option.")

    def handle_list_backups(self):
        """Handle list backups menu"""
        in_list_menu = True
        while in_list_menu:
            print("\n" + "=" * 40)
            print("Last backup time: [Will be populated later]")
            print("=" * 40)
            print("\nLater this will show a list of backups")
            print("(Table with backup name and timestamp columns)")
            print("\n(1) Return to main menu")
            print()

            choice = self.get_user_choice()

            if choice == "1":
                print("\nReturning to main menu...")
                in_list_menu = False
            elif choice == "exit":
                self.handle_exit()
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please select a valid option.")

    def handle_restore_backup(self):
        """Handle restore backup menu"""
        in_restore_menu = True
        while in_restore_menu:
            print("\n" + "=" * 40)
            print("Available Backups:")
            print("=" * 40)
            print("\n[Later this will show numbered list of backups]")
            print("\nExample:")
            print("  (1) backup_2026-01-12_10-30-00")
            print("  (2) backup_2026-01-11_10-30-00")
            print("  (3) backup_2026-01-10_10-30-00")
            print("\n(0) Return to main menu")
            print()

            choice = self.get_user_choice()

            if choice == "0":
                print("\nReturning to main menu...")
                in_restore_menu = False
            elif choice == "exit":
                self.handle_exit()
            elif choice.isdigit() and int(choice) > 0:
                # Simulate backup selection
                backup_name = f"backup_example_{choice}"
                self.handle_restore_confirmation(backup_name)
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please select a valid option.")

    def handle_restore_confirmation(self, backup_name):
        """Handle restore confirmation process"""
        # Step 1: Confirm restore
        print(f"\nRestore '{backup_name}'? (Y/N): ", end="")
        confirm = input().strip().upper()

        if confirm != "Y":
            print("Restore cancelled.")
            return

        # Step 2: Overwrite SQL encryption key
        print(f"\nOverwrite SQL encryption key? (Y/N): ", end="")
        sql_key = input().strip().upper()

        # Step 3: Restore SIP register data with warning
        print("\n" + "!" * 60)
        print("WARNING: THIS WILL MAKE THE ENVIRONMENT LIVE!")
        print("If restoring to a disaster recovery server,")
        print("ensure the main server is offline.")
        print("!" * 60)
        print(f"\nRestore SIP register data? (Y/N): ", end="")
        sip_register = input().strip().upper()

        print("\n[Restore process would execute here]")
        print(f"Backup: {backup_name}")
        print(f"SQL Key Overwrite: {sql_key}")
        print(f"SIP Register: {sip_register}")
        print("\nPress Enter to return to main menu...")
        input()

    def handle_make_dr_live(self):
        """Handle making DR instance live"""
        in_dr_menu = True
        while in_dr_menu:
            print("\n" + "!" * 60)
            print("WARNING: THIS WILL MAKE THE ENVIRONMENT LIVE!")
            print("If restoring to a disaster recovery server,")
            print("ensure the main server is offline.")
            print("!" * 60)
            print("\nAre you sure you want to make this DR instance a live instance?")
            print("\n(Y) Yes, make live")
            print("(N) No, return to main menu")
            print()

            choice = self.get_user_choice().upper()

            if choice == "Y":
                print("\n[DR instance would be made live here]")
                print("Press Enter to return to main menu...")
                input()
                in_dr_menu = False
            elif choice == "N":
                print("\nReturning to main menu...")
                in_dr_menu = False
            elif choice == "EXIT":
                self.handle_exit()
            else:
                print(f"\nInvalid choice: {choice}")
                print("Please enter Y or N.")

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
            self.handle_make_dr_live()
        elif choice == "6":
            self.handle_exit()
        elif choice == "exit":
            self.handle_exit()
        else:
            print(f"\nInvalid choice: {choice}")
            print("Please select a valid option.")

    def run(self):
        """Main application loop"""
        self.show_banner()

        while self.running:
            self.show_menu()
            choice = self.get_user_choice()
            self.handle_choice(choice)


def main():
    """Entry point for the application"""
    try:
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
