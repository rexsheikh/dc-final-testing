#!/usr/bin/env python3
"""
NLP Worker Process for PDF-to-Anki Service
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
from nlp import process_pipeline, DeckAssembler

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))

# Redis connection (update for Cloud Memorystore)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

OUTPUT_FOLDER = '/tmp/outputs'
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in Redis"""
    job_json = redis_client.get(f"job:{job_id}")
    if job_json:
        job_data = json.loads(job_json)
        job_data['status'] = status
        job_data['updated_at'] = datetime.utcnow().isoformat()
        job_data.update(kwargs)
        redis_client.set(f"job:{job_id}", json.dumps(job_data))


def process_text_file(filepath: str, job_id: str) -> str:
    """
    Process text file through lightweight NLP pipeline:
    1. Text normalization (regex-based)
    2. Summarization (extractive, word frequency)
    3. TF-IDF keyword extraction (manual calculation)
    4. Named entity recognition (pattern-based)
    5. Generate Anki CSV deck
    
    Total processing time: 2-5 seconds (no ML frameworks)
    Returns path to output CSV file
    """
    print(f"Processing file: {filepath}")
    
    # Read input text
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Run NLP pipeline (lightweight, pure Python)
    filename = os.path.basename(filepath)
    results = process_pipeline(text, filename)
    
    # Generate output CSV
    output_path = os.path.join(OUTPUT_FOLDER, f"{job_id}_deck.csv")
    DeckAssembler.write_csv(results['cards'], output_path)
    
    print(f"Generated deck with {len(results['cards'])} cards: {output_path}")
    return output_path


def worker_loop():
    """Main worker loop: BRPOP from queue, process jobs"""
    print("Worker started, waiting for jobs...")
    
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
            filepath = job_data['filepath']
            
            # Update status to processing
            update_job_status(job_id, 'processing', started_at=datetime.utcnow().isoformat())
            
            # Process the file
            try:
                output_path = process_text_file(filepath, job_id)
                update_job_status(
                    job_id,
                    'completed',
                    output_path=output_path,
                    completed_at=datetime.utcnow().isoformat()
                )
                print(f"Job {job_id} completed successfully")
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
