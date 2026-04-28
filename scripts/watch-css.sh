#!/bin/bash
# Watch templates and rebuild Tailwind CSS on changes
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$DIR/tools/bin/tailwindcss" \
    -i "$DIR/server/static/css/input.css" \
    -o "$DIR/server/static/css/output.css" \
    --watch
