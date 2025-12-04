# Setup Guide - PDF-to-Anki Text Service

This guide walks you through the initial setup of the PDF-to-Anki service infrastructure.

## Quick Start

```bash
# 1. Make scripts executable
chmod +x setup_base_vm.sh verify_setup.sh

# 2. Run the setup script
./setup_base_vm.sh

# 3. Verify everything is configured correctly
./verify_setup.sh
```

## Prerequisites

Before running the setup scripts, ensure you have:

1. **Google Cloud SDK (gcloud CLI)** installed
   ```bash
   # Check if installed
   gcloud --version
   
   # If not installed, visit:
   # https://cloud.google.com/sdk/docs/install
   ```

2. **Authenticated with GCP**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Python 3.8+** installed locally
   ```bash
   python3 --version
   ```

4. **Git** installed
   ```bash
   git --version
   ```

5. **GitHub Authentication** (choose one method below)

### GitHub Authentication Methods

GitHub no longer supports password authentication for Git operations. Choose one of these methods:

#### Method 1: Personal Access Token (PAT) - Recommended for Cloud Shell

```bash
# 1. Create a Personal Access Token on GitHub:
#    - Go to: https://github.com/settings/tokens
#    - Click "Generate new token" → "Generate new token (classic)"
#    - Name: "GCP Cloud Shell Access"
#    - Expiration: 90 days (or as needed)
#    - Select scopes: ✓ repo (all)
#    - Click "Generate token"
#    - COPY THE TOKEN (you won't see it again!)

# 2. Clone using the token as password:
git clone https://github.com/rexsheikh/dc-final-testing
# Username: rexsheikh
# Password: <paste your token>

# 3. Cache credentials to avoid re-entering:
git config --global credential.helper 'cache --timeout=7200'  # 2 hours
```

#### Method 2: SSH Keys - Best for Long-term Use

```bash
# 1. Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter for default location
# Optionally set a passphrase

# 2. Copy the public key
cat ~/.ssh/id_ed25519.pub

# 3. Add to GitHub:
#    - Go to: https://github.com/settings/keys
#    - Click "New SSH key"
#    - Title: "GCP Cloud Shell"
#    - Paste the public key
#    - Click "Add SSH key"

# 4. Test connection
ssh -T git@github.com
# Should see: "Hi rexsheikh! You've successfully authenticated..."

# 5. Clone using SSH URL
git clone git@github.com:rexsheikh/dc-final-testing.git
```

#### Method 3: GitHub CLI - Easiest for Cloud Shell

```bash
# 1. Install GitHub CLI (if not already installed)
# On Cloud Shell:
type -p curl >/dev/null || (sudo apt update && sudo apt install curl -y)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y

# 2. Authenticate
gh auth login
# Choose: GitHub.com
# Choose: HTTPS
# Choose: Login with a web browser
# Follow the prompts

# 3. Clone repository
gh repo clone rexsheikh/dc-final-testing
```

#### Method 4: Make Repository Public (Quick Test)

If this is just for testing/coursework:

```bash
# 1. On GitHub, go to your repository settings:
#    https://github.com/rexsheikh/dc-final-testing/settings

# 2. Scroll to "Danger Zone" → "Change repository visibility"

# 3. Click "Change visibility" → "Make public"

# 4. Now clone without authentication:
git clone https://github.com/rexsheikh/dc-final-testing.git
```

### Recommended Setup for GCP Cloud Shell

If you're working in GCP Cloud Shell, use this quick setup:

```bash
# Option A: Use GitHub CLI (easiest)
gh auth login
gh repo clone rexsheikh/dc-final-testing

# Option B: Use Personal Access Token
# Create token at: https://github.com/settings/tokens
git clone https://github.com/rexsheikh/dc-final-testing
# Enter token when prompted for password
git config --global credential.helper 'cache --timeout=7200'
```

## Detailed Setup Steps

### Step 1: Initial Configuration

The `setup_base_vm.sh` script automates the following:

1. **GCP Environment Configuration**
   - Sets project ID to `substantial-art-471117-v1`
   - Sets default zone to `us-west1-b`
   - Enables required APIs (Compute, Redis, Storage)

2. **Firewall Rule Creation**
   - Creates `allow-5000` rule for Flask API access
   - Allows TCP traffic on port 5000 from anywhere

3. **Base VM Creation**
   - Creates `flask-instance` VM with Ubuntu 22.04
   - Machine type: `e2-medium` (2 vCPU, 4GB RAM)
   - 10GB boot disk

4. **Dependency Installation**
   - Python 3, pip, virtualenv
   - Redis server (with auto-start)
   - Git and build tools

5. **Snapshot Creation**
   - Creates `base-snapshot-flask-instance` for cloning
   - Used to rapidly deploy REST and worker VMs

### Step 2: Run Setup Script

```bash
cd final-project
./setup_base_vm.sh
```

**What to expect:**
- Script takes 5-10 minutes to complete
- Progress is logged with colored output
- Each step shows success/failure status
- Creates base VM and snapshot

**Sample output:**
```
======================================
PDF-to-Anki Service - Base VM Setup
======================================

ℹ Project: substantial-art-471117-v1
ℹ Zone: us-west1-b
ℹ Instance: flask-instance

[Step 1/8] Checking prerequisites
✓ gcloud CLI found
✓ python3 found

[Step 2/8] Configuring GCP environment
ℹ Setting project to substantial-art-471117-v1...
✓ Project configured
...
```

### Step 3: Verify Setup

After setup completes, verify everything is configured:

```bash
./verify_setup.sh
```

**Checks performed:**
- ✓ gcloud CLI installation
- ✓ GCP project configuration
- ✓ Firewall rule exists
- ✓ Base instance running
- ✓ Snapshot created
- ✓ Python installed on VM
- ✓ Redis server running
- ✓ Git installed

**Expected output:**
```
======================================
PDF-to-Anki Setup Verification
======================================

[CHECK] Checking gcloud CLI installation
  ✓ PASS - gcloud CLI installed (version: 458.0.1)

[CHECK] Checking GCP project configuration
  ✓ PASS - Project configured: substantial-art-471117-v1
...

======================================
Verification Summary
======================================
Passed: 8
Failed: 0
Skipped: 0

✓ All checks passed!
You're ready to deploy the service.
```

## Troubleshooting

### Issue: "gcloud: command not found"

**Solution:**
```bash
# Install Google Cloud SDK
# macOS (with Homebrew):
brew install google-cloud-sdk

# Linux:
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

### Issue: "Project not found or permission denied"

**Solution:**
```bash
# Re-authenticate
gcloud auth login

# List available projects
gcloud projects list

# Set correct project
gcloud config set project YOUR_PROJECT_ID
```

### Issue: Setup script fails at VM creation

**Solution:**
```bash
# Check quota limits
gcloud compute project-info describe --project=substantial-art-471117-v1

# Try a different zone
export ZONE="us-central1-a"
./setup_base_vm.sh
```

### Issue: Cannot SSH into VM

**Solution:**
```bash
# Wait 30 seconds after VM creation
sleep 30

# Try SSH with verbose output
gcloud compute ssh flask-instance --zone=us-west1-b --ssh-flag="-v"

# Check firewall rules
gcloud compute firewall-rules list
```

### Issue: Redis not starting

**Solution:**
```bash
# SSH into VM
gcloud compute ssh flask-instance --zone=us-west1-b

# Check Redis status
sudo systemctl status redis-server

# Restart Redis
sudo systemctl restart redis-server

# View logs
sudo journalctl -u redis-server -n 50
```

### Issue: "Authentication failed" when cloning repository

**Cause:** GitHub no longer accepts password authentication.

**Solution:** Use one of the authentication methods above. For Cloud Shell, Personal Access Token or GitHub CLI are recommended.

```bash
# Quick fix with Personal Access Token:
# 1. Get token from: https://github.com/settings/tokens
# 2. Clone and use token as password:
git clone https://github.com/rexsheikh/dc-final-testing
# Username: rexsheikh
# Password: ghp_xxxxxxxxxxxxxxxxxxxx (your token)
```

### Issue: "Permission denied (publickey)" with SSH

**Solution:**
```bash
# Verify SSH key is added to ssh-agent
ssh-add -l

# If empty, add your key:
ssh-add ~/.ssh/id_ed25519

# Test GitHub connection
ssh -T git@github.com
```

## Manual Setup (Alternative)

If the automated script fails, you can set up manually:

### 1. Configure GCP

```bash
export PROJECT_ID="substantial-art-471117-v1"
export ZONE="us-west1-b"

gcloud config set project $PROJECT_ID
gcloud config set compute/zone $ZONE

gcloud services enable compute.googleapis.com
gcloud services enable redis.googleapis.com
```

### 2. Create Firewall Rule

```bash
gcloud compute firewall-rules create allow-5000 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:5000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=allow-5000
```

### 3. Create Base VM

```bash
gcloud compute instances create flask-instance \
  --zone=$ZONE \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=10GB \
  --tags=allow-5000
```

### 4. Install Dependencies

```bash
# SSH into VM
gcloud compute ssh flask-instance --zone=$ZONE

# Inside VM - run these commands:
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y python3-pip python3-venv git redis-server

sudo systemctl enable redis-server
sudo systemctl start redis-server

redis-cli ping  # Should return PONG

sudo mkdir -p /opt/anki-service
sudo chown $(whoami):$(whoami) /opt/anki-service

exit
```

### 5. Create Snapshot

```bash
# Get boot disk name
BOOT_DISK=$(gcloud compute instances describe flask-instance \
  --zone=$ZONE \
  --format='get(disks[0].source.basename())')

# Create snapshot
gcloud compute disks snapshot $BOOT_DISK \
  --zone=$ZONE \
  --snapshot-names=base-snapshot-flask-instance
```

## Next Steps

After setup is complete and verified:

1. **Deploy REST Tier**
   ```bash
   python3 create_rest_tier.py
   ```

2. **Deploy Worker Tier**
   ```bash
   python3 create_workers.py
   ```

3. **Test the Service**
   ```bash
   # Get REST server IP
   REST_IP=$(gcloud compute instances describe anki-rest-server \
     --zone=us-west1-b \
     --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
   
   # Test health endpoint
   curl http://$REST_IP:5000/health
   ```

4. **Follow Testing Guide**
   - See `DEPLOYMENT.md` for comprehensive testing procedures
   - Test file uploads, job processing, and deck generation

## Cleanup

To remove all resources created by setup:

```bash
# Delete base instance
gcloud compute instances delete flask-instance --zone=us-west1-b --quiet

# Delete snapshot
gcloud compute snapshots delete base-snapshot-flask-instance --quiet

# Delete firewall rule
gcloud compute firewall-rules delete allow-5000 --quiet
```

## Additional Resources

- Full deployment guide: `DEPLOYMENT.md`
- Project architecture: `README.md`
- Course outline: `../outline.tex`

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review logs: `gcloud compute ssh flask-instance --command "sudo journalctl -xe"`
3. Verify GCP quotas and permissions
