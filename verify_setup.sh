#!/usr/bin/env bash
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID="substantial-art-471117-v1"
ZONE="us-west1-b"
BASE_INSTANCE="flask-instance"

log_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}  ✓ PASS${NC} - $1"
}

log_fail() {
    echo -e "${RED}  ✗ FAIL${NC} - $1"
}

log_skip() {
    echo -e "${YELLOW}  ⊘ SKIP${NC} - $1"
}

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

check_gcloud() {
    log_check "Checking gcloud CLI installation"
    if command -v gcloud >/dev/null 2>&1; then
        VERSION=$(gcloud version --format="value(version)")
        log_pass "gcloud CLI installed (version: $VERSION)"
        ((PASS_COUNT++))
    else
        log_fail "gcloud CLI not found"
        ((FAIL_COUNT++))
    fi
}

check_project() {
    log_check "Checking GCP project configuration"
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$CURRENT_PROJECT" = "$PROJECT_ID" ]; then
        log_pass "Project configured: $PROJECT_ID"
        ((PASS_COUNT++))
    else
        log_fail "Project not configured (current: $CURRENT_PROJECT, expected: $PROJECT_ID)"
        ((FAIL_COUNT++))
    fi
}

check_firewall() {
    log_check "Checking firewall rule 'allow-5000'"
    if gcloud compute firewall-rules describe allow-5000 --project="$PROJECT_ID" &>/dev/null; then
        log_pass "Firewall rule exists"
        ((PASS_COUNT++))
    else
        log_fail "Firewall rule not found"
        ((FAIL_COUNT++))
    fi
}

check_base_instance() {
    log_check "Checking base instance '$BASE_INSTANCE'"
    if gcloud compute instances describe "$BASE_INSTANCE" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        STATUS=$(gcloud compute instances describe "$BASE_INSTANCE" --zone="$ZONE" --format="value(status)")
        if [ "$STATUS" = "RUNNING" ]; then
            log_pass "Instance exists and running"
            ((PASS_COUNT++))
        else
            log_fail "Instance exists but not running (status: $STATUS)"
            ((FAIL_COUNT++))
        fi
    else
        log_skip "Base instance not created yet"
        ((SKIP_COUNT++))
    fi
}

check_snapshot() {
    log_check "Checking base snapshot"
    SNAPSHOT_NAME="base-snapshot-$BASE_INSTANCE"
    if gcloud compute snapshots describe "$SNAPSHOT_NAME" --project="$PROJECT_ID" &>/dev/null; then
        SIZE=$(gcloud compute snapshots describe "$SNAPSHOT_NAME" --format="value(diskSizeGb)")
        log_pass "Snapshot exists (size: ${SIZE}GB)"
        ((PASS_COUNT++))
    else
        log_skip "Snapshot not created yet"
        ((SKIP_COUNT++))
    fi
}

check_vm_dependencies() {
    log_check "Checking dependencies on base VM"
    if gcloud compute instances describe "$BASE_INSTANCE" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        # Check Python
        if gcloud compute ssh "$BASE_INSTANCE" --zone="$ZONE" --command="python3 --version" &>/dev/null; then
            PYTHON_VER=$(gcloud compute ssh "$BASE_INSTANCE" --zone="$ZONE" --command="python3 --version" 2>&1)
            log_pass "Python installed: $PYTHON_VER"
            ((PASS_COUNT++))
        else
            log_fail "Python not installed on VM"
            ((FAIL_COUNT++))
        fi
        
        # Check Redis
        if gcloud compute ssh "$BASE_INSTANCE" --zone="$ZONE" --command="redis-cli ping" &>/dev/null; then
            log_pass "Redis server running"
            ((PASS_COUNT++))
        else
            log_fail "Redis server not running"
            ((FAIL_COUNT++))
        fi
        
        # Check Git
        if gcloud compute ssh "$BASE_INSTANCE" --zone="$ZONE" --command="git --version" &>/dev/null; then
            log_pass "Git installed"
            ((PASS_COUNT++))
        else
            log_fail "Git not installed"
            ((FAIL_COUNT++))
        fi
    else
        log_skip "Base instance not available"
        ((SKIP_COUNT+=3))
    fi
}

print_summary() {
    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}Verification Summary${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
    echo -e "${RED}Failed:${NC} $FAIL_COUNT"
    echo -e "${YELLOW}Skipped:${NC} $SKIP_COUNT"
    echo ""
    
    if [ $FAIL_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ All checks passed!${NC}"
        echo "You're ready to deploy the service."
        exit 0
    else
        echo -e "${RED}✗ Some checks failed.${NC}"
        echo "Please run setup_base_vm.sh to configure your environment."
        exit 1
    fi
}

main() {
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}PDF-to-Anki Setup Verification${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    
    check_gcloud
    echo ""
    check_project
    echo ""
    check_firewall
    echo ""
    check_base_instance
    echo ""
    check_snapshot
    echo ""
    check_vm_dependencies
    
    print_summary
}

main "$@"
