from flask import Flask, request, jsonify, send_file, redirect, url_for
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

@app.route('/generate', methods=['POST'])
def generate_qr():
    data = request.get_json()
    if not data or 'unique_id' not in data or 'target_url' not in data:
        return jsonify({'error': 'Invalid input. Provide unique_id and target_url.'}), 400

    unique_id = data['unique_id']
    target_url = data['target_url']

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

@app.route('/qr/<unique_id>', methods=['GET'])
def redirect_to_target(unique_id):
    # Look up the target URL from the database
    target_url = get_target_url(unique_id)
    if not target_url:
        return jsonify({'error': 'No target URL found for this QR code'}), 404
    return redirect(target_url)

@app.route('/', methods=['GET'])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Dynamic QR Code Generator</title></head>
    <body>
        <h1>Generate and Manage Dynamic QR Codes</h1>
        <h2>Create a QR Code</h2>
        <form id="qrForm">
            <label for="unique_id">Unique ID:</label>
            <input type="text" id="unique_id" name="unique_id" required>
            <br><label for="target_url">Target URL:</label>
            <input type="url" id="target_url" name="target_url" required>
            <br><button type="button" onclick="generateQR()">Generate QR Code</button>
        </form>
        <div id="result">
            <h3>Your QR Code:</h3>
            <img id="qrImage" src="" alt="QR Code will appear here">
        </div>
        <script>
            async function generateQR() {
                const unique_id = document.getElementById('unique_id').value;
                const target_url = document.getElementById('target_url').value;
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ unique_id: unique_id, target_url: target_url })
                });
                if (response.ok) {
                    const blob = await response.blob();
                    const imgURL = URL.createObjectURL(blob);
                    document.getElementById('qrImage').src = imgURL;
                } else {
                    alert('Error generating QR Code. Check your input.');
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
