#!/usr/bin/env bash
set -euo pipefail

REST_INSTANCE=${REST_INSTANCE:-anki-rest-server}
ZONE=${ZONE:-us-west1-b}
WORKERS=${WORKERS:-anki-worker-1,anki-worker-2}

IFS=',' read -r -a worker_list <<< "$WORKERS"

log(){
  printf '\n=== %s ===\n' "$1"
}

# Get REST server external IP
REST_IP=$(gcloud compute instances describe "$REST_INSTANCE" \
  --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "REST Server: http://$REST_IP:5000"

log "Checking Redis for completed jobs"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "
echo 'Total jobs in Redis:'
redis-cli KEYS 'job:*' | wc -l

echo -e '\nCompleted jobs:'
for key in \$(redis-cli KEYS 'job:*'); do
  job_data=\$(redis-cli GET \"\$key\")
  status=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"status\", \"unknown\"))')
  if [ \"\$status\" = \"completed\" ]; then
    job_id=\$(echo \"\$key\" | cut -d: -f2)
    filename=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"filename\", \"unknown\"))')
    has_output=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(\"YES\" if json.load(sys.stdin).get(\"output_content\") else \"NO\")')
    output_size=\$(echo \"\$job_data\" | python3 -c 'import sys, json; c=json.load(sys.stdin).get(\"output_content\",\"\"); print(len(c))')
    echo \"  Job: \$job_id | File: \$filename | Output in Redis: \$has_output | Size: \$output_size bytes\"
  fi
done

echo -e '\nFailed jobs:'
for key in \$(redis-cli KEYS 'job:*'); do
  job_data=\$(redis-cli GET \"\$key\")
  status=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"status\", \"unknown\"))')
  if [ \"\$status\" = \"failed\" ]; then
    job_id=\$(echo \"\$key\" | cut -d: -f2)
    filename=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"filename\", \"unknown\"))')
    error=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"error\", \"no error message\"))')
    echo \"  Job: \$job_id | File: \$filename | Error: \$error\"
  fi
done
"

log "Testing download endpoint for completed jobs"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "
for key in \$(redis-cli KEYS 'job:*'); do
  job_data=\$(redis-cli GET \"\$key\")
  status=\$(echo \"\$job_data\" | python3 -c 'import sys, json; print(json.load(sys.stdin).get(\"status\", \"unknown\"))')
  if [ \"\$status\" = \"completed\" ]; then
    job_id=\$(echo \"\$key\" | cut -d: -f2)
    echo \"Testing download for job: \$job_id\"
    curl -s -o /tmp/test_output.csv http://localhost:5000/download/\$job_id
    if [ -f /tmp/test_output.csv ] && [ -s /tmp/test_output.csv ]; then
      lines=\$(wc -l < /tmp/test_output.csv)
      echo \"  ✓ Downloaded successfully: \$lines lines\"
      echo \"  First 3 lines:\"
      head -n 3 /tmp/test_output.csv | sed 's/^/    /'
      rm /tmp/test_output.csv
    else
      echo \"  ✗ Download failed or empty file\"
    fi
    echo
  fi
done
"

log "Worker output directories"
for worker in "${worker_list[@]}"; do
  echo "Worker: $worker"
  gcloud compute ssh "$worker" --zone="$ZONE" --command "
    echo 'Output directory contents:'
    ls -lh /mnt/shared/outputs/ 2>/dev/null || echo 'Directory not found or empty'
    echo
    echo 'Sample of first output file (if any):'
    first_file=\$(ls /mnt/shared/outputs/*.csv 2>/dev/null | head -1)
    if [ -n \"\$first_file\" ]; then
      echo \"File: \$first_file\"
      head -n 3 \"\$first_file\" || echo 'Could not read file'
    else
      echo 'No CSV files found'
    fi
  " || echo "Failed to connect to $worker"
  echo
done

log "Summary"
echo "To test download via browser:"
echo "  1. Visit: http://$REST_IP:5000"
echo "  2. Check 'Recent Jobs' table for completed jobs"
echo "  3. Click 'Download deck' link"
echo
echo "To test via curl:"
gcloud compute ssh "$REST_INSTANCE" --zone="$ZONE" --command "
  completed_job=\$(redis-cli KEYS 'job:*' | head -1 | xargs redis-cli GET | python3 -c 'import sys, json; j=json.load(sys.stdin); print(j[\"job_id\"]) if j.get(\"status\")==\"completed\" else \"\"' 2>/dev/null || echo '')
  if [ -n \"\$completed_job\" ]; then
    echo \"  curl -O http://$REST_IP:5000/download/\$completed_job\"
  else
    echo '  (No completed jobs found)'
  fi
"
