#!/bin/bash
set -euo pipefail

echo "Running Inkly build and install scripts"
bash ./build.sh 
bash ./install.sh
echo "Inkly build and install complete"

ink "Hello"

