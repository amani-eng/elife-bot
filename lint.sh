#!/bin/bash
set -e
source venv/bin/activate

# intentionally only the script files in the root folder
pylint -E *.py
