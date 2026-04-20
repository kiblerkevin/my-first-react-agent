#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== Chicago Sports Recap — Service Installer ==="
echo ""

mkdir -p "$LAUNCH_AGENTS"

# Install Docker service
echo "Installing Docker Compose service..."
cp "$SCRIPT_DIR/com.chicagosportsrecap.docker.plist" "$LAUNCH_AGENTS/"
launchctl load "$LAUNCH_AGENTS/com.chicagosportsrecap.docker.plist" 2>/dev/null || true
echo "  ✅ com.chicagosportsrecap.docker installed"

# Install Approval Server service
echo "Installing Approval Server service..."
cp "$SCRIPT_DIR/com.chicagosportsrecap.approval-server.plist" "$LAUNCH_AGENTS/"
launchctl load "$LAUNCH_AGENTS/com.chicagosportsrecap.approval-server.plist" 2>/dev/null || true
echo "  ✅ com.chicagosportsrecap.approval-server installed"

# Install Cloudflare Tunnel service (conditional)
if grep -q "PLACEHOLDER_TUNNEL_NAME" "$SCRIPT_DIR/com.chicagosportsrecap.cloudflare-tunnel.plist"; then
    echo "Skipping Cloudflare Tunnel — placeholder values detected."
    echo "  ⚠️  Update services/com.chicagosportsrecap.cloudflare-tunnel.plist with your tunnel name and cloudflared path, then re-run this script."
else
    echo "Installing Cloudflare Tunnel service..."
    cp "$SCRIPT_DIR/com.chicagosportsrecap.cloudflare-tunnel.plist" "$LAUNCH_AGENTS/"
    launchctl load "$LAUNCH_AGENTS/com.chicagosportsrecap.cloudflare-tunnel.plist" 2>/dev/null || true
    echo "  ✅ com.chicagosportsrecap.cloudflare-tunnel installed"
fi

echo ""
echo "=== Verifying Services ==="
echo ""

for label in com.chicagosportsrecap.docker com.chicagosportsrecap.approval-server com.chicagosportsrecap.cloudflare-tunnel; do
    status=$(launchctl list | grep "$label" || echo "not loaded")
    if echo "$status" | grep -q "$label"; then
        echo "  ✅ $label — loaded"
    else
        echo "  ⏭️  $label — not loaded"
    fi
done

echo ""
echo "Services will start automatically on next login."
echo "To start immediately: launchctl start <label>"
echo "To check status: launchctl list | grep chicagosportsrecap"
