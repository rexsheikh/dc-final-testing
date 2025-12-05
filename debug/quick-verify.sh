#!/usr/bin/env bash

ZONE="us-west1-b"

echo "=== Quick Verification ==="
echo ""

echo "1. REST Server Status:"
gcloud compute instances describe anki-rest-server --zone=$ZONE \
  --format="value(status)" 2>/dev/null || echo "NOT FOUND"

echo ""
echo "2. REST Server IP:"
gcloud compute instances describe anki-rest-server --zone=$ZONE \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null

echo ""
echo "3. Workers Status:"
gcloud compute instances list --filter="name~'anki-worker-'" \
  --format="table(name,status,networkInterfaces[0].accessConfigs[0].natIP)"

echo ""
echo "4. Testing REST API Health:"
REST_IP=$(gcloud compute instances describe anki-rest-server --zone=$ZONE \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null)

if [ -n "$REST_IP" ]; then
    echo "Trying http://$REST_IP:5000/health"
    curl -s --connect-timeout 5 http://$REST_IP:5000/health || echo "FAILED - Flask might still be starting"
else
    echo "No REST server IP found"
fi

echo ""
echo "=== Summary ==="
echo "If REST server shows RUNNING and health check succeeds, you're ready to test!"