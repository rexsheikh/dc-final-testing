#!/usr/bin/env bash
set -euo pipefail

# Complete deployment script for Text-to-Anki service
# Deletes existing VMs, sets up base VM, creates REST tier and workers
# Then runs diagnostic scripts to verify deployment

PROJECT_ID="substantial-art-471117-v1"
ZONE="us-west1-b"
BASE_INSTANCE="flask-instance"
REST_INSTANCE="anki-rest-server"
WORKER_PREFIX="anki-worker"
NUM_WORKERS=2

log() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# Step 1: Delete existing service VMs (keep base VM)
log "Step 1: Cleaning up existing VMs"
echo "Deleting REST tier and workers..."
gcloud compute instances delete "$REST_INSTANCE" \
    --zone="$ZONE" \
    --quiet 2>/dev/null || echo "  $REST_INSTANCE not found, skipping"

for i in $(seq 1 $NUM_WORKERS); do
    WORKER_NAME="${WORKER_PREFIX}-${i}"
    gcloud compute instances delete "$WORKER_NAME" \
        --zone="$ZONE" \
        --quiet 2>/dev/null || echo "  $WORKER_NAME not found, skipping"
done

echo "Cleanup complete!"

# Step 2: Verify/setup base VM
log "Step 2: Setting up base VM"
BASE_EXISTS=$(gcloud compute instances list --filter="name=$BASE_INSTANCE" --format="value(name)" 2>/dev/null || echo "")

if [[ -z "$BASE_EXISTS" ]]; then
    echo "Base VM not found. Running setup_base_vm.sh..."
    cd setup
    bash setup_base_vm.sh
    cd ..
    echo "Waiting 60 seconds for base VM to fully initialize..."
    sleep 60
else
    echo "Base VM '$BASE_INSTANCE' already exists, skipping setup"
fi

# Step 3: Create REST tier
log "Step 3: Creating REST tier"
python3 setup/create_rest_tier.py
echo "Waiting 45 seconds for REST tier to start services..."
sleep 45

# Step 4: Create workers
log "Step 4: Creating worker tier"
python3 setup/create_workers.py
echo "Waiting 45 seconds for workers to start services..."
sleep 45

# Step 5: Run diagnostics
log "Step 5: Running diagnostic scripts"

echo ""
echo "--- Quick Verify ---"
bash debug/quick-verify.sh || echo "Quick verify had issues, continuing..."

echo ""
echo "--- REST Server Diagnostics ---"
bash debug/diagnose_rest.sh || echo "REST diagnostics had issues, continuing..."

echo ""
echo "--- Worker Queue Check ---"
bash debug/check_queue_process.sh || echo "Queue check had issues, continuing..."

echo ""
echo "--- Output Verification ---"
bash debug/verify_outputs.sh || echo "Output verification had issues (expected if no jobs submitted yet)"

# Step 6: Summary
log "Deployment Complete!"

REST_IP=$(gcloud compute instances describe "$REST_INSTANCE" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "Service Information:"
echo "  REST Server: $REST_INSTANCE"
echo "  External IP: $REST_IP"
echo "  Web UI: http://$REST_IP:5000"
echo ""
echo "Workers:"
for i in $(seq 1 $NUM_WORKERS); do
    WORKER_NAME="${WORKER_PREFIX}-${i}"
    WORKER_IP=$(gcloud compute instances describe "$WORKER_NAME" \
        --zone="$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    echo "  $WORKER_NAME: $WORKER_IP"
done

echo ""
echo "Next steps:"
echo "  1. Visit http://$REST_IP:5000 to test the web UI"
echo "  2. Upload a text file to create a job"
echo "  3. Check status and download the generated Anki deck"
echo ""
echo "To check logs:"
echo "  gcloud compute ssh $REST_INSTANCE --zone=$ZONE --command='sudo journalctl -u anki-rest.service -f'"
echo "  gcloud compute ssh anki-worker-1 --zone=$ZONE --command='sudo journalctl -u anki-worker.service -f'"
