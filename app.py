import os
import uuid
import json
import requests
from flask import Flask, render_template, request, jsonify
from vercel_blob import put, list_blobs

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "farmail_cloud_key_99")

DB_FILENAME = "farmail_db.json"

def get_db():
    try:
        # Fetch list of blobs to find the DB URL
        blobs_data = list_blobs()
        target = next((b for b in blobs_data.get('blobs', []) if b['pathname'] == DB_FILENAME), None)
        
        if target:
            response = requests.get(target['url'])
            return response.json()
        return {"users": {}, "messages": []}
    except Exception:
        return {"users": {}, "messages": []}

def save_db(data):
    # 'add_random_suffix': 'false' is critical to keep the filename consistent
    put(DB_FILENAME, json.dumps(data), {"contentType": "application/json", "addRandomSuffix": "false"})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth/<mode>', methods=['POST'])
def handle_auth(mode):
    db = get_db()
    data = request.json
    user_input = data.get('user').lower().strip()
    pwd = data.get('pass')
    email = f"{user_input}@farmail.com" if "@" not in user_input else user_input

    if mode == 'signup':
        if email in db['users']:
            return jsonify({"success": False, "error": "Email taken"}), 400
        db['users'][email] = {"password": pwd}
        save_db(db)
        return jsonify({"success": True, "email": email})
    else:
        if email in db['users'] and db['users'][email]['password'] == pwd:
            return jsonify({"success": True, "email": email})
        return jsonify({"success": False, "error": "Login failed"}), 401

@app.route('/api/send', methods=['POST'])
def send_email():
    db = get_db()
    sender = request.form.get('sender')
    to = request.form.get('to').lower().strip()
    subject = request.form.get('subject')
    body = request.form.get('body')
    
    file_url, file_name = None, None
    if 'file' in request.files:
        f = request.files['file']
        if f.filename != '':
            file_name = f.filename
            blob = put(f"uploads/{uuid.uuid4()}-{file_name}", f.read(), {"access": "public"})
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
def mark_read(msg_id):
    db = get_db()
    for m in db['messages']:
        if m['id'] == msg_id:
            m['read'] = True
            break
    save_db(db)
    return jsonify({"success": True})

# This is required for Vercel to recognize the app object
app = app
