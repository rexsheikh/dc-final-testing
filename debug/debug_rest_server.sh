#!/usr/bin/env bash
set -euo pipefail

ZONE="us-west1-b"
INSTANCE="anki-rest-server"

echo "=== Diagnosing REST Server ==="
echo ""

# Get IP
REST_IP=$(gcloud compute instances describe $INSTANCE \
  --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "REST Server IP: $REST_IP"
echo ""

# Check instance status
echo "1. Instance Status:"
gcloud compute instances describe $INSTANCE --zone=$ZONE \
  --format="table(name,status,tags.items)"
echo ""

# Check if startup script completed
echo "2. Startup Script Status:"
gcloud compute ssh $INSTANCE --zone=$ZONE --command \
  "sudo journalctl -u google-startup-scripts.service | tail -20"
echo ""

# Check if Flask process is running
echo "3. Flask Process Check:"
gcloud compute ssh $INSTANCE --zone=$ZONE --command \
  "ps aux | grep -E 'python3.*app.py|flask' | grep -v grep || echo 'Flask not running'"
echo ""

# Check application logs
echo "4. Application Logs (last 30 lines):"
gcloud compute ssh $INSTANCE --zone=$ZONE --command \
  "sudo tail -30 /var/log/anki-rest.log 2>/dev/null || echo 'Log file not found'"
echo ""

# Check if port 5000 is listening
echo "5. Port 5000 Status:"
gcloud compute ssh $INSTANCE --zone=$ZONE --command \
  "sudo netstat -tlnp | grep 5000 || echo 'Port 5000 not listening'"
echo ""

# Check firewall rule
echo "6. Firewall Rule Status:"
gcloud compute firewall-rules describe allow-5000 --format="table(name,allowed,targetTags)" 2>/dev/null || echo "Firewall rule not found"
echo ""

# Test from inside VM
echo "7. Internal Health Check (from VM):"
gcloud compute ssh $INSTANCE --zone=$ZONE --command \
  "curl -s http://localhost:5000/health || echo 'Internal health check failed'"
echo ""

echo "=== Common Issues & Solutions ==="
echo ""
echo "If Flask is not running:"
echo "  • Wait 2-3 more minutes for startup script to complete"
echo "  • Check startup logs: sudo journalctl -u google-startup-scripts.service"
echo ""
echo "If startup script failed:"
echo "  • SSH in: gcloud compute ssh $INSTANCE --zone=$ZONE"
echo "  • Run manually:"
echo "    cd /opt"
echo "    sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service"
echo "    cd anki-service"
echo "    sudo pip3 install -r requirements.txt"
echo "    nohup python3 app.py &>/var/log/anki-rest.log &"
echo ""
echo "If port 5000 not listening:"
echo "  • Check app.py is using correct host: app.run(host='0.0.0.0', port=5000)"
echo "  • Check for errors in: sudo tail -f /var/log/anki-rest.log"
