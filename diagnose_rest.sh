#!/usr/bin/env bash
set -euo pipefail

# Simple diagnostics script to capture REST tier health information.
# Usage: ./diagnose_rest.sh

REST_INSTANCE=${REST_INSTANCE:-anki-rest-server}
ZONE=${ZONE:-us-west1-b}
REST_PORT=${REST_PORT:-5000}

log() {
    printf "\n=== %s ===\n" "$1"
}

run_local() {
    log "Local curl to REST /health"
    REST_IP=$(gcloud compute instances describe "$REST_INSTANCE" \
        --zone="$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    echo "REST_IP: $REST_IP"
    if [[ -z "$REST_IP" ]]; then
        echo "Could not resolve REST IP"
        return
    fi
    set +e
    curl -v --max-time 5 "http://$REST_IP:$REST_PORT/health"
    echo "curl exit code: $?"
    set -e
}

run_remote() {
    log "Remote diagnostics on $REST_INSTANCE"

    gcloud compute ssh "$REST_INSTANCE" \
        --zone="$ZONE" \
        --command="
set -euxo pipefail
echo 'Python version:'
python3 -V
echo 'pip info:'
python3 -m pip -V || true
echo 'Probe Flask import:'
python3 - <<'PY'
try:
    import flask
    from flask import Flask
    print('flask import OK:', flask.__version__, flask.__file__)
except Exception as exc:
    print('flask import failed:', exc)
PY
echo 'Check repo path:'
ls -l /opt/anki-service || true
echo 'Is app.py present?'
ls -l /opt/anki-service/app.py || true
echo 'Active Flask processes (python app.py):'
ps -ef | grep '[p]ython3 app.py' || echo 'No python3 app.py process found'
echo 'Listening sockets on port $REST_PORT:'
sudo lsof -iTCP:$REST_PORT -sTCP:LISTEN || echo 'Nothing listening on port $REST_PORT'
echo 'Local curl to /health:'
set +e
curl -v --max-time 5 http://127.0.0.1:$REST_PORT/health
echo 'curl exit code:' \$?
set -e
echo 'Last 60 lines of /var/log/anki-rest.log:'
sudo tail -n 60 /var/log/anki-rest.log || true
" || {
        echo "Remote diagnostics failed"
    }
}

run_local
run_remote

log "Diagnostics complete"
