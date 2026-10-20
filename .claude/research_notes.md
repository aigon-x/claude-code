#!/bin/bash

# =============================================================================
# Script to securely add a generic password to the macOS keychain with error handling,
# logging, and input validation.
# =============================================================================

# Constants
KEYCHAIN_ITEM_NAME="Claude Code-credentials"
LOG_FILE="/var/log/claude_code.log"

# Function to log messages with timestamp
log_message() {
    local level="$1"
    local message="$2"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $message" >> "$LOG_FILE"
}

# Function to add a generic password to the keychain
add_generic_password() {
    local account="$1"
    local password="$2"

    # Input validation
    if [[ -z "$account" || -z "$password" ]]; then
        log_message "ERROR" "Account and password must not be empty."
        return 1
    fi

    # Attempt to add the password to the keychain
    if security add-generic-password -U -a "$account" -s "$KEYCHAIN_ITEM_NAME" -w "$password"; then
        log_message "INFO" "Successfully added password for account: $account"
    else
        log_message "ERROR" "Failed to add password for account: $account"
        return 1
    fi
}

# Main script execution
main() {
    local account="$1"
    local password="$2"

    # Error handling with try/catch equivalent
    {
        add_generic_password "$account" "$password"
    } || {
        log_message "ERROR" "An error occurred while adding the password."
        exit 1
    }
}

# Check for correct number of arguments
if [[ $# -ne 2 ]]; then
    log_message "ERROR" "Usage: $0 <account> <password>"
    exit 1
fi

# Run the main function with provided arguments
main "$1" "$2"