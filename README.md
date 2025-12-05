# Text-to-Anki Service

A cloud-hosted Flask service that converts text documents into Anki flashcard decks using lightweight NLP techniques.

## Architecture

- **REST Tier**: Flask API for file uploads, job status, and deck downloads
- **Worker Tier**: 2+ worker VMs processing jobs from Redis queue
- **Queue**: Redis (local or Cloud Memorystore) for job management
- **Storage**: Local filesystem (upgradeable to Cloud Storage)
- **NLP Pipeline**: Pure Python implementation using standard library (no heavy ML frameworks)

## Key Design Decisions

### Lightweight NLP Implementation

This project intentionally uses **lightweight, pure-Python NLP** instead of heavy ML frameworks:

- **No external ML libraries**: No TensorFlow, PyTorch, transformers, spaCy, or NLTK
- **Fast startup**: VMs boot and process jobs in seconds, not minutes
- **Low resource usage**: Runs on `f1-micro` instances (614MB RAM)
- **Simple deployment**: No model downloads, GPU dependencies, or complex configurations

**Why?** The focus is on datacenter-scale computing concepts (VMs, queues, REST APIs, distributed systems) rather than NLP sophistication.

### NLP Pipeline Components

1. **Text Normalization**: Regex-based sentence splitting and whitespace cleanup
2. **Summarization**: Extractive summarization using word frequency scoring
3. **TF-IDF Extraction**: Manual TF-IDF calculation with `collections.Counter`
4. **Named Entity Recognition**: Pattern-based capitalized phrase detection
5. **Deck Assembly**: CSV generation with Python's built-in `csv.writer`

All processing uses Python 3 standard library + basic data structures.

## Quick Test (Local)

Test the NLP pipeline locally before deploying:

```bash
# Test with sample text
python3 -c "
from nlp import process_pipeline, DeckAssembler

text = '''Machine learning is a subset of artificial intelligence. Neural networks are 
computational models inspired by biological neurons. Deep learning uses multiple 
layers to extract features from data.'''

results = process_pipeline(text, 'test.txt')
DeckAssembler.write_csv(results['cards'], 'output.csv')
print(f'Generated {len(results[\"cards\"])} flashcards')
"

# View the output
cat output.csv
```

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

## Dependencies

Minimal dependencies for fast deployment:

```
Flask==3.0.0           # REST API framework
redis==5.0.1           # Queue and metadata store
google-api-python-client  # VM provisioning
Werkzeug==3.0.1        # Flask utilities
```

**No ML frameworks required** - all NLP is implemented in pure Python.

## Usage Example

```bash
# Get REST server IP
export REST_IP=$(gcloud compute instances describe anki-rest-server \
  --zone=us-west1-b \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Upload a text file
curl -F "files=@lecture.txt" -F "user=student" http://$REST_IP:5000/upload

# Response: {"jobs":[{"job_id":"abc-123","filename":"lecture.txt"}]}

# Check status (wait ~5 seconds for processing)
curl http://$REST_IP:5000/status/abc-123

# Download deck when completed
curl http://$REST_IP:5000/download/abc-123 -o deck.csv

# View the deck
cat deck.csv
```

## Repository

Code repo: https://github.com/rexsheikh/dc-final-testing

## Course Lab Connections

- **Lab 5**: VM snapshot-and-clone approach for worker creation
- **Lab 6**: Flask REST API design and manual VM provisioning
- **Lab 7**: Redis queue architecture (LPUSH/BRPOP pattern)

## Performance Characteristics

- **VM Creation**: 15-25 seconds from snapshot
- **Startup Time**: 30-60 seconds (no model loading)
- **Job Processing**: 2-5 seconds per text file
- **Memory Usage**: ~100MB per worker process
- **API Latency**: <100ms for status checks

These metrics are achievable because we avoid heavy ML dependencies.

## Documentation

- **DEPLOYMENT.md**: Complete deployment guide with GCP commands
- **ARCHITECTURE.md**: Design decisions and system architecture
- **QUICK_FIX.md**: Troubleshooting GitHub authentication issues
