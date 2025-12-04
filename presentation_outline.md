# Kubernetes Cluster on GCP VMs - Presentation Outline

## Slide 1: Title
**Multi-Node Kubernetes Cluster on Google Cloud Platform**
- Course: Data Center Scale Computing
- Institution: University of Colorado Boulder
- Semester: Fall 2025
- Participants: [Your Names]

---

## Slide 2: Project Goals
**What We Accomplished:**
- Deployed a production-grade Kubernetes cluster on GCP Compute Engine
- Implemented high-availability architecture with 3 control plane nodes
- Configured distributed storage using Longhorn
- Set up comprehensive monitoring with Prometheus and Grafana
- Deployed and tested ML workloads (Stable Diffusion inference)
- Achieved automatic failover and self-healing capabilities
- Demonstrated container orchestration at scale

---

## Slide 3: Hardware Components
**GCP Compute Engine Instances:**
- **Control Plane Nodes (3x):**
  - Machine Type: e2-standard-4 (4 vCPUs, 16 GB RAM)
  - OS: Ubuntu 22.04 LTS
  - Boot Disk: 50 GB SSD
  - Purpose: Kubernetes control plane (HA configuration)

- **Worker Nodes (2x):**
  - Machine Type: e2-standard-4 (4 vCPUs, 16 GB RAM)
  - OS: Ubuntu 22.04 LTS
  - Boot Disk: 50 GB SSD
  - Additional Storage: 100 GB persistent disks for Longhorn
  - Purpose: Application workload execution

- **Network Infrastructure:**
  - VPC Network with custom firewall rules
  - Internal IPs for cluster communication
  - External IPs for management access

---

## Slide 4: Software Components
**Core Stack:**
- **Kubernetes v1.31:** Container orchestration platform
  - kubeadm, kubelet, kubectl
- **containerd 1.7:** Container runtime (CRI)
- **Calico v3.28:** CNI for pod networking
- **Longhorn v1.7:** Distributed block storage
- **MetalLB v0.14:** Load balancer for bare metal

**Observability & Orchestration:**
- **Prometheus:** Metrics collection
- **Grafana:** Visualization dashboards
- **Argo Workflows v3.5:** ML pipeline orchestration

**ML Workloads:**
- Stable Diffusion with custom inference containers
- PyTorch-based models

---

## Slide 5: System Architecture
**Architecture Diagram Elements:**
```
┌─────────────────────────────────────────────────────────┐
│                    GCP VPC Network                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Control Plane (HA)                      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │  │
│  │  │ Master 1 │  │ Master 2 │  │ Master 3 │       │  │
│  │  │ API+etcd │  │ API+etcd │  │ API+etcd │       │  │
│  │  └──────────┘  └──────────┘  └──────────┘       │  │
│  └──────────────────────────────────────────────────┘  │
│                           │                             │
│               Calico CNI Network                        │
│                           │                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Worker Nodes                         │  │
│  │  ┌──────────┐         ┌──────────┐               │  │
│  │  │ Worker 1 │         │ Worker 2 │               │  │
│  │  │ +Longhorn│         │ +Longhorn│               │  │
│  │  └──────────┘         └──────────┘               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [Prometheus] ← metrics ← [All Nodes]                  │
│       ↓                                                 │
│  [Grafana Dashboards]                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Slide 6: Component Interactions
**Request Flow:**
1. **User → kubectl:** Submit workload definition
2. **kubectl → API Server:** Authenticate and validate request
3. **API Server → etcd:** Store cluster state (replicated across 3 masters)
4. **Scheduler:** Watch for unscheduled pods, assign to optimal node
5. **Kubelet → containerd:** Pull images and start containers
6. **Calico:** Assign pod IPs, configure routing
7. **Longhorn:** Provision and attach persistent volumes
8. **MetalLB:** Allocate LoadBalancer IPs for services

**Monitoring Flow:**
- Node Exporter → Prometheus (hardware metrics)
- kube-state-metrics → Prometheus (K8s object state)
- Prometheus → Grafana (visualization)

---

## Slide 7: Debugging & Testing Methodology
**Debugging Strategies:**
- `kubectl logs/describe` for pod troubleshooting
- `journalctl -u kubelet` for node-level issues
- Calico diagnostics with `calicoctl`
- Longhorn UI for storage health monitoring
- Prometheus queries for performance analysis

**Testing Approach:**
1. **Unit Testing:** Individual component verification
2. **Integration Testing:** Multi-component workflows
3. **Load Testing:** Multiple concurrent ML jobs
4. **Chaos Testing:** Simulated node failures
5. **Performance Testing:** Latency and throughput benchmarks

**Training Data:**
- Stable Diffusion pre-trained models
- Test prompts for inference validation
- Synthetic workloads for stress testing

---

## Slide 8: System Performance
**Workload Capacity:**
- Concurrent ML inference jobs: 4-6 simultaneous tasks
- Pod density: ~30-40 pods per worker node
- Storage: 200 GB distributed across nodes (3x replication)
- Network throughput: ~10 Gbps (GCP network)

**Performance Metrics:**
- Pod startup time: 5-15 seconds
- Image pull time: 30 seconds - 3 minutes (model size dependent)
- Stable Diffusion inference: 15-45 seconds per image
- Control plane failover: <30 seconds
- Volume provisioning: 10-20 seconds

**Identified Bottlenecks:**
1. **CPU:** Limited by e2-standard-4 vCPU count for ML workloads
2. **Memory:** 16 GB constrains large model sizes
3. **Storage I/O:** Longhorn replication overhead
4. **Network:** Large model transfers during image pulls
5. **etcd:** Performance degrades with >100k objects

---

## Slide 9: Demo & Results
**Live Demonstration:**
- Grafana monitoring dashboard
- Running pods: `kubectl get pods -A`
- Argo Workflows UI showing ML pipelines
- Stable Diffusion inference output
- Node failure simulation and recovery

**Key Results:**
✓ Successfully deployed HA Kubernetes cluster
✓ Zero-downtime control plane failover tested
✓ Persistent storage maintained across pod restarts
✓ ML inference workloads running successfully
✓ Real-time monitoring and alerting operational

---

## Slide 10: Lessons Learned & Future Work
**Key Takeaways:**
- High availability requires careful planning and testing
- Monitoring is essential for production systems
- Storage is often the bottleneck in stateful workloads
- Kubernetes abstractions simplify complex orchestration

**Future Enhancements:**
- GPU-enabled nodes for faster ML inference
- Horizontal Pod Autoscaler for dynamic scaling
- Service mesh (Istio) for advanced traffic management
- GitOps with ArgoCD for declarative deployments
- Multi-cluster federation for geo-distribution
