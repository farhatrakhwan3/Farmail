import os
import uuid
import json
import requests
from flask import Flask, render_template, request, jsonify, session
from vercel_blob import put, list_blobs

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "farmail_default_key_123")

DB_FILENAME = "farmail_db.json"

def get_db():
    """Retrieves the database JSON from Vercel Blob storage."""
    try:
        all_blobs = list_blobs()
        # Find the database file in the list of blobs
        target_blob = next((b for b in all_blobs.get('blobs', []) if b['pathname'] == DB_FILENAME), None)
        
        if target_blob:
            response = requests.get(target_blob['url'])
            return response.json()
        return {"users": {}, "messages": []}
    except Exception:
        return {"users": {}, "messages": []}

def save_db(data):
    """Saves the database JSON back to Vercel Blob."""
    json_data = json.dumps(data)
    # add_random_suffix=False ensures we overwrite the same file
    put(DB_FILENAME, json_data, {"contentType": "application/json", "addRandomSuffix": "false"})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth/<mode>', methods=['POST'])
def handle_auth(mode):
    db = get_db()
    data = request.json
    username = data.get('user').lower().strip()
    password = data.get('pass')
    email = f"{username}@farmail.com" if "@farmail.com" not in username else username

    if mode == 'signup':
        if email in db['users']:
            return jsonify({"success": False, "error": "Username taken"}), 400
        db['users'][email] = {"password": password}
        save_db(db)
        return jsonify({"success": True, "email": email})
    else:
        if email in db['users'] and db['users'][email]['password'] == password:
            return jsonify({"success": True, "email": email})
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route('/api/send', methods=['POST'])
def send_email():
    db = get_db()
    sender = request.form.get('sender')
    to = request.form.get('to').lower().strip()
    subject = request.form.get('subject')
    body = request.form.get('body')
    
    file_url = None
    file_name = None
    
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            file_name = file.filename
            # Upload attachment to Blob
            blob = put(f"attachments/{uuid.uuid4()}-{file_name}", file.read(), {"access": "public"})
            file_url = blob['url']

    db['messages'].append({
        "id": str(uuid.uuid4()),
        "sender": sender,
        "receiver": to,
        "subject": subject,
        "body": body,
        "file_url": file_url,
        "file_name": file_name,
        "read": False
    })
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/messages/<email>')
def get_messages(email):
    db = get_db()
    user_msgs = [m for m in db['messages'] if m['receiver'] == email.lower()]
    return jsonify(user_msgs[::-1])

@app.route('/api/read/<msg_id>', methods=['POST'])
def mark_as_read(msg_id):
    db = get_db()
    for m in db['messages']:
        if m['id'] == msg_id:
            m['read'] = True
            break
    save_db(db)
    return jsonify({"success": True})

# Required for Vercel
app.debug = False