#!/bin/bash
# Ink CLI Installer for HPC
# Wraps GitHub Copilot CLI under the "inkly" command
# Run this on your HPC cluster

set -e

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# Create tools directory
mkdir -p ~/tools
cd ~/tools

# Download and install Copilot CLI (renamed as inkly)
wget https://github.com/github/copilot-cli/releases/download/v0.0.353/copilot-linux-amd64 -O inkly
chmod +x inkly
echo 'export PATH="$HOME/tools:$PATH"' >> ~/.bashrc
source ~/.bashrc

echo "Installation complete."
inkly --version || echo "Inkly installed (copilot binary renamed)."
