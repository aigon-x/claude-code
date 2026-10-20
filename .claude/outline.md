#!/bin/bash

# Improved script to securely add a generic password to the macOS keychain
# with enhanced error handling, logging, and input validation.

# Constants
KEYCHAIN_ITEM_NAME="Claude Code-credentials"
LOG_FILE="/var/log/claude_code.log"

# Function to log messages with timestamps
log() {
    local level="$1"
    shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $@" >> "$LOG_FILE"
}

# Function to add a generic password to the keychain
add_generic_password() {
    local account="$1"
    local password="$2"

    # Input validation
    if [[ -z "$account" || -z "$password" ]]; then
        log "ERROR" "Account and password must be provided."
        return 1
    fi

    # Attempt to add the password to the keychain
    if security add-generic-password -U -a "$account" -s "$KEYCHAIN_ITEM_NAME" -w "$password"; then
        log "INFO" "Successfully added password for account: $account"
    else
        log "ERROR" "Failed to add password for account: $account"
        return 1
    fi
}

# Main execution
# Example usage: add_generic_password "user@example.com" "securepassword123"
if [[ $# -ne 2 ]]; then
    log "ERROR" "Usage: $0 <account> <password>"
    exit 1
fi

add_generic_password "$1" "$2"