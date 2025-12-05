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
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import redis

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

shared_root = os.environ.get('SHARED_STORAGE_ROOT')
default_upload = os.path.join(shared_root, 'uploads') if shared_root else '/tmp/uploads'
default_output = os.path.join(shared_root, 'outputs') if shared_root else '/tmp/outputs'
app.config['UPLOAD_FOLDER'] = os.environ.get('SHARED_UPLOAD_FOLDER', default_upload)
app.config['OUTPUT_FOLDER'] = os.environ.get('SHARED_OUTPUT_FOLDER', default_output)

# Redis connection (update host for Cloud Memorystore)
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def fetch_jobs(user_filter=None, limit=None):
    """Utility to collect job metadata from Redis."""
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
    jobs.sort(key=lambda j: j.get('created_at', ''), reverse=True)
    if limit:
        return jobs[:limit]
    return jobs


DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF-to-Anki Text Service</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, Arial, sans-serif; margin: 0; padding: 0; background: #f6f8fb; color: #111; }
    header { background: #1f2933; color: #fff; padding: 1.5rem 1rem; }
    header h1 { margin: 0; font-size: 1.6rem; }
    main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
    .card { background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); padding: 1.5rem; margin-bottom: 1.5rem; }
    label { display: block; font-weight: 600; margin-bottom: 0.4rem; }
    input[type="file"], input[type="text"] { width: 100%; padding: 0.55rem; border: 1px solid #cbd5e0; border-radius: 6px; }
    button { background: #2563eb; color: #fff; border: none; border-radius: 6px; padding: 0.6rem 1.2rem; font-size: 1rem; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { padding: 0.5rem; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 0.95rem; }
    th { background: #f8fafc; }
    .status-badge { padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; text-transform: capitalize; }
    .status-queued { background: #fff7ed; color: #c2410c; }
    .status-processing { background: #eef2ff; color: #3730a3; }
    .status-completed { background: #ecfdf5; color: #065f46; }
    .status-failed { background: #fef2f2; color: #b91c1c; }
    .muted { color: #64748b; font-size: 0.9rem; }
    #upload-status { margin-top: 0.6rem; font-size: 0.95rem; }
    .download-link { color: #2563eb; text-decoration: none; font-weight: 600; }
    .download-link:hover { text-decoration: underline; }
    .jobs-empty { text-align: center; padding: 1rem; color: #64748b; }
    code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 0.85rem; background: #f1f5f9; padding: 0.1rem 0.3rem; border-radius: 4px; }
  </style>
</head>
<body>
  <header>
    <h1>PDF-to-Anki Text Service</h1>
    <p class="muted">Upload .txt files to extract complex words and download ready-to-import decks.</p>
  </header>
  <main>
    <section class="card">
      <h2>Upload Text Files</h2>
      <p class="muted">Accepted formats: {{ allowed_ext }}</p>
      <form id="upload-form" enctype="multipart/form-data">
        <label for="files">Choose one or more .txt files</label>
        <input id="files" name="files" type="file" accept=".txt" multiple required />
        <label for="user" class="muted" style="margin-top: 0.8rem;">Optional user label</label>
        <input id="user" name="user" type="text" placeholder="e.g., demo-user" />
        <button id="upload-button" type="submit" style="margin-top: 1rem;">Upload &amp; Process</button>
      </form>
      <div id="upload-status" class="muted"></div>
    </section>

    <section class="card">
      <h2>Recent Jobs</h2>
      <p class="muted">The table refreshes automatically every few seconds. Completed jobs include a download link.</p>
      <table>
        <thead>
          <tr>
            <th>Job ID</th>
            <th>File</th>
            <th>Status</th>
            <th>Created</th>
            <th>Output</th>
          </tr>
        </thead>
        <tbody id="jobs-body">
          {% if jobs %}
            {% for job in jobs %}
              <tr data-job-id="{{ job['job_id'] }}">
                <td><code>{{ job['job_id'] }}</code></td>
                <td>{{ job['filename'] }}</td>
                <td>
                  <span class="status-badge status-{{ job['status'] }}">{{ job['status'] }}</span>
                </td>
                <td class="muted">{{ job.get('created_at', '') }}</td>
                <td>
                  {% if job['status'] == 'completed' %}
                    <a class="download-link" href="/download/{{ job['job_id'] }}">Download deck</a>
                  {% elif job['status'] == 'failed' %}
                    <span class="muted">Failed</span>
                  {% else %}
                    <span class="muted">Processing…</span>
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          {% else %}
            <tr class="jobs-empty"><td colspan="5">No jobs yet. Upload a .txt file to get started.</td></tr>
          {% endif %}
        </tbody>
      </table>
    </section>
  </main>

  <script>
    const jobsBody = document.getElementById('jobs-body');
    const uploadStatus = document.getElementById('upload-status');
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.getElementById('upload-button');

    function statusBadge(status) {
      return `<span class="status-badge status-${status}">${status}</span>`;
    }

    function renderJobs(jobs) {
      if (!jobs.length) {
        jobsBody.innerHTML = '<tr class="jobs-empty"><td colspan="5">No jobs yet. Upload a .txt file to get started.</td></tr>';
        return;
      }
      jobsBody.innerHTML = jobs.map(job => {
        const output = job.status === 'completed'
          ? `<a class="download-link" href="/download/${job.job_id}">Download deck</a>`
          : job.status === 'failed'
            ? '<span class="muted">Failed</span>'
            : '<span class="muted">Processing…</span>';
        return `
          <tr data-job-id="${job.job_id}">
            <td><code>${job.job_id}</code></td>
            <td>${job.filename}</td>
            <td>${statusBadge(job.status)}</td>
            <td class="muted">${job.created_at || ''}</td>
            <td>${output}</td>
          </tr>
        `;
      }).join('');
    }

    async function refreshJobs() {
      try {
        const res = await fetch('/jobs?limit=25');
        const data = await res.json();
        renderJobs(data.jobs || []);
      } catch (err) {
        console.error('Failed to refresh jobs', err);
      }
    }

    uploadForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      uploadBtn.disabled = true;
      uploadStatus.textContent = 'Uploading...';
      const formData = new FormData(uploadForm);
      try {
        const res = await fetch('/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) {
          uploadStatus.textContent = data.error || 'Upload failed';
        } else {
          const jobCount = data.jobs ? data.jobs.length : 0;
          uploadStatus.textContent = `Uploaded ${jobCount} file(s). Tracking ${jobCount} job(s).`;
          uploadForm.reset();
          refreshJobs();
        }
      } catch (err) {
        uploadStatus.textContent = 'Upload failed. Check console/logs.';
        console.error(err);
      } finally {
        uploadBtn.disabled = false;
      }
    });

    const initialJobs = {{ jobs|tojson }};
    renderJobs(initialJobs || []);
    setInterval(refreshJobs, 5000);
  </script>
</body>
</html>
"""


@app.route('/', methods=['GET'])
def index():
    """Simple dashboard for uploading files and monitoring jobs."""
    jobs = fetch_jobs(limit=25)
    return render_template_string(DASHBOARD_TEMPLATE, jobs=jobs, allowed_ext=', '.join(sorted(ALLOWED_EXTENSIONS)))


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
    Optional query params: user=<username>, limit=<n>
    """
    user_filter = request.args.get('user')
    limit = request.args.get('limit', type=int)
    jobs = fetch_jobs(user_filter=user_filter, limit=limit)
    return jsonify({'jobs': jobs, 'count': len(jobs)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
