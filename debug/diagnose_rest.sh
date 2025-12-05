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
echo '=== System Info ==='
echo 'Python version:'
python3 -V
echo 'pip info:'
python3 -m pip -V || true

echo ''
echo '=== Flask Installation ==='
python3 - <<'PY'
try:
    import flask
    from flask import Flask
    print('flask import OK:', flask.__version__, flask.__file__)
except Exception as exc:
    print('flask import failed:', exc)
PY

echo ''
echo '=== Repository State ==='
echo 'Check repo path:'
ls -l /home/rexsheikh/anki-service || true
echo 'Is app.py present?'
ls -l /home/rexsheikh/anki-service/app.py || true
echo 'Latest commit:'
cd /home/rexsheikh/anki-service && git log -1 --oneline || true

echo ''
echo '=== Systemd Service Status ==='
sudo systemctl status anki-rest.service --no-pager || echo 'anki-rest.service not found or inactive'

echo ''
echo '=== Service Configuration ==='
echo 'Service file:'
sudo cat /etc/systemd/system/anki-rest.service || true

echo ''
echo '=== Process Info ==='
echo 'Active Flask processes (python app.py):'
ps aux | grep '[p]ython.*app.py' || echo 'No python app.py process found'

echo ''
echo '=== Network Status ==='
echo 'Listening sockets on port 5000:'
sudo lsof -iTCP:5000 -sTCP:LISTEN || echo 'Nothing listening on port 5000'
echo 'Firewall status:'
sudo ufw status || echo 'ufw not configured'

echo ''
echo '=== Local Connectivity Test ==='
set +e
curl -v --max-time 5 http://127.0.0.1:5000/health
echo 'curl exit code:' \$?
set -e

echo ''
echo '=== Service Logs (last 60 lines) ==='
sudo journalctl -u anki-rest.service -n 60 --no-pager || echo 'No logs available'

echo ''
echo '=== Environment Variables from Process ==='
REST_PID=\$(pgrep -f 'python.*app.py' | head -1)
if [[ -n \"\$REST_PID\" ]]; then
    echo \"Process PID: \$REST_PID\"
    echo 'Environment variables:'
    sudo cat /proc/\$REST_PID/environ | tr '\\0' '\\n' | grep -E 'REDIS|SHARED|PYTHON' || echo 'No matching env vars'
else
    echo 'No REST process running'
fi

echo ''
echo '=== Redis Connectivity ==='
python3 -c 'import redis; r=redis.Redis(host=\"localhost\", port=6379); print(\"Redis PING:\", r.ping())' || echo 'Redis connection failed'
" || {
        echo "Remote diagnostics failed"
    }
}

run_local
run_remote

log "Diagnostics complete"
