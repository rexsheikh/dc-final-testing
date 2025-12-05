# Systemd Service Management Guide

This guide covers managing the Anki service components via systemd after deploying with `create_rest_tier.py` and `create_workers.py`.

## Services Overview

After deployment, the following systemd services are created:

- **REST Tier**: `anki-rest.service` (on `anki-rest-server`)
- **Worker Tier**: `anki-worker.service` (on each `anki-worker-N` VM)

## Common Commands

### Check Service Status

```bash
# On REST server
gcloud compute ssh anki-rest-server --zone=us-west1-b --command "systemctl status anki-rest"

# On worker
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "systemctl status anki-worker"
```

### View Live Logs

```bash
# REST server logs
gcloud compute ssh anki-rest-server --zone=us-west1-b --command "journalctl -u anki-rest -f"

# Worker logs
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "journalctl -u anki-worker -f"
```

### Restart Services

```bash
# Restart REST API
gcloud compute ssh anki-rest-server --zone=us-west1-b --command "sudo systemctl restart anki-rest"

# Restart worker
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "sudo systemctl restart anki-worker"
```

### Stop/Start Services

```bash
# Stop service
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "sudo systemctl stop anki-worker"

# Start service
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "sudo systemctl start anki-worker"
```

### View Recent Logs

```bash
# Last 100 lines
gcloud compute ssh anki-rest-server --zone=us-west1-b --command "journalctl -u anki-rest -n 100"

# Logs from last hour
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "journalctl -u anki-worker --since '1 hour ago'"
```

## Systemd Service Features

### Auto-Restart

Services automatically restart if they crash:
- **Restart Policy**: `always`
- **Restart Delay**: 10 seconds
- Check restart count: `systemctl status anki-worker | grep Restarts`

### Environment Variables

Environment variables are configured in the service file:

**REST Server** (`/etc/systemd/system/anki-rest.service`):
```ini
Environment="SHARED_STORAGE_ROOT=/mnt/shared"
Environment="SHARED_UPLOAD_FOLDER=/mnt/shared/uploads"
Environment="SHARED_OUTPUT_FOLDER=/mnt/shared/outputs"
```

**Workers** (`/etc/systemd/system/anki-worker.service`):
```ini
Environment="REDIS_HOST=<rest-internal-ip>"
Environment="SHARED_STORAGE_ROOT=/mnt/shared"
Environment="SHARED_UPLOAD_FOLDER=/mnt/shared/uploads"
Environment="SHARED_OUTPUT_FOLDER=/mnt/shared/outputs"
```

### Log Files

Logs are written to both:
1. **Systemd journal**: `journalctl -u anki-worker`
2. **Traditional log files**: `/var/log/anki-worker.log` or `/var/log/anki-rest.log`

## Troubleshooting

### Service Won't Start

```bash
# Check detailed status
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "systemctl status anki-worker -l"

# View service file
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "cat /etc/systemd/system/anki-worker.service"

# Test manually
gcloud compute ssh anki-worker-1 --zone=us-west1-b
source /opt/anki-venv/bin/activate
cd /opt/anki-service
python worker.py  # Run in foreground to see errors
```

### Environment Variables Not Set

```bash
# SSH into VM and check environment in service
gcloud compute ssh anki-worker-1 --zone=us-west1-b

# View service environment
sudo systemctl show anki-worker --property=Environment

# Check what Python sees
sudo journalctl -u anki-worker -n 50 | grep -i "env\|shared\|redis"
```

### Update Code After Deployment

If you update code in the GitHub repo:

```bash
# SSH into VM
gcloud compute ssh anki-worker-1 --zone=us-west1-b

# Pull latest code
cd /opt/anki-service
sudo git pull

# Restart service to use new code
sudo systemctl restart anki-worker

# Verify it's running
systemctl status anki-worker
```

### Manually Update Environment Variables

If you need to change environment variables without recreating VMs:

```bash
# SSH into VM
gcloud compute ssh anki-worker-1 --zone=us-west1-b

# Edit service file
sudo nano /etc/systemd/system/anki-worker.service
# Modify Environment= lines as needed

# Reload systemd and restart
sudo systemctl daemon-reload
sudo systemctl restart anki-worker

# Verify
systemctl status anki-worker
```

## Verification Script

Use the enhanced diagnostic script:

```bash
./check_queue_process.sh
```

This now checks:
- ✓ Systemd service status
- ✓ Metadata server values
- ✓ Environment variables from running processes
- ✓ Shared storage access
- ✓ Recent logs

## Benefits Over nohup

| Feature | nohup | systemd |
|---------|-------|---------|
| Auto-restart on crash | ❌ No | ✅ Yes |
| Integrated logging | ❌ Manual | ✅ journalctl |
| Environment management | ⚠️ Complex | ✅ Built-in |
| Process monitoring | ❌ Manual ps | ✅ systemctl status |
| Survives reboots | ❌ No | ✅ Yes (with enable) |
| Resource limits | ❌ No | ✅ Configurable |
| Dependencies | ❌ No | ✅ After/Wants |

## Quick Reference

```bash
# Status of all services
for vm in anki-rest-server anki-worker-1 anki-worker-2; do
  echo "=== $vm ==="
  gcloud compute ssh $vm --zone=us-west1-b --command "systemctl status anki-* --no-pager" 2>/dev/null || true
done

# Restart everything
gcloud compute ssh anki-rest-server --zone=us-west1-b --command "sudo systemctl restart anki-rest"
gcloud compute ssh anki-worker-1 --zone=us-west1-b --command "sudo systemctl restart anki-worker"
gcloud compute ssh anki-worker-2 --zone=us-west1-b --command "sudo systemctl restart anki-worker"

# Follow all logs
tmux new-session -d "gcloud compute ssh anki-rest-server --zone=us-west1-b -- journalctl -u anki-rest -f" \; \
  split-window -h "gcloud compute ssh anki-worker-1 --zone=us-west1-b -- journalctl -u anki-worker -f" \; \
  split-window -v "gcloud compute ssh anki-worker-2 --zone=us-west1-b -- journalctl -u anki-worker -f" \; \
  attach
```

## Next Steps

After verifying services are running:

1. **Test the service**: Upload a file and check job processing
2. **Monitor logs**: Use `journalctl -f` to watch real-time activity
3. **Check queue depth**: Run `./check_queue_process.sh` periodically
4. **Scale workers**: Run `create_workers.py` with higher `WORKER_COUNT`
