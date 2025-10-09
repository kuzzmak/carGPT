#!/bin/bash

# Script to download and extract Tor Browser
# Usage: ./download_tor.sh <download_path>

set -e  # Exit on any error

# Check if path argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <download_path>"
    echo "Example: $0 /tmp/tor"
    exit 1
fi

DOWNLOAD_PATH="$1"

# Create download directory if it doesn't exist
mkdir -p "$DOWNLOAD_PATH"

get_latest_dl_url() { 
    version_url="https://dist.torproject.org/torbrowser/?C=M;O=D"
    version="$(curl -s "$version_url" | grep -m 1 -Po "(?<=>)\d+.\d+(.\d+)?(?=/)")"
    echo "https://www.torproject.org/dist/torbrowser/${version}/tor-browser-linux-x86_64-${version}.tar.xz" 
}

download_and_extract_tor() {
    local download_path="$1"
    local download_url
    local filename
    local filepath
    
    echo "Getting latest Tor Browser download URL..."
    download_url=$(get_latest_dl_url)
    filename=$(basename "$download_url")
    filepath="$download_path/$filename"
    
    echo "Download URL: $download_url"
    echo "Downloading to: $filepath"
    
    # Download Tor Browser
    if [ -f "$filepath" ]; then
        echo "File already exists: $filepath"
        echo "Exiting..."
        exit 0
    else
        echo "Downloading Tor Browser..."
        curl -L -o "$filepath" "$download_url"
        echo "Download completed: $filepath"
    fi
    
    # Extract Tor Browser
    echo "Extracting Tor Browser to: $download_path"
    tar -xf "$filepath" -C "$download_path"
    
    # Get the extracted directory name
    # extracted_dir=$(tar -tf "$filepath" | head -1 | cut -f1 -d"/")
    # extracted_path="$download_path/$extracted_dir"
    
    # echo "Tor Browser extracted to: $extracted_path"
    # echo "Tor executable location: $extracted_path/Browser/start-tor-browser"
    
    return 0
}

# Main execution
# echo "Starting Tor Browser download and extraction..."
# echo "Target directory: $DOWNLOAD_PATH"

download_and_extract_tor "$DOWNLOAD_PATH"

# echo "Tor Browser setup completed successfully!"
# echo "You can start Tor Browser by running:"
# echo "  $DOWNLOAD_PATH/tor-browser/Browser/start-tor-browser"