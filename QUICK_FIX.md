# Quick Fix: Startup Script Failed Due to GitHub Authentication

## Problem

The startup script failed with:
```
fatal: could not read Username for 'https://github.com': No such device or address
```

This happens because automated startup scripts can't prompt for GitHub credentials.

## Solution Options

### Option 1: Make Repository Public (Fastest - Recommended for Testing)

1. Go to your repository settings:
   ```
   https://github.com/rexsheikh/dc-final-testing/settings
   ```

2. Scroll to "Danger Zone" → "Change repository visibility"

3. Click "Change visibility" → "Make public"

4. Recreate your VMs:
   ```bash
   # Delete existing instances
   gcloud compute instances delete anki-rest-server anki-worker-1 anki-worker-2 \
     --zone=us-west1-b --quiet
   
   # Recreate with updated startup scripts
   python3 create_rest_tier.py
   python3 create_workers.py
   ```

### Option 2: Manual Fix (Keep Private Repo)

Run the fix script which will SSH in and clone with your credentials:

```bash
chmod +x fix_rest_server.sh
./fix_rest_server.sh
```

When prompted, enter:
- Username: `rexsheikh`
- Password: `<your-personal-access-token>` (from https://github.com/settings/tokens)

### Option 3: Manual SSH Fix

```bash
# SSH into the server
gcloud compute ssh anki-rest-server --zone=us-west1-b

# Inside the VM:
cd /opt
sudo rm -rf anki-service  # Remove failed clone

# Clone with your credentials
sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service
# Enter username: rexsheikh
# Enter password: <your-personal-access-token>

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

### Option 4: Use Deploy Token in Startup Script (Production)

For production deployments, use a deploy key:

1. Create a deploy key:
   ```bash
   ssh-keygen -t ed25519 -C "deploy-key" -f ~/.ssh/github_deploy_key -N ""
   ```

2. Add public key to GitHub:
   - Go to: https://github.com/rexsheikh/dc-final-testing/settings/keys
   - Click "Add deploy key"
   - Paste contents of `~/.ssh/github_deploy_key.pub`
   - Check "Allow write access" if needed

3. Store private key in GCP Secret Manager:
   ```bash
   gcloud secrets create github-deploy-key --data-file=~/.ssh/github_deploy_key
   ```

4. Update startup script to use the deploy key (see create_rest_tier.py)

## Verify the Fix

After applying any solution:

```bash
# Get REST server IP
REST_IP=$(gcloud compute instances describe anki-rest-server \
  --zone=us-west1-b \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Test health endpoint
curl http://$REST_IP:5000/health

# Should return: {"status":"healthy","timestamp":"2025-..."}
```

## Repeat for Workers

If you manually fixed the REST server, repeat for workers:

```bash
# For each worker
for i in 1 2; do
  gcloud compute ssh anki-worker-$i --zone=us-west1-b << 'EOF'
cd /opt
sudo rm -rf anki-service
sudo git clone https://github.com/rexsheikh/dc-final-testing anki-service
cd anki-service
sudo pip3 install -r requirements.txt
nohup python3 worker.py &>/var/log/anki-worker.log &
EOF
done
```

## Prevention for Future Deployments

**For coursework/testing:** Make repo public

**For production:** Use one of these:
- Deploy keys (GitHub)
- Service account with Secret Manager (GCP)
- Cloud Source Repositories mirror (GCP)
