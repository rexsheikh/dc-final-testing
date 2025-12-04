# PDF-to-Anki Text Service

A cloud-hosted Flask service that converts text documents into Anki flashcard decks using NLP techniques.

## Architecture

- **REST Tier**: Flask API for file uploads, job status, and deck downloads
- **Worker Tier**: 2+ worker VMs processing jobs from Redis queue
- **Queue**: Redis (local or Cloud Memorystore) for job management
- **Storage**: Local filesystem (upgradeable to Cloud Storage)

## Deployment

### 1. Create REST Tier VM

```bash
python3 create_rest_tier.py
```

This creates a single VM running the Flask API server.

### 2. Create Worker VMs

```bash
python3 create_workers.py
```

This creates 2 worker VMs that process NLP jobs from the Redis queue.

### 3. Configure Redis

Workers connect to `localhost:6379` by default. For production, update to Cloud Memorystore host.

## API Endpoints

- `GET /health` - Health check
- `POST /upload` - Upload .txt files (multipart/form-data)
- `GET /status/<job_id>` - Check job status
- `GET /download/<job_id>` - Download generated Anki deck (CSV)
- `GET /jobs` - List all jobs (optional: `?user=<username>`)

## NLP Pipeline

1. **Text Normalization**: Sentence splitting and cleaning
2. **Summarization**: Extractive summary using sentence scoring
3. **TF-IDF Extraction**: Top-N keywords with context
4. **Named Entity Recognition**: Simple pattern-based NER
5. **Deck Assembly**: Generate Anki-compatible CSV

## Usage Example

```bash
# Upload a text file
curl -F "files=@lecture.txt" http://<REST_IP>:5000/upload

# Check status
curl http://<REST_IP>:5000/status/<job_id>

# Download deck when completed
curl http://<REST_IP>:5000/download/<job_id> -o deck.csv
```

## Repository

Code repo: https://github.com/rexsheikh/dc-final-testing

## Course Lab Connections

- **Lab 5**: VM snapshot-and-clone approach for worker creation
- **Lab 6**: Flask REST API design and manual VM provisioning
- **Lab 7**: Redis queue architecture (LPUSH/BRPOP pattern)
