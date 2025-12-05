#!/usr/bin/env python3
"""
NLP Worker Process for Text-to-Anki Service
Pulls jobs from Redis queue and processes text files through NLP pipeline

Performance characteristics:
- Processing time: 2-5 seconds per file (pure Python, no ML models)
- Memory usage: ~100MB per worker process
- Startup time: <5 seconds (no model loading)
- Suitable for f1-micro VMs (614MB RAM)
"""

import os
import json
import time
import redis
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError
from nlp import flesch_kincaid_analysis, write_complex_word_deck

METADATA_REDIS_URL = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/rest-internal-ip"
METADATA_SHARED_ROOT_URL = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/shared-root"
METADATA_SHARED_UPLOAD_URL = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/shared-upload"
METADATA_SHARED_OUTPUT_URL = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/shared-output"


def _metadata_lookup(url: str) -> str:
    try:
        req = Request(url, headers={"Metadata-Flavor": "Google"})
        with urlopen(req, timeout=2) as resp:
            value = resp.read().decode().strip()
            if value:
                return value
    except URLError:
        return ""
    return ""


def discover_redis_host(default: str = "localhost") -> str:
    """Pick Redis host from env or metadata server."""
    env_host = os.environ.get("REDIS_HOST")
    if env_host:
        return env_host
    ip = _metadata_lookup(METADATA_REDIS_URL)
    return ip or default


def discover_path(env_key: str, metadata_url: str, default: str) -> str:
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    meta_val = _metadata_lookup(metadata_url)
    return meta_val or default


REDIS_HOST = discover_redis_host()
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))

shared_root = discover_path('SHARED_STORAGE_ROOT', METADATA_SHARED_ROOT_URL, '/tmp')
shared_output = discover_path('SHARED_OUTPUT_FOLDER', METADATA_SHARED_OUTPUT_URL,
                              os.path.join(shared_root, 'outputs') if shared_root else '/tmp/outputs')
OUTPUT_FOLDER = shared_output
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Log configuration at startup for debugging
print(f"Worker starting with configuration:", flush=True)
print(f"  REDIS_HOST: {REDIS_HOST}", flush=True)
print(f"  REDIS_PORT: {REDIS_PORT}", flush=True)
print(f"  SHARED_STORAGE_ROOT: {shared_root}", flush=True)
print(f"  SHARED_OUTPUT_FOLDER: {OUTPUT_FOLDER}", flush=True)
print(f"  Environment REDIS_HOST: {os.environ.get('REDIS_HOST')}", flush=True)
print(f"  Environment SHARED_STORAGE_ROOT: {os.environ.get('SHARED_STORAGE_ROOT')}", flush=True)

# Redis connection (update for Cloud Memorystore)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in Redis"""
    job_json = redis_client.get(f"job:{job_id}")
    if job_json:
        job_data = json.loads(job_json)
        job_data['status'] = status
        job_data['updated_at'] = datetime.utcnow().isoformat()
        job_data.update(kwargs)
        redis_client.set(f"job:{job_id}", json.dumps(job_data))


def process_text_content(text: str, filename: str, job_id: str) -> str:
    """
    Process text content through lightweight NLP pipeline:
    1. Text normalization (regex-based)
    2. Summarization (extractive, word frequency)
    3. Flesch-Kincaid complexity analysis
    4. Extract most difficult words for study
    5. Generate Anki CSV deck with complex words only
    
    Total processing time: 2-5 seconds (no ML frameworks)
    Returns path to output CSV file
    """
    print(f"Processing content for file: {filename}", flush=True)
    
    # Run Flesch-Kincaid analysis to extract complex words
    fk_results = flesch_kincaid_analysis(text)
    complex_words = fk_results['complex_words']
    
    print(f"Found {len(complex_words)} complex words (grade level: {fk_results['grade_level']:.1f})", flush=True)
    
    # Generate output CSV with complex words only
    output_path = os.path.join(OUTPUT_FOLDER, f"{job_id}_deck.csv")
    write_complex_word_deck(complex_words, output_path)
    
    print(f"Generated deck with {len(complex_words)} complex words: {output_path}", flush=True)
    return output_path


def worker_loop():
    """Main worker loop: BRPOP from queue, process jobs"""
    print("Worker started, waiting for jobs...", flush=True)
    
    while True:
        try:
            # Blocking pop from Redis queue (30s timeout)
            result = redis_client.brpop('job_queue', timeout=30)
            
            if result is None:
                print("No jobs in queue, waiting...")
                continue
            
            _, job_id = result
            print(f"\nProcessing job: {job_id}")
            
            # Get job metadata
            job_json = redis_client.get(f"job:{job_id}")
            if not job_json:
                print(f"Job {job_id} metadata not found, skipping")
                continue
            
            job_data = json.loads(job_json)
            filename = job_data['filename']
            file_content = job_data.get('file_content')
            
            if not file_content:
                print(f"Job {job_id} missing file_content in metadata, skipping", flush=True)
                update_job_status(job_id, 'failed', error='Missing file content in job metadata')
                continue
            
            # Update status to processing
            update_job_status(job_id, 'processing', started_at=datetime.utcnow().isoformat())
            
            # Process the file content
            try:
                output_path = process_text_content(file_content, filename, job_id)
                
                # Read output CSV content to store in Redis
                with open(output_path, 'r', encoding='utf-8') as f:
                    output_content = f.read()
                
                update_job_status(
                    job_id,
                    'completed',
                    output_path=output_path,
                    output_content=output_content,  # Store CSV content in Redis
                    completed_at=datetime.utcnow().isoformat()
                )
                print(f"Job {job_id} completed successfully", flush=True)
            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
                update_job_status(
                    job_id,
                    'failed',
                    error=str(e),
                    failed_at=datetime.utcnow().isoformat()
                )
        
        except KeyboardInterrupt:
            print("\nWorker shutting down...")
            break
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    worker_loop()
