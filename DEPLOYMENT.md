# Deployment Guide - Text-to-Anki Service

This guide provides step-by-step Google Cloud commands for deploying and testing the service.

## Prerequisites

1. Google Cloud SDK installed (`gcloud` CLI)
2. Authenticated with your GCP account
3. Project created with billing enabled
4. **GitHub authentication configured** (see below)

**Note**: This project uses **lightweight Python-only NLP** with minimal dependencies (Flask, Redis). No TensorFlow, PyTorch, or other heavy ML frameworks are required. This enables fast deployment and low resource usage.

## Quick Local Test (Before Deployment)

Test the NLP pipeline locally to verify it works:

```bash
# Clone the repository
git clone https://github.com/rexsheikh/dc-final-testing
cd dc-final-testing

# Quick pipeline test
python3 -c "
from nlp import process_pipeline, DeckAssembler

text = '''Machine learning is a subset of artificial intelligence. Neural networks are 
computational models inspired by biological neurons. Deep learning uses multiple 
layers to extract features from data. Supervised learning requires labeled training 
data. Unsupervised learning finds patterns without labels.'''

results = process_pipeline(text, 'test.txt')
DeckAssembler.write_csv(results['cards'], 'test_output.csv')

print(f'Stats: {results[\"normalized\"][\"word_count\"]} words, {results[\"normalized\"][\"sentence_count\"]} sentences')
print(f'Generated {len(results[\"cards\"])} flashcards')
print(f'Top keyword: {results[\"keywords\"][0][0]} (score: {results[\"keywords\"][0][1]:.3f})')
"

# View output
cat test_output.csv
```

Expected output:
```
Stats: 44 words, 5 sentences
Generated 9 flashcards
Top keyword: learning (score: 0.156)
```

### GitHub Authentication Setup

GitHub no longer supports password authentication. Before proceeding, set up authentication:

**Quick Setup (Recommended for GCP Cloud Shell):**

```bash
# Method 1: Personal Access Token
# Create at: https://github.com/settings/tokens
# Scopes needed: repo (all)
git config --global credential.helper 'cache --timeout=7200'
# Use token as password when cloning

# Method 2: GitHub CLI (easiest)
gh auth login
# Follow browser authentication flow
```

**Detailed authentication guide:** See `SETUP_GUIDE.md` section "GitHub Authentication Methods"

## Quick Start (Automated Setup)

**NEW**: Use the automated setup script to configure everything:

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

For detailed setup instructions, see [`SETUP_GUIDE.md`](SETUP_GUIDE.md).

---

## Manual Setup (Alternative)

If you prefer manual control or the automated script fails, follow these steps:

### 1. Configure GCP Environment

```bash
# Set your project ID
export PROJECT_ID="substantial-art-471117-v1"
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

```bash
# Clone the repo to your local machine
cd ~/Documents/boulder-fall-2025/data-center-scale-computing

# Using Personal Access Token:
git clone https://github.com/rexsheikh/dc-final-testing
# Username: rexsheikh
# Password: <your-personal-access-token>

# OR using GitHub CLI:
gh repo clone rexsheikh/dc-final-testing

# OR using SSH (if configured):
git clone git@github.com:rexsheikh/dc-final-testing.git

cd dc-final-testing

# If repository doesn't exist yet, initialize:
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/rexsheikh/dc-final-testing
git push -u origin main
```

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

# Quick end-to-end test
cat > quick_test.txt << 'EOF'
Distributed systems enable horizontal scaling. Load balancing distributes requests across multiple servers. Caching reduces database load. Message queues decouple services. Microservices architecture promotes modularity.
EOF

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

Record your actual results in `PERFORMANCE.md` for the project report.

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
cat > test_lecture.txt << 'EOF'
Machine learning is a subset of artificial intelligence. Neural networks are 
computational models inspired by biological neurons. Deep learning uses multiple 
layers to extract features from data. Supervised learning requires labeled training 
data. Unsupervised learning finds patterns without labels. The gradient descent 
algorithm optimizes model parameters by minimizing loss functions.
EOF

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

# Expected: CSV with Front,Back columns containing flashcards
```

### Test 5: Multiple File Upload

```bash
# Create additional test files
cat > lecture2.txt << 'EOF'
Data structures organize information efficiently. Arrays provide constant-time 
indexed access. Linked lists enable dynamic memory allocation. Hash tables offer 
average constant-time lookups. Binary trees support ordered data operations. 
Graph algorithms solve connectivity problems.
EOF

cat > lecture3.txt << 'EOF'
Operating systems manage computer resources. Process scheduling allocates CPU time. 
Virtual memory extends physical RAM. File systems organize persistent storage. 
Device drivers interface with hardware. System calls provide kernel services.
EOF

# Upload multiple files
curl -F "files=@lecture2.txt" \
     -F "files=@lecture3.txt" \
     -F "user=testuser" \
     http://$REST_IP:5000/upload

# Lists all jobs for user
curl "http://$REST_IP:5000/jobs?user=testuser"
```

### Test 6: Load Testing

```bash
# Install Apache Bench (if not installed)
# macOS: already included
# Ubuntu: sudo apt-get install apache2-utils

# Create a simple upload script
cat > upload_test.sh << 'EOF'
#!/bin/bash
for i in {1..10}; do
  echo "Upload $i of 10"
  curl -s -F "files=@test_lecture.txt" http://$REST_IP:5000/upload
done
EOF

chmod +x upload_test.sh

# Run concurrent uploads
./upload_test.sh

# Monitor queue length in Redis
gcloud compute ssh anki-worker-1 --zone=$ZONE
redis-cli LLEN job_queue
# Shows number of pending jobs
exit
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

## Monitoring and Debugging

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

**Solutions:**

**Solution A: Wait for startup script to complete**
```bash
# Startup scripts take 2-5 minutes, especially on first run
# Monitor progress:
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo journalctl -u google-startup-scripts.service -f"
# Press Ctrl+C when you see "Finished startup scripts"
```

**Solution B: GitHub authentication failed (most common)**

If the startup script failed to clone the repository:

```bash
# SSH into the VM
gcloud compute ssh anki-rest-server --zone=$ZONE

# Check if repo exists
ls -la /opt/anki-service
# If missing, clone manually:

cd /opt
sudo rm -rf anki-service  # Remove if exists but empty
sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service
# Enter your GitHub username and Personal Access Token when prompted

cd anki-service
sudo pip3 install -r requirements.txt

# Start Flask
nohup python3 app.py &>/var/log/anki-rest.log &

# Verify it's running
sleep 2
curl http://localhost:5000/health

# Should return: {"status":"healthy",...}
exit
```

**Solution C: Dependencies missing**
```bash
gcloud compute ssh anki-rest-server --zone=$ZONE

cd /opt/anki-service
sudo pip3 install -r requirements.txt

# Restart Flask
sudo pkill -f "python3 app.py"
nohup python3 app.py &>/var/log/anki-rest.log &
exit
```

**Solution D: Check firewall tag is applied**
```bash
# Verify instance has allow-5000 tag
gcloud compute instances describe anki-rest-server --zone=$ZONE \
  --format="get(tags.items)"

# Should include: allow-5000
# If missing, add it:
gcloud compute instances add-tags anki-rest-server \
  --zone=$ZONE \
  --tags=allow-5000
```

### Issue: REST API not responding

```bash
# Check if Flask is running
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "ps aux | grep 'python.*app.py'"

# Restart Flask manually if needed
gcloud compute ssh anki-rest-server --zone=$ZONE
sudo pkill -f "python3 app.py"
cd /opt/anki-service
nohup python3 app.py &>/var/log/anki-rest.log &
exit
```

### Issue: Workers not processing jobs

```bash
# Check Redis connectivity
gcloud compute ssh anki-worker-1 --zone=$ZONE
redis-cli ping
# Should return PONG

# Check if worker process is running
ps aux | grep worker.py

# Restart worker if needed
sudo pkill -f "python3 worker.py"
cd /opt/anki-service
nohup python3 worker.py &>/var/log/anki-worker.log &
exit
```

### Issue: Startup script didn't run

```bash
# Check startup script status
gcloud compute ssh anki-rest-server --zone=$ZONE --command \
  "sudo journalctl -u google-startup-scripts.service -n 50"

# Manually run startup commands
gcloud compute ssh anki-rest-server --zone=$ZONE
cd /opt
sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service
cd anki-service
sudo pip3 install -r requirements.txt
nohup python3 app.py &>/var/log/anki-rest.log &
exit
```
