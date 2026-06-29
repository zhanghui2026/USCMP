#!/bin/bash
# Download congress-legislators vendor data from unitedstates/congress-legislators
set -e

REPO_URL="https://github.com/unitedstates/congress-legislators.git"
COMMIT_SHA="dfa9622263dd4c8d08636926e498f1845704d7eb"
TARGET_DIR="backend/data/external/congress-legislators/$COMMIT_SHA"

if [ -f "$TARGET_DIR/legislators-current.yaml" ]; then
    echo "Congress-legislators data already exists at $TARGET_DIR"
    exit 0
fi

mkdir -p "data/external/congress-legislators"

echo "Cloning unitedstates/congress-legislators (commit: $COMMIT_SHA)..."
TMP_DIR=$(mktemp -d)
git clone --depth 1 "$REPO_URL" "$TMP_DIR"
cd "$TMP_DIR"
git fetch --depth 1 origin "$COMMIT_SHA"
git checkout "$COMMIT_SHA"
cd - > /dev/null

mkdir -p "$TARGET_DIR"
mv "$TMP_DIR"/*.yaml "$TARGET_DIR/" 2>/dev/null || true
rm -rf "$TMP_DIR"

echo "Done. Vendor data at: $TARGET_DIR/"