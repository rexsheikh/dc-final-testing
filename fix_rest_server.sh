#!/usr/bin/env bash
set -euo pipefail

ZONE="us-west1-b"
INSTANCE="anki-rest-server"

echo "=== Fixing REST Server After Failed Startup ==="
echo ""
echo "This script will SSH into the server and manually clone the repo."
echo "You'll need to provide your GitHub Personal Access Token when prompted."
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

echo ""
echo "Connecting to $INSTANCE..."
echo ""

gcloud compute ssh $INSTANCE --zone=$ZONE << 'ENDSSH'
set -euxo pipefail

# Navigate to /opt
cd /opt

# Remove failed clone attempt if exists
sudo rm -rf anki-service

# Clone the repository
echo ""
echo "================================================"
echo "ENTER YOUR GITHUB CREDENTIALS:"
echo "  Username: rexsheikh"
echo "  Password: <your-personal-access-token>"
echo "================================================"
echo ""

sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service

# Change ownership
sudo chown -R $(whoami):$(whoami) anki-service

# Install dependencies
cd anki-service
sudo pip3 install -r requirements.txt

# Stop any existing Flask process
sudo pkill -f "python3 app.py" || true

# Start Flask
nohup python3 app.py &>/var/log/anki-rest.log &

# Wait and verify
sleep 3
if curl -s http://localhost:5000/health > /dev/null; then
    echo ""
    echo "✓ Flask is running successfully!"
    curl http://localhost:5000/health
else
    echo ""
    echo "✗ Flask might not be running. Check logs:"
    echo "  sudo tail -50 /var/log/anki-rest.log"
fi

ENDSSH

echo ""
echo "=== Done! ==="
echo ""
echo "Test the REST API:"
REST_IP=$(gcloud compute instances describe $INSTANCE --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "  curl http://$REST_IP:5000/health"
