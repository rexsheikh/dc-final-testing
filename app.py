#!/usr/bin/env python3
"""
Flask REST API for PDF-to-Anki Text Service
Handles file uploads, job status queries, and deck downloads

Design: Lightweight queue-based architecture
- No heavy ML dependencies (TensorFlow, PyTorch, etc.)
- Fast startup: 30-60 seconds vs 5-10 minutes for model loading
- Low memory: ~50MB for REST tier (no models in memory)
"""

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import redis

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'

# Redis connection (update host for Cloud Memorystore)
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload one or more .txt files and enqueue processing jobs
    Returns job IDs for tracking
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    job_ids = []
    errors = []
    
    for file in files:
        if file and allowed_file(file.filename):
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
            
            # Save file
            file.save(filepath)
            
            # Create job metadata
            job_data = {
                'job_id': job_id,
                'filename': filename,
                'filepath': filepath,
                'status': 'queued',
                'created_at': datetime.utcnow().isoformat(),
                'user': request.form.get('user', 'anonymous')
            }
            
            # Store job metadata in Redis
            redis_client.set(f"job:{job_id}", json.dumps(job_data))
            
            # Enqueue job for processing (LPUSH for FIFO with BRPOP)
            redis_client.lpush('job_queue', job_id)
            
            job_ids.append({'job_id': job_id, 'filename': filename})
        else:
            errors.append(f"Invalid file: {file.filename}")
    
    response = {'jobs': job_ids}
    if errors:
        response['errors'] = errors
    
    return jsonify(response), 201


@app.route('/status/<job_id>', methods=['GET'])
def job_status(job_id):
    """
    Query job status by job_id
    Returns: queued, processing, completed, failed
    """
    job_json = redis_client.get(f"job:{job_id}")
    if not job_json:
        return jsonify({'error': 'Job not found'}), 404
    
    job_data = json.loads(job_json)
    return jsonify(job_data)


@app.route('/download/<job_id>', methods=['GET'])
def download_deck(job_id):
    """
    Download the generated Anki CSV deck for a completed job
    """
    job_json = redis_client.get(f"job:{job_id}")
    if not job_json:
        return jsonify({'error': 'Job not found'}), 404
    
    job_data = json.loads(job_json)
    
    if job_data['status'] != 'completed':
        return jsonify({'error': f"Job not completed (status: {job_data['status']})"}), 400
    
    output_path = job_data.get('output_path')
    if not output_path or not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found'}), 404
    
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"{job_data['filename'].rsplit('.', 1)[0]}_deck.csv"
    )


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List all jobs (for debugging/admin)
    Optional query param: user=<username>
    """
    user_filter = request.args.get('user')
    
    # Scan for all job keys (in production, use PostgreSQL instead)
    cursor = 0
    jobs = []
    while True:
        cursor, keys = redis_client.scan(cursor, match='job:*', count=100)
        for key in keys:
            job_json = redis_client.get(key)
            if job_json:
                job_data = json.loads(job_json)
                if not user_filter or job_data.get('user') == user_filter:
                    jobs.append(job_data)
        if cursor == 0:
            break
    
    return jsonify({'jobs': jobs, 'count': len(jobs)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
