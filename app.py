from flask import Flask, request, jsonify, redirect, url_for, render_template_string
import qrcode
from io import BytesIO
import sqlite3

app = Flask(__name__)

# Initialize SQLite database
DB_FILE = 'qr_codes.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qr_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT UNIQUE,
            target_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_all_ids():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT unique_id, target_url FROM qr_codes')
    results = cursor.fetchall()
    conn.close()
    return results

def get_target_url(unique_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT target_url FROM qr_codes WHERE unique_id = ?', (unique_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_target_url(unique_id, target_url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO qr_codes (unique_id, target_url)
        VALUES (?, ?)
        ON CONFLICT(unique_id) DO UPDATE SET target_url=excluded.target_url
    ''', (unique_id, target_url))
    conn.commit()
    conn.close()

def delete_qr_code(unique_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM qr_codes WHERE unique_id = ?', (unique_id,))
    conn.commit()
    conn.close()

@app.route('/')
def home():
    # Show all unique IDs and their associated URLs
    all_ids = get_all_ids()
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Dynamic QR Code Manager</title></head>
    <body>
        <h1>Dynamic QR Code Manager</h1>
        <h2>Create or Update a QR Code</h2>
        <form action="/generate" method="post">
            <label for="unique_id">Unique ID:</label>
            <input type="text" id="unique_id" name="unique_id" required>
            <br>
            <label for="target_url">Target URL:</label>
            <input type="url" id="target_url" name="target_url" required>
            <br>
            <button type="submit">Create/Update QR Code</button>
        </form>
        <h2>Existing QR Codes</h2>
        <ul>
            {% for unique_id, target_url in all_ids %}
                <li>
                    {{ unique_id }} - {{ target_url }}
                    <a href="/edit/{{ unique_id }}">Edit</a> |
                    <a href="/delete/{{ unique_id }}" onclick="return confirm('Are you sure you want to delete this QR Code?');">Delete</a>
                </li>
            {% endfor %}
        </ul>
    </body>
    </html>
    ''', all_ids=all_ids)

@app.route('/generate', methods=['POST'])
def generate_qr():
    unique_id = request.form.get('unique_id')
    target_url = request.form.get('target_url')

    if not target_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL. Include http:// or https://'}), 400

    # Save mapping to database
    set_target_url(unique_id, target_url)

    # Generate QR Code pointing to the dynamic redirect endpoint
    redirect_url = url_for('redirect_to_target', unique_id=unique_id, _external=True)
    qr = qrcode.QRCode()
    qr.add_data(redirect_url)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    # Return QR Code as an image
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

@app.route('/edit/<unique_id>', methods=['GET', 'POST'])
def edit_qr(unique_id):
    if request.method == 'POST':
        # Update the URL for the specified unique_id
        new_url = request.form.get('target_url')
        if not new_url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Invalid URL. Include http:// or https://'}), 400
        set_target_url(unique_id, new_url)
        return redirect('/')

    # Show current URL for the unique_id
    current_url = get_target_url(unique_id)
    if not current_url:
        return jsonify({'error': f'No QR Code found for ID {unique_id}'}), 404

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Edit QR Code</title></head>
    <body>
        <h1>Edit QR Code for {{ unique_id }}</h1>
        <form method="post">
            <label for="target_url">New URL:</label>
            <input type="url" id="target_url" name="target_url" value="{{ current_url }}" required>
            <br>
            <button type="submit">Update QR Code</button>
        </form>
        <a href="/">Back to Home</a>
    </body>
    </html>
    ''', unique_id=unique_id, current_url=current_url)

@app.route('/delete/<unique_id>', methods=['GET'])
def delete_qr(unique_id):
    delete_qr_code(unique_id)
    return redirect('/')

@app.route('/qr/<unique_id>', methods=['GET'])
def redirect_to_target(unique_id):
    target_url = get_target_url(unique_id)
    if not target_url:
        return jsonify({'error': 'No target URL found for this QR code'}), 404
    return redirect(target_url)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
