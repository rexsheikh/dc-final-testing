#!/usr/bin/env bash
set -euo pipefail
REST_INSTANCE=${REST_INSTANCE:-anki-rest-server}
ZONE=${ZONE:-us-west1-b}
WORKERS=${WORKERS:-anki-worker-1,anki-worker-2}

IFS=',' read -r -a worker_list <<< "$WORKERS"

log(){
  printf '\n=== %s ===\n' "$1"
}

log "Queue depth"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "redis-cli llen job_queue"

log "Sample queued job"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "redis-cli lrange job_queue 0 0"

log "Worker metadata (job:*)"
JOB_ID=$(gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "redis-cli lindex job_queue 0" 2>/dev/null || true)
if [[ -n "$JOB_ID" ]]; then
  gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "redis-cli get job:$JOB_ID"
else
  echo "No job ID found in queue"
fi

glog_rest_dir(){
  log "REST shared storage layout"
  gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "ls -lah /mnt/shared && ls -lah /mnt/shared/uploads || true"
}

glog_rest_dir

for worker in "${worker_list[@]}"; do
  log "Worker $worker systemd status"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "systemctl status anki-worker --no-pager || echo 'Systemd service not found (old deployment?)'"

  log "Worker $worker systemd service file"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "echo '--- Service Environment Lines ---' && grep '^Environment=' /etc/systemd/system/anki-worker.service 2>/dev/null || echo 'Service file not found'"

  log "Worker $worker code version check"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "echo '--- Checking for diagnostic logging in worker.py ---' && grep -n 'Worker starting with configuration' /opt/anki-service/worker.py || echo 'Diagnostic logging NOT FOUND (old code)'"

  log "Worker $worker metadata server values"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "echo 'rest-internal-ip:' && curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/attributes/rest-internal-ip || echo 'N/A'; echo 'shared-root:' && curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/attributes/shared-root || echo 'N/A'"

  log "Worker $worker Redis connectivity"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "
REST_IP=\$(curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/attributes/rest-internal-ip)
echo \"Testing Redis connection to \$REST_IP:6379\"
redis-cli -h \$REST_IP -p 6379 ping 2>&1 || echo 'Redis connection FAILED'
"

  log "Worker $worker environment (from running process)"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "
# Get PID of worker process
WORKER_PID=\$(pgrep -f 'python.*worker.py' | head -1)
if [ -n \"\$WORKER_PID\" ]; then
  echo \"Worker PID: \$WORKER_PID\"
  echo '--- Environment of actual worker process ---'
  sudo cat /proc/\$WORKER_PID/environ | tr '\\0' '\\n' | grep -E 'REDIS_HOST|SHARED_' || echo 'No matching env vars found'
else
  echo 'Worker process not found'
fi
"

  log "Worker $worker shared storage"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "ls -lah /mnt/shared || true; ls -lah /mnt/shared/uploads || true"

  log "Worker $worker process + recent log"
  gcloud compute ssh "$worker" --zone="$ZONE" --command \
    "ps -ef | grep -v grep | grep worker.py || echo 'No worker process'; echo '--- Last 60 lines of log ---'; sudo tail -n 60 /var/log/anki-worker.log || echo 'No log'; echo '--- Check for Python errors ---'; sudo journalctl -u anki-worker -n 30 --no-pager || echo 'No journalctl'"
done

log "REST systemd status"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "systemctl status anki-rest --no-pager || echo 'Systemd service not found (old deployment?)'"

log "REST systemd service file"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "echo '--- Service Environment Lines ---' && grep '^Environment=' /etc/systemd/system/anki-rest.service 2>/dev/null || echo 'Service file not found'"

log "REST Flask log"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "sudo tail -n 60 /var/log/anki-rest.log"
