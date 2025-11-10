#!/bin/bash
# Ink CLI Installer for HPC
# Wraps GitHub Copilot CLI under the "inkly" command
# Run this on your HPC cluster

set -e

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# Create tools directory
mkdir -p ~/tools/inkly
cd ~/tools/inkly

# Download and install Copilot CLI (renamed as inkly)
wget https://github.com/github/copilot-cli/releases/download/v0.0.353/copilot-linux-amd64 -O inkly
chmod +x ~/tools/inkly/inkly


# Ensure correct path setup
if ! grep -q 'export PATH="$HOME/tools/inkly:$PATH"' ~/.bashrc; then
  echo 'export PATH="$HOME/tools/inkly:$PATH"' >> ~/.bashrc
fi

source ~/.bashrc

echo "Installation complete."
inkly --version || echo "Inkly installed (copilot binary renamed)."
