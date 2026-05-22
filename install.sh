#!/bin/bash
# Install DJI Video Recovery Skill for Claude Code
# Usage: ./install.sh

set -e

SKILL_NAME="dji-video-recovery"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== DJI Video Recovery Skill Installer ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.8+"
    exit 1
fi
echo "  python3: $(python3 --version)"

if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: ffmpeg not found. Install with: brew install ffmpeg"
else
    echo "  ffmpeg: $(ffmpeg -version | head -1)"
fi

# Install skill for Claude Code (AgentSkills standard)
SKILL_DIR="$HOME/.claude/skills/${SKILL_NAME}"
mkdir -p "$SKILL_DIR/scripts"

cp "$SCRIPT_DIR/skills/${SKILL_NAME}/SKILL.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skills/${SKILL_NAME}/scripts/"*.py "$SKILL_DIR/scripts/"
chmod +x "$SKILL_DIR/scripts/"*.py
echo ""
echo "Skill installed to: $SKILL_DIR/SKILL.md"

# Also install legacy format for backward compatibility
LEGACY_DIR="$HOME/.claude/skills"
cp "$SCRIPT_DIR/skill.md" "$LEGACY_DIR/${SKILL_NAME}.md"

# Copy scripts to a permanent location
BIN_DIR="$HOME/.claude/scripts"
mkdir -p "$BIN_DIR"
cp "$SCRIPT_DIR/scripts/"*.py "$BIN_DIR/"
chmod +x "$BIN_DIR/"*.py
echo "Scripts installed to: $BIN_DIR/"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To use: Tell Claude Code about your DJI SD card recovery needs."
echo "The skill will be automatically triggered."
echo ""
echo "Manual usage:"
echo "  sudo python3 $BIN_DIR/fat_chain_recover.py /dev/rdisk4s1 ./recovered/"
echo "  python3 $BIN_DIR/verify_recovery.py ./recovered/"
