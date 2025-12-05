# Deployment Guide - Text-to-Anki Service

This guide provides step-by-step Google Cloud commands for deploying and testing the service.

## Prerequisites

1. Google Cloud SDK installed (`gcloud` CLI) or access to google cloud console
2. Authenticated with your GCP account
4. **GitHub authentication configured** (see below)

**Note**: This project uses **lightweight Python-only NLP** with minimal dependencies (Flask, Redis). No TensorFlow, PyTorch, or other heavy ML frameworks are required. This enables fast deployment and low resource usage.

## Quick Local Test (Before Deployment)

Test the NLP pipeline locally to verify it works:

```bash
# Clone the repository
git clone https://github.com/rexsheikh/dc-final-testing
cd dc-final-testing
python3 nlp.py sample-data/short-samples/mixed-words.txt --test.csv

Expected output: the more difficult words from mixed-words.text are extracted effectively and outputted into csv. 


```bash
# 1. Run automated setup (creates base VM, installs dependencies, creates snapshot)
chmod +x setup_base_vm.sh verify_setup.sh
./setup_base_vm.sh

# 2. Verify setup
./verify_setup.sh

# 3. Deploy services
python3 create_rest_tier.py
python3 create_workers.py
```
---

## Manual Setup

If you prefer manual control or the automated script fails, follow these steps:

### 1. Configure GCP Environment

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Set default zone
export ZONE="us-west1-b"
gcloud config set compute/zone $ZONE

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### 2. Create Base VM (Source Instance)

This VM will be snapshotted and cloned for REST/worker tiers.

```bash
# Create base instance with Ubuntu 22.04
gcloud compute instances create flask-instance \
  --zone=$ZONE \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=10GB \
  --tags=allow-5000

# SSH into the instance
gcloud compute ssh flask-instance --zone=$ZONE
```

### 3. Install Dependencies on Base VM

Run these commands **inside the flask-instance VM**:

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and tools
sudo apt-get install -y python3-pip python3-venv git redis-server

# Install Redis and start service
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify Redis is running
redis-cli ping
# Should output: PONG

# Create application directory
sudo mkdir -p /opt/anki-service
sudo chown $(whoami):$(whoami) /opt/anki-service

# Exit the VM
exit
```

### 4. Create Firewall Rule

```bash
# Create firewall rule for Flask port 5000
gcloud compute firewall-rules create allow-5000 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:5000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=allow-5000

# Verify firewall rule
gcloud compute firewall-rules describe allow-5000
```

### 5. Create Snapshot of Base VM

```bash
# Get boot disk name
BOOT_DISK=$(gcloud compute instances describe flask-instance \
  --zone=$ZONE \
  --format='get(disks[0].source.basename())')

echo "Boot disk: $BOOT_DISK"

# Create snapshot
gcloud compute disks snapshot $BOOT_DISK \
  --zone=$ZONE \
  --snapshot-names=base-snapshot-flask-instance

# Verify snapshot
gcloud compute snapshots describe base-snapshot-flask-instance
```

## Deploy the Service

### 6. Clone Repository Locally

### 7. Create REST Tier VM

```bash
# Run the REST tier creation script
cd final-project
python3 create_rest_tier.py

# This will:
# - Create snapshot if not exists
# - Launch anki-rest-server VM
# - Install dependencies via startup script
# - Start Flask API on port 5000

# Get the REST server IP
REST_IP=$(gcloud compute instances describe anki-rest-server \
  --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "REST API available at: http://$REST_IP:5000"
```

### 8. Create Worker VMs

```bash
# Run the worker creation script
python3 create_workers.py

# This will create 2 worker VMs (anki-worker-1, anki-worker-2)

# Get worker IPs
gcloud compute instances list --filter="name~'anki-worker-'" \
  --format="table(name,networkInterfaces[0].accessConfigs[0].natIP:label=EXTERNAL_IP)"
```

### 9. Verify Deployment

```bash
# Wait 2-3 minutes for startup scripts to complete

# Get REST server IP
export REST_IP=$(gcloud compute instances describe anki-rest-server \
  --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Check REST server health
curl http://$REST_IP:5000/health

# Expected output: {"status":"healthy","timestamp":"2025-..."}

# Upload and process
curl -F "files=@quick_test.txt" -F "user=test" http://$REST_IP:5000/upload
# Copy the job_id from response

# Check status (wait ~5 seconds)
sleep 5
curl http://$REST_IP:5000/status/<job_id>

# Download deck
curl http://$REST_IP:5000/download/<job_id> -o quick_deck.csv
cat quick_deck.csv
```

## Performance Benchmarks

Expected performance metrics with lightweight implementation:

- **VM Creation Time**: 15-25 seconds per instance (from snapshot)
- **Startup Time**: 30-60 seconds (no model downloads required)
- **Job Processing Time**: 2-5 seconds per text file (pure Python processing)
- **API Latency**: <100ms for status checks, <1s for uploads
- **Throughput**: 2 workers can process ~20-30 jobs/minute
- **Memory Usage**: ~100MB per worker process (no ML models in memory)
- **Disk Usage**: <500MB per VM (no model files)

**Comparison to ML-heavy approach:**
- Traditional NLP: 5-10 minute startup (model loading), 2GB+ RAM, 10-30 seconds per file
- This implementation: 30-60 second startup, 100MB RAM, 2-5 seconds per file

These fast metrics are achievable because we use lightweight, pure-Python NLP instead of heavy ML frameworks.

## Testing Regime

### Test 1: Basic Health Check

```bash
# Set REST IP if not already set
export ZONE="us-west1-b"
export REST_IP=$(gcloud compute instances describe anki-rest-server \
  --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Test REST API health endpoint
curl http://$REST_IP:5000/health

# Expected: {"status": "healthy", "timestamp": "2025-..."}
```

### Test 2: File Upload

```bash
# Create a test text file

# Upload the file
curl -F "files=@test_lecture.txt" \
     -F "user=testuser" \
     http://$REST_IP:5000/upload

# Expected output: {"jobs":[{"job_id":"<uuid>","filename":"test_lecture.txt"}]}
# Save the job_id for next steps
```

### Test 3: Job Status Tracking

```bash
# Replace <job_id> with the UUID from upload response
JOB_ID="<paste-job-id-here>"

# Check job status (initially: queued)
curl http://$REST_IP:5000/status/$JOB_ID

# Wait 10-20 seconds for processing
sleep 20

# Check again (should be: completed)
curl http://$REST_IP:5000/status/$JOB_ID
```

### Test 4: Download Deck

```bash
# Download the generated Anki deck
curl http://$REST_IP:5000/download/$JOB_ID -o deck.csv

# View the deck contents
cat deck.csv

# Expected: CSV with Front,Back columns ready to upload to Anki
```

### Test 5: Multiple File Upload

```bash
# Create additional test files
# Upload multiple files
curl -F "files=@lecture2.txt" \
     -F "files=@lecture3.txt" \
     -F "user=testuser" \
     http://$REST_IP:5000/upload

# Lists all jobs for user
curl "http://$REST_IP:5000/jobs?user=testuser"
```


### Test 7: Worker Scaling Test

```bash
# Check current worker status
gcloud compute instances list --filter="name~'anki-worker-'"

# Create additional workers if needed
# Edit create_workers.py: set WORKER_COUNT = 4
python3 create_workers.py

# Verify all workers are processing
gcloud compute ssh anki-worker-1 --zone=$ZONE
redis-cli LLEN job_queue  # Should decrease as workers process
exit
```
### View Application Logs

```bash
# REST server logs
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo tail -100 /var/log/anki-rest.log"

# Worker logs
gcloud compute ssh anki-worker-1 --zone=$ZONE --command \
  "sudo tail -100 /var/log/anki-worker.log"

# Startup script logs
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo journalctl -u google-startup-scripts.service"
```

### Check Redis Queue

```bash
# Connect to worker and check Redis
gcloud compute ssh anki-worker-1 --zone=$ZONE

# Inside VM:
redis-cli
> LLEN job_queue        # Queue length
> LRANGE job_queue 0 -1 # View all job IDs
> KEYS job:*            # List all job metadata keys
> GET job:<job-id>      # View specific job data
> QUIT

exit
```

### Check Resource Usage

```bash
# CPU and memory on REST server
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "top -bn1 | head -20"

# Disk usage
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "df -h"

# Active processes
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "ps aux | grep python"
```

## Cleanup

### Stop Services (Keep VMs)

```bash
# Stop VMs without deleting
gcloud compute instances stop anki-rest-server --zone=$ZONE
gcloud compute instances stop anki-worker-1 --zone=$ZONE
gcloud compute instances stop anki-worker-2 --zone=$ZONE
```

### Full Cleanup (Delete Everything)

```bash
# Delete all worker VMs
gcloud compute instances delete anki-worker-1 anki-worker-2 \
  --zone=$ZONE --quiet

# Delete REST server
gcloud compute instances delete anki-rest-server --zone=$ZONE --quiet

# Delete base instance
gcloud compute instances delete flask-instance --zone=$ZONE --quiet

# Delete snapshot
gcloud compute snapshots delete base-snapshot-flask-instance --quiet

# Delete firewall rule
gcloud compute firewall-rules delete allow-5000 --quiet

# Clean up local files
rm -f test_lecture.txt lecture2.txt lecture3.txt deck.csv upload_test.sh
```

## Troubleshooting

### Issue: "Failed to connect to port 5000" after VM creation

**Symptoms:** 
- Ping works: `ping $REST_IP` succeeds
- Curl fails: `curl http://$REST_IP:5000/health` connection refused

**Diagnosis:**

```bash
# Quick diagnostic script
chmod +x debug_rest_server.sh
./debug_rest_server.sh

# Or manual checks:
# 1. Check if startup script is still running (wait 2-3 minutes)
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo journalctl -u google-startup-scripts.service | tail -20"

# 2. Check if Flask process exists
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "ps aux | grep app.py"

# 3. Check application logs
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo tail -50 /var/log/anki-rest.log"
```

