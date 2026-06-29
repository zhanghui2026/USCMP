#!/bin/bash
# Download pre-built bootstrap SQLite database (members only, no FEC)
set -e

URL="https://github.com/zhanghui2026/USCMP/releases/download/v1.2-bootstrap/congress-bootstrap-2.0.db.gz"
TARGET="backend/data/congress.db"

mkdir -p "$(dirname "$TARGET")"

if [ -f "$TARGET" ] && [ -s "$TARGET" ]; then
    echo "Database already exists at $TARGET ($(du -h "$TARGET" | cut -f1)). Skipping download."
    echo "Remove it first if you want to re-download."
    exit 0
fi

echo "Downloading bootstrap database (444KB compressed)..."
if command -v curl &>/dev/null; then
    curl -fL "$URL" -o "${TARGET}.gz"
elif command -v wget &>/dev/null; then
    wget -q "$URL" -O "${TARGET}.gz"
else
    echo "ERROR: Neither curl nor wget found. Please install one of them."
    exit 1
fi

echo "Decompressing..."
gzip -d "${TARGET}.gz"

echo "Done. Database saved to $TARGET ($(du -h "$TARGET" | cut -f1))"
echo "Run 'docker compose up --build -d' to start."

echo "Database contains: 537 current US Congress members, 537 profiles, committee assignments"