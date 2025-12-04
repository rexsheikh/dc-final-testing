#!/usr/bin/env python3
"""
Create REST tier VM for PDF-to-Anki service
Single instance running Flask API server
Based on lab5/part2_updated.py
"""

import os
import time
from typing import Dict

import googleapiclient.discovery
from googleapiclient.errors import HttpError

# Configuration
PROJECT_ID = "substantial-art-471117-v1"
ZONE = "us-west1-b"
SOURCE_INSTANCE = "flask-instance"
MACHINE_TYPE = "e2-medium"  # Larger for REST tier
INSTANCE_NAME = "anki-rest-server"

# GitHub repo
REPO_URL = "https://github.com/rexsheikh/dc-final-testing"


def wait_for_operation(compute, project: str, zone: str, operation: str) -> Dict:
    """Wait for ZONAL operation to complete."""
    print(f"Waiting for zonal operation {operation} to finish...")
    while True:
        result = (
            compute.zoneOperations()
            .get(project=project, zone=zone, operation=operation)
            .execute()
        )
        if result.get("status") == "DONE":
            print("done.")
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        time.sleep(1)


def wait_for_global_operation(compute, project: str, operation: str) -> Dict:
    """Wait for GLOBAL operation to complete."""
    print(f"Waiting for global operation {operation} to finish...")
    while True:
        result = compute.globalOperations().get(project=project, operation=operation).execute()
        if result.get("status") == "DONE":
            print("done.")
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        time.sleep(1)


def ensure_firewall_rule(compute, project: str) -> None:
    """Ensure firewall rule 'allow-5000' exists."""
    rule_name = "allow-5000"
    try:
        compute.firewalls().get(project=project, firewall=rule_name).execute()
        print(f"Firewall rule '{rule_name}' already exists.")
    except HttpError as e:
        if getattr(e, "resp", None) and getattr(e.resp, "status", None) == 404:
            print(f"Creating firewall rule '{rule_name}'...")
            body = {
                "name": rule_name,
                "network": "global/networks/default",
                "direction": "INGRESS",
                "targetTags": ["allow-5000"],
                "allowed": [{"IPProtocol": "tcp", "ports": ["5000"]}],
                "sourceRanges": ["0.0.0.0/0"],
                "description": "Allow TCP port 5000 for Flask app",
            }
            op = compute.firewalls().insert(project=project, body=body).execute()
            wait_for_global_operation(compute, project, op["name"])
        else:
            raise


def get_boot_disk_name(compute, project: str, zone: str, instance_name: str) -> str:
    """Find the boot disk name for a given instance."""
    inst = compute.instances().get(project=project, zone=zone, instance=instance_name).execute()
    for d in inst.get("disks", []):
        if d.get("boot"):
            source_link = d.get("source", "")
            disk_name = source_link.split("/")[-1]
            return disk_name
    raise RuntimeError(f"No boot disk found for instance {instance_name}")


def ensure_snapshot(compute, project: str, zone: str, source_instance: str) -> str:
    """Ensure a snapshot exists; create if missing."""
    snapshot_name = f"base-snapshot-{source_instance}"
    try:
        compute.snapshots().get(project=project, snapshot=snapshot_name).execute()
        print(f"Snapshot '{snapshot_name}' already exists.")
        return snapshot_name
    except HttpError as e:
        if getattr(e, "resp", None) and getattr(e.resp, "status", None) == 404:
            disk_name = get_boot_disk_name(compute, project, zone, source_instance)
            print(f"Creating snapshot '{snapshot_name}' from disk '{disk_name}'...")
            body = {"name": snapshot_name}
            op = (
                compute.disks()
                .createSnapshot(project=project, zone=zone, disk=disk_name, body=body)
                .execute()
            )
            wait_for_operation(compute, project, zone, op["name"])
            return snapshot_name
        else:
            raise


def create_rest_instance(
    compute,
    project: str,
    zone: str,
    name: str,
    machine_type_short: str,
    snapshot_name: str,
) -> Dict:
    """Create REST tier instance with Flask app startup script."""
    machine_type = f"zones/{zone}/machineTypes/{machine_type_short}"
    
    # REST tier startup script: clone repo, install deps, start Flask
    startup_script = f"""#!/usr/bin/env bash
set -euxo pipefail

# Install dependencies
apt-get update
apt-get install -y python3-pip git redis-tools

# Clone repository
cd /opt
git clone {REPO_URL} anki-service
cd anki-service

# Install Python dependencies
pip3 install -r requirements.txt

# Start Flask REST API
nohup python3 app.py &>/var/log/anki-rest.log &
"""

    body = {
        "name": name,
        "machineType": machine_type,
        "tags": {"items": ["allow-5000"]},
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceSnapshot": f"global/snapshots/{snapshot_name}"
                },
            }
        ],
        "networkInterfaces": [
            {
                "network": "global/networks/default",
                "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
            }
        ],
        "serviceAccounts": [
            {
                "email": "default",
                "scopes": [
                    "https://www.googleapis.com/auth/devstorage.read_write",
                    "https://www.googleapis.com/auth/logging.write",
                ],
            }
        ],
        "metadata": {
            "items": [
                {"key": "startup-script", "value": startup_script},
            ]
        },
    }

    try:
        return compute.instances().insert(project=project, zone=zone, body=body).execute()
    except HttpError as e:
        if getattr(e, "resp", None) and getattr(e.resp, "status", None) == 409:
            alt_name = f"{name}-{int(time.time())}"
            print(f"Name conflict for {name}, retrying as {alt_name}...")
            body["name"] = alt_name
            return compute.instances().insert(project=project, zone=zone, body=body).execute()
        else:
            raise


def get_external_ip(compute, project: str, zone: str, instance_name: str) -> str:
    """Retrieve instance external IP."""
    inst = compute.instances().get(project=project, zone=zone, instance=instance_name).execute()
    for nic in inst.get("networkInterfaces", []):
        for ac in nic.get("accessConfigs", []):
            if "natIP" in ac:
                return ac["natIP"]
    raise RuntimeError("No external IP found")


def main():
    compute = googleapiclient.discovery.build("compute", "v1")
    
    print(f"Creating REST tier VM for Anki service...")
    print(f"Project: {PROJECT_ID}, Zone: {ZONE}")
    
    # Ensure firewall rule
    ensure_firewall_rule(compute, PROJECT_ID)
    
    # Ensure snapshot exists
    snapshot_name = ensure_snapshot(compute, PROJECT_ID, ZONE, SOURCE_INSTANCE)
    
    # Create REST instance
    print(f"\nCreating REST server {INSTANCE_NAME}...")
    t0 = time.monotonic()
    op = create_rest_instance(
        compute, PROJECT_ID, ZONE, INSTANCE_NAME, MACHINE_TYPE, snapshot_name
    )
    wait_for_operation(compute, PROJECT_ID, ZONE, op["name"])
    t1 = time.monotonic()
    
    try:
        ip = get_external_ip(compute, PROJECT_ID, ZONE, INSTANCE_NAME)
        print(f"\n{'='*60}")
        print(f"REST server created successfully in {t1-t0:.1f}s")
        print(f"Instance: {INSTANCE_NAME}")
        print(f"External IP: {ip}")
        print(f"API Endpoint: http://{ip}:5000")
        print(f"Health Check: http://{ip}:5000/health")
        print(f"{'='*60}")
    except Exception as e:
        print(f"Warning: could not get IP for {INSTANCE_NAME}: {e}")


if __name__ == "__main__":
    main()
