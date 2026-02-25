#!/bin/sh
#
# This script is used to compile your program on CodeCrafters
#
# This runs before .codecrafters/run.sh
#
# Learn more: https://codecrafters.io/program-interface

set -e # Exit on failure

TARGET_DIR="/tmp/shell-target"

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R app "$TARGET_DIR/app"
