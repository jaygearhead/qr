# test persisten db #2
from flask import Flask, request, jsonify, send_file, redirect, render_template_string, url_for
import qrcode
from io import BytesIO
import sqlite3
import os

app = Flask(__name__)

# Database Location
PERSISTENT_STORAGE = os.getenv('PERSISTENT_STORAGE', '.')
DB_FILE = os.path.join(PERSISTENT_STORAGE, 'qr_codes.db')

# Initialize the Database
def init_db():
    if not os.path.exists(DB_FILE):
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

# Get All QR Codes
def get_all_qr_codes():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, unique_id, target_url FROM qr_codes')
    results = cursor.fetchall()
    conn.close()
    return [{'id': row[0], 'unique_id': row[1], 'target_url': row[2]} for row in results]

# Get Target URL for a Given Unique ID
def get_target_url(unique_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT target_url FROM qr_codes WHERE unique_id = ?', (unique_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Set Target URL for a Given Unique ID
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

# Delete QR Code
def delete_qr_code(unique_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM qr_codes WHERE unique_id = ?', (unique_id,))
    conn.commit()
    conn.close()

# Generate QR Code
@app.route('/generate', methods=['POST'])
def generate_qr():
    data = request.get_json()
    if not data or 'unique_id' not in data or 'target_url' not in data:
        return jsonify({'error': 'Invalid input. Provide unique_id and target_url.'}), 400

    unique_id = data['unique_id']
    target_url = data['target_url']

    if not target_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL. Include http:// or https://'}), 400

    set_target_url(unique_id, target_url)
    redirect_url = request.host_url + 'qr/' + unique_id
    qr = qrcode.QRCode()
    qr.add_data(redirect_url)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

# Redirect to Target URL
@app.route('/qr/<unique_id>', methods=['GET'])
def redirect_to_target(unique_id):
    target_url = get_target_url(unique_id)
    if not target_url:
        return jsonify({'error': 'No target URL found for this QR code'}), 404
    return redirect(target_url)

# List QR Codes
@app.route('/list', methods=['GET'])
def list_qr_codes():
    qr_codes = get_all_qr_codes()
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>QR Code List</title>
    </head>
    <body>
        <h1>All QR Codes</h1>
        <a href="/">Back to Home</a>
        <table border="1">
            <tr>
                <th>Unique ID</th>
                <th>Target URL</th>
                <th>Actions</th>
            </tr>
            {% for qr in qr_codes %}
            <tr>
                <td>{{ qr.unique_id }}</td>
                <td>{{ qr.target_url }}</td>
                <td>
                    <button onclick="editQR('{{ qr.unique_id }}')">Edit</button>
                    <button onclick="deleteQR('{{ qr.unique_id }}')">Delete</button>
                </td>
            </tr>
            {% endfor %}
        </table>
        <script>
            async function editQR(unique_id) {
                const newURL = prompt("Enter new URL for " + unique_id);
                if (newURL) {
                    const response = await fetch(`/edit/${unique_id}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ target_url: newURL })
                    });
                    if (response.ok) {
                        const result = await response.json();
                        alert(result.message);
                        window.location.reload();
                    } else {
                        alert('Error updating QR code.');
                    }
                }
            }
            async function deleteQR(unique_id) {
                if (confirm("Are you sure you want to delete " + unique_id + "?")) {
                    await fetch(`/delete/${unique_id}`, { method: 'POST' });
                    window.location.reload();
                }
            }
        </script>
    </body>
    </html>
    ''', qr_codes=qr_codes)

# Edit QR Code
@app.route('/edit/<unique_id>', methods=['POST'])
def edit_qr_code(unique_id):
    data = request.get_json()
    if not data or 'target_url' not in data:
        return jsonify({'error': 'Invalid input. Provide a new target_url.'}), 400

    target_url = data['target_url']
    if not target_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL. Include http:// or https://'}), 400

    set_target_url(unique_id, target_url)
    return jsonify({'message': f'QR code for {unique_id} updated successfully.'}), 200

# Home Page
@app.route('/', methods=['GET'])
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>QR Code Generator</title>
    </head>
    <body>
        <h1>QR Code Generator</h1>
        <form id="qrForm">
            <label for="unique_id">Unique ID:</label>
            <input type="text" id="unique_id" name="unique_id" required>
            <label for="target_url">Target URL:</label>
            <input type="url" id="target_url" name="target_url" required>
            <button type="button" onclick="generateQR()">Generate QR Code</button>
        </form>
        <h2><a href="/list">View All QR Codes</a></h2>
        <div id="result">
            <h3>Your QR Code:</h3>
            <img id="qrImage" style="display:none;" alt="QR Code">
        </div>
        <script>
            async function generateQR() {
                const unique_id = document.getElementById('unique_id').value;
                const target_url = document.getElementById('target_url').value;
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ unique_id, target_url })
                });
                if (response.ok) {
                    const blob = await response.blob();
                    const imgURL = URL.createObjectURL(blob);
                    const qrImage = document.getElementById('qrImage');
                    qrImage.src = imgURL;
                    qrImage.style.display = 'block';
                } else {
                    alert('Error generating QR Code.');
                }
            }
        </script>
    </body>
    </html>
    '''

# Initialize Database
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
