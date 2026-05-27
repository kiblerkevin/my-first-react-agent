#!/bin/bash
# Build Tailwind CSS output from input.css
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$DIR/tools/bin/tailwindcss" \
    -i "$DIR/server/static/css/input.css" \
    -o "$DIR/server/static/css/output.css" \
    --minify
echo "Built: server/static/css/output.css"
