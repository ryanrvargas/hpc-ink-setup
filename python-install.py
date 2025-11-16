#python version of install.sh

import os
import subprocess
import shutil
from pathlib import Path

HOME = Path.home()
NVM_DIR = HOME / ".nvm"
NPM_GLOBAL = HOME / ".npm-global"
COPILOT_DIR = HOME / ".copilot"
NPM_DIR = HOME / ".npm"

def run_command(cmd):
    return subprocess.run(cmd, shell=True, check=True, text=True)
    
