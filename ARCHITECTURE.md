# Architecture Design Document

## Overview

The PDF-to-Anki Text Service is a distributed system for converting text documents into Anki flashcard decks. The architecture emphasizes **datacenter-scale computing concepts** over NLP sophistication.

## Core Design Principles

### 1. Lightweight NLP (No Heavy ML Dependencies)

**Decision**: Use pure Python NLP instead of ML frameworks (TensorFlow, PyTorch, transformers, spaCy, NLTK).

**Rationale**:
- **Focus on systems, not algorithms**: This is a datacenter computing course, not an NLP course
- **Fast deployment**: No model downloads (multi-GB files), no GPU setup, no dependency hell
- **Low resource usage**: Runs on `f1-micro` VMs with 614MB RAM
- **Quick startup**: Workers ready in 30-60 seconds vs. 5-10 minutes for model loading
- **Simple debugging**: Pure Python is easier to trace and troubleshoot

**Trade-offs**:
- Lower NLP quality (extractive vs. abstractive summarization, pattern-based vs. learned NER)
- Good enough for coursework demonstration and flashcard generation from lecture notes

**Implementation**:
- Extractive summarization using word frequency scoring
- TF-IDF with manual calculation (`collections.Counter` + math)
- Regex-based named entity recognition (capitalized phrases)
- All stages complete in 2-5 seconds per document

### 2. Queue-Based Worker Architecture (Lab 7 Pattern)

**Decision**: Redis LPUSH/BRPOP queue decouples REST API from NLP workers.

**Rationale**:
- Direct application of Lab 7 (MSaaS) architecture
- Horizontal scaling: add more workers without API changes
- Fault tolerance: failed jobs stay in queue, workers are stateless
- Load balancing: Redis distributes work automatically

**Implementation**:
```
Client → Flask REST → Redis Queue → Worker Pool → Redis Metadata → Client
         (upload)     (LPUSH)       (BRPOP)       (status update)   (download)
```

### 3. Snapshot-Based VM Cloning (Lab 5 Pattern)

**Decision**: Create golden image snapshot, then clone REST + worker VMs.

**Rationale**:
- Direct application of Lab 5 snapshot automation
- Fast VM creation: 15-25 seconds from snapshot vs. 2-3 minutes from scratch
- Consistent environment: all VMs have identical Python/Redis/Git setup
- No containerization needed: snapshots provide the same benefits for this scale

**Implementation**:
- Base VM: Ubuntu 22.04 + Python 3 + Redis + Git → Snapshot
- REST tier: 1x `e2-medium` VM cloned from snapshot
- Worker tier: 2x `f1-micro` VMs cloned from snapshot
- Startup scripts: `git clone` + `pip install` + start service

### 4. Public GitHub Repository (Deployment Simplicity)

**Decision**: Use public repo instead of private with deploy keys.

**Rationale**:
- Startup scripts can clone without authentication
- Simpler for coursework demonstration
- No secrets management needed
- Easy for instructors to review code

**Trade-offs**:
- Not production-ready (would use Cloud Source Repositories or private repo with Secret Manager)

### 5. Local Redis + Filesystem (Upgradeable Design)

**Decision**: Use local Redis and `/tmp` storage initially, design for cloud upgrade.

**Rationale**:
- Faster initial development and testing
- Lower cost for coursework
- Clear upgrade path documented:
  - Redis → Cloud Memorystore (multi-VM shared state)
  - `/tmp` → Cloud Storage (durable, scalable storage)
  - Redis metadata → Cloud SQL (complex queries, relationships)

**Current Limitations**:
- Workers must access REST tier's Redis (internal networking)
- `/tmp` storage not persistent across VM restarts
- No multi-region redundancy

## System Components

### REST Tier (Flask API)

**Responsibilities**:
- Accept file uploads via `POST /upload`
- Enqueue jobs to Redis (`LPUSH job_queue`)
- Track job metadata in Redis (`SET job:<uuid>`)
- Serve status queries (`GET /status/<id>`)
- Stream deck downloads (`GET /download/<id>`)

**Scaling**: Single instance sufficient for coursework; add load balancer + multiple instances for production.

### Worker Tier (NLP Processors)

**Responsibilities**:
- Pull jobs from Redis (`BRPOP job_queue`)
- Execute NLP pipeline (5 stages)
- Update job status in Redis
- Write output CSV to filesystem

**Scaling**: Add more workers by running `create_workers.py` with higher `WORKER_COUNT`.

### Queue (Redis)

**Responsibilities**:
- Job queue (`job_queue` list)
- Job metadata (`job:<uuid>` keys)
- Worker coordination (automatic via BRPOP)

**Current Setup**: Local Redis on REST tier VM.

**Upgrade Path**: Cloud Memorystore for multi-VM access.

### Storage (Filesystem)

**Responsibilities**:
- Input text files (`/tmp/uploads`)
- Output CSV decks (`/tmp/outputs`)

**Current Setup**: Local `/tmp` directories.

**Upgrade Path**: Cloud Storage buckets with signed URLs.

## Data Flow

1. **Upload**: Client → REST API → Save to `/tmp/uploads` → Enqueue job ID → Return job ID
2. **Processing**: Worker BRPOP → Load file → NLP pipeline → Save CSV → Update metadata
3. **Download**: Client → REST API → Check metadata → Stream file from `/tmp/outputs`

## Deployment Automation

### Base VM Setup (`setup_base_vm.sh`)

Automates:
- GCP configuration (project, zone, APIs)
- Firewall rule creation
- Base VM provisioning
- Dependency installation (Python, Redis, Git)
- Snapshot creation

### VM Provisioning (`create_rest_tier.py`, `create_workers.py`)

Uses Google Compute API to:
- Create instances from snapshot
- Inject startup scripts (clone repo, install deps, start service)
- Apply network tags (firewall rules)
- Wait for operations to complete

### Verification (`verify_setup.sh`, `debug_rest_server.sh`)

Diagnostic tools to:
- Check gcloud configuration
- Verify VMs are running
- Test API endpoints
- Inspect logs
- Debug startup failures

## Course Lab Connections

- **Lab 2 (UrlCount)**: Text parsing and frequency analysis → TF-IDF implementation
- **Labs 3-4 (SQL/PySpark)**: Data aggregation concepts → metadata management in Redis
- **Lab 5 (Snapshots)**: Snapshot automation → entire VM provisioning strategy
- **Lab 6 (REST API)**: API design → Flask endpoint structure
- **Lab 7 (MSaaS)**: Queue architecture → Redis-based worker pattern

## Performance Targets

- **VM boot**: <30 seconds from snapshot
- **Startup**: <60 seconds (git clone + pip install)
- **Job processing**: 2-5 seconds per file
- **API response**: <100ms for metadata queries
- **Throughput**: 20-30 jobs/minute with 2 workers

## Future Enhancements

1. **Cloud Memorystore**: Shared Redis for multi-VM deployments
2. **Cloud Storage**: Durable file storage with signed URLs
3. **Cloud SQL**: Metadata store for complex queries
4. **Load Balancing**: Multiple REST tier instances
5. **Auto-scaling**: Instance groups with health checks
6. **Monitoring**: Cloud Logging + Cloud Monitoring
7. **CI/CD**: Cloud Build pipelines
8. **ML Upgrade**: Optional transformer models for better NLP quality

## Security Considerations

**Current State** (coursework):
- Public GitHub repo
- Open firewall (0.0.0.0/0)
- No authentication on API
- No encryption

**Production Requirements**:
- Private repo with deploy keys
- Restricted firewall (specific IP ranges)
- API authentication (JWT tokens)
- HTTPS with SSL certificates
- Data encryption at rest
- Secret Manager for credentials
