#!/bin/bash
# Install Tailwind CSS standalone CLI (no Node.js required)
set -e

VERSION="v4.1.5"
PLATFORM="macos-arm64"
URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VERSION}/tailwindcss-${PLATFORM}"
DEST="$(dirname "$0")/../tools/bin/tailwindcss"

mkdir -p "$(dirname "$DEST")"

echo "Downloading Tailwind CSS ${VERSION} for ${PLATFORM}..."
curl -sL "$URL" -o "$DEST"
chmod +x "$DEST"

echo "Installed: $DEST"
"$DEST" --help | head -1
