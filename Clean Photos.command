#!/usr/bin/env bash
# Double-click this file in Finder to clean every photo in the "in" folder.
# Cleaned copies appear in "out". Originals are never touched.
cd "$(dirname "$0")" || exit 1
./clean.sh
echo
echo "Opening the 'out' folder..."
open ./out
echo
echo "You can close this window."
