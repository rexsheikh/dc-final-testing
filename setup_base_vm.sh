#!/usr/bin/env bash
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="substantial-art-471117-v1"
ZONE="us-west1-b"
BASE_INSTANCE="flask-instance"
MACHINE_TYPE="e2-medium"
DISK_SIZE="10GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"
REPO_URL="https://github.com/rexsheikh/dc-final-testing.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="/opt/anki-venv"

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

# Logging functions
log_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗ ERROR:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠ WARNING:${NC} $1"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

wait_for_ssh() {
    local max_attempts=${1:-10}
    local delay=${2:-10}

    log_info "Waiting for SSH connectivity to $BASE_INSTANCE (up to $((max_attempts * delay))s)..."
    for attempt in $(seq 1 "$max_attempts"); do
        if gcloud compute ssh "$BASE_INSTANCE" \
            --zone="$ZONE" \
            --command="echo ssh-ready" \
            --quiet >/dev/null 2>&1; then
            log_success "SSH reachable on attempt $attempt"
            return 0
        fi
        log_info "SSH not ready (attempt $attempt/$max_attempts). Retrying in ${delay}s..."
        sleep "$delay"
    done

    error_exit "SSH still unavailable after $max_attempts attempts"
}

# Error handler
error_exit() {
    log_error "$1"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup script
main() {
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}PDF-to-Anki Service - Base VM Setup${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    log_info "Project: $PROJECT_ID"
    log_info "Zone: $ZONE"
    log_info "Instance: $BASE_INSTANCE"
    echo ""

    # Step 1: Check prerequisites
    log_step "Checking prerequisites"
    
    if ! command_exists gcloud; then
        error_exit "gcloud CLI not found. Please install Google Cloud SDK."
    fi
    log_success "gcloud CLI found"

    if ! command_exists python3; then
        error_exit "python3 not found. Please install Python 3."
    fi
    log_success "python3 found"

    # Step 2: Configure GCP environment
    log_step "Configuring GCP environment"
    
    log_info "Setting project to $PROJECT_ID..."
    gcloud config set project "$PROJECT_ID" --quiet || error_exit "Failed to set project"
    log_success "Project configured"

    log_info "Setting default zone to $ZONE..."
    gcloud config set compute/zone "$ZONE" --quiet || error_exit "Failed to set zone"
    log_success "Zone configured"

    # Step 3: Enable required APIs
    log_step "Enabling required GCP APIs"
    
    log_info "Enabling Compute Engine API..."
    gcloud services enable compute.googleapis.com --quiet 2>/dev/null || true
    
    log_info "Enabling Redis API..."
    gcloud services enable redis.googleapis.com --quiet 2>/dev/null || true
    
    log_info "Enabling Storage API..."
    gcloud services enable storage-api.googleapis.com --quiet 2>/dev/null || true
    
    log_success "APIs enabled (this may take a minute to propagate)"

    # Step 4: Create firewall rule
    log_step "Creating firewall rule for port 5000"
    
    if gcloud compute firewall-rules describe allow-5000 &>/dev/null; then
        log_warning "Firewall rule 'allow-5000' already exists, skipping"
    else
        log_info "Creating firewall rule..."
        gcloud compute firewall-rules create allow-5000 \
            --direction=INGRESS \
            --priority=1000 \
            --network=default \
            --action=ALLOW \
            --rules=tcp:5000 \
            --source-ranges=0.0.0.0/0 \
            --target-tags=allow-5000 \
            --description="Allow TCP port 5000 for Flask app" \
            --quiet || error_exit "Failed to create firewall rule"
        log_success "Firewall rule created"
    fi

    # Step 5: Check if base instance exists
    log_step "Checking for existing base instance"
    
    if gcloud compute instances describe "$BASE_INSTANCE" --zone="$ZONE" &>/dev/null; then
        log_warning "Instance '$BASE_INSTANCE' already exists"
        read -p "Delete and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing instance..."
            gcloud compute instances delete "$BASE_INSTANCE" \
                --zone="$ZONE" \
                --quiet || error_exit "Failed to delete instance"
            log_success "Existing instance deleted"
        else
            log_info "Using existing instance"
            INSTANCE_EXISTS=true
        fi
    fi

    # Step 6: Create base instance
    if [ "${INSTANCE_EXISTS:-false}" != "true" ]; then
        log_step "Creating base VM instance"
        
        log_info "Creating instance '$BASE_INSTANCE'..."
        gcloud compute instances create "$BASE_INSTANCE" \
            --zone="$ZONE" \
            --machine-type="$MACHINE_TYPE" \
            --image-family="$IMAGE_FAMILY" \
            --image-project="$IMAGE_PROJECT" \
            --boot-disk-size="$DISK_SIZE" \
            --tags=allow-5000 \
            --metadata=enable-oslogin=FALSE \
            --quiet || error_exit "Failed to create instance"
        
        log_success "Instance created successfully"
        
        # Wait for instance to be ready
        log_info "Waiting for instance to be ready (30 seconds)..."
        sleep 30
    else
        CURRENT_STEP=$((CURRENT_STEP + 1))
    fi

    # Ensure SSH is available before attempting SCP/SSH operations
    wait_for_ssh

    # Step 7: Install dependencies on VM
    log_step "Installing dependencies on base VM"
    
    log_info "Creating dependency installation script..."
    
VENV_PATH="/opt/anki-service/venv"

# Create temporary script for VM
cat > /tmp/install_deps.sh << 'EOFSCRIPT'
#!/usr/bin/env bash
set -euxo pipefail

VENV_PATH="/opt/anki-venv"

echo "==> Updating system packages..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "==> Installing Python and development tools..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    redis-server \
    build-essential \
    curl \
    wget

echo "==> Ensuring python3 pip module is available..."
sudo apt-get install --reinstall -y python3-pip python3-setuptools python3-wheel

echo "==> Configuring Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

echo "==> Testing Redis connection..."
redis-cli ping

echo "==> Installing global Python packages..."
sudo python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip --version

echo "==> Creating virtual environment..."
python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"
pip install --upgrade pip setuptools wheel
pip --version

echo "==> Dependency installation complete!"
EOFSCRIPT

    log_info "Copying installation script to VM..."
    gcloud compute scp /tmp/install_deps.sh "$BASE_INSTANCE":/tmp/install_deps.sh \
        --zone="$ZONE" \
        --quiet || error_exit "Failed to copy script to VM"
    
    log_info "Running installation script (this may take 3-5 minutes)..."
    gcloud compute ssh "$BASE_INSTANCE" \
        --zone="$ZONE" \
        --command="bash /tmp/install_deps.sh" \
        --quiet || error_exit "Failed to install dependencies"
    
    rm /tmp/install_deps.sh
    log_success "Dependencies installed successfully"

    # Pre-install Python requirements so snapshot includes dependencies
    REQUIREMENTS_PATH="$SCRIPT_DIR/requirements.txt"
    if [[ -f "$REQUIREMENTS_PATH" ]]; then
        log_info "Copying requirements.txt to base VM..."
        gcloud compute scp "$REQUIREMENTS_PATH" "$BASE_INSTANCE":/tmp/requirements.txt \
            --zone="$ZONE" \
            --quiet || error_exit "Failed to copy requirements.txt to VM"

        log_info "Installing Python dependencies on base VM (cached in snapshot)..."
        gcloud compute ssh "$BASE_INSTANCE" \
            --zone="$ZONE" \
            --command="source /opt/anki-venv/bin/activate && pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt" \
            --quiet || error_exit "Failed to pre-install Python dependencies"
        log_success "Python requirements installed on base VM"
    else
        log_warning "requirements.txt not found at $REQUIREMENTS_PATH; skipping pre-install"
    fi

    # Step 8: Create snapshot
    log_step "Creating snapshot of base VM"
    
    SNAPSHOT_NAME="base-snapshot-$BASE_INSTANCE"
    
    # Get boot disk name
    BOOT_DISK=$(gcloud compute instances describe "$BASE_INSTANCE" \
        --zone="$ZONE" \
        --format='get(disks[0].source.basename())' \
        --quiet) || error_exit "Failed to get boot disk name"
    
    log_info "Boot disk: $BOOT_DISK"
    
    # Check if snapshot exists
    if gcloud compute snapshots describe "$SNAPSHOT_NAME" &>/dev/null; then
        log_warning "Snapshot '$SNAPSHOT_NAME' already exists"
        read -p "Delete and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing snapshot..."
            gcloud compute snapshots delete "$SNAPSHOT_NAME" \
                --quiet || error_exit "Failed to delete snapshot"
        else
            log_info "Keeping existing snapshot"
            log_success "Setup complete!"
            print_summary
            exit 0
        fi
    fi
    
    log_info "Creating snapshot (this may take 2-3 minutes)..."
    gcloud compute disks snapshot "$BOOT_DISK" \
        --zone="$ZONE" \
        --snapshot-names="$SNAPSHOT_NAME" \
        --quiet || error_exit "Failed to create snapshot"
    
    log_success "Snapshot created successfully"

    # Summary
    print_summary
}

print_summary() {
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Base VM Setup Complete!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "${BLUE}Resources Created:${NC}"
    echo "  • Instance: $BASE_INSTANCE (zone: $ZONE)"
    echo "  • Snapshot: base-snapshot-$BASE_INSTANCE"
    echo "  • Firewall: allow-5000 (TCP:5000)"
    echo ""
    echo -e "${YELLOW}Important: GitHub Authentication${NC}"
    echo "  Before deploying, ensure you can authenticate with GitHub:"
    echo ""
    echo "  Option 1 - Personal Access Token (Recommended for Cloud Shell):"
    echo "    1. Create token: https://github.com/settings/tokens"
    echo "    2. Select scope: repo (all)"
    echo "    3. Use token as password when cloning"
    echo "    4. Cache: git config --global credential.helper 'cache --timeout=7200'"
    echo ""
    echo "  Option 2 - GitHub CLI (Easiest):"
    echo "    gh auth login"
    echo "    gh repo clone rexsheikh/dc-final-testing"
    echo ""
    echo "  Option 3 - SSH Keys:"
    echo "    ssh-keygen -t ed25519 -C \"your_email@example.com\""
    echo "    cat ~/.ssh/id_ed25519.pub  # Add to https://github.com/settings/keys"
    echo "    git clone git@github.com:rexsheikh/dc-final-testing.git"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "  1. Set up GitHub authentication (see above)"
    echo ""
    echo "  2. Deploy REST tier:"
    echo "     python3 create_rest_tier.py"
    echo ""
    echo "  3. Deploy worker tier:"
    echo "     python3 create_workers.py"
    echo ""
    echo "  4. Test the service:"
    echo "     REST_IP=\$(gcloud compute instances describe anki-rest-server --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
    echo "     curl http://\$REST_IP:5000/health"
    echo ""
    echo -e "${YELLOW}Note:${NC} Startup scripts will use HTTPS clone. You may need to configure"
    echo "  credentials on VMs or make the repository public for testing."
    echo ""
}

# Run main function
main "$@"
