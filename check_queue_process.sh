#!/usr/bin/env bash
set -euo pipefail
REST_INSTANCE=${REST_INSTANCE:-anki-rest-server}
ZONE=${ZONE:-us-west1-b}

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

declare -a workers=(anki-worker-1 anki-worker-2)
for worker in "${workers[@]}"; do
  log "Worker $worker process + log"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "ps -ef | grep -v grep | grep worker.py || echo 'No worker process'; sudo tail -n 40 /var/log/anki-worker.log || echo 'No log'"
done

gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "sudo tail -n 60 /var/log/anki-rest.log"
