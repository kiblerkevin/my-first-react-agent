#!/bin/bash
set -e

LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== Chicago Sports Recap — Service Uninstaller ==="
echo ""

for label in com.chicagosportsrecap.approval-server com.chicagosportsrecap.docker com.chicagosportsrecap.cloudflare-tunnel; do
    plist="$LAUNCH_AGENTS/$label.plist"
    if [ -f "$plist" ]; then
        echo "Unloading $label..."
        launchctl unload "$plist" 2>/dev/null || true
        rm "$plist"
        echo "  ✅ $label removed"
    else
        echo "  ⏭️  $label — not installed"
    fi
done

echo ""
echo "All services uninstalled."
echo "Docker containers are still running — stop with: docker compose down"
