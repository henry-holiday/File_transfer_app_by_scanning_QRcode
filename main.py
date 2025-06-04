from flask import Flask, request, send_from_directory, redirect, render_template, send_file, url_for
import os
import socket
import qrcode
from urllib.parse import quote

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
FILES_DIR = os.path.join(os.getcwd(), 'shared_files')
QR_CODE_FILE = "qr_code.png"
os.makedirs(FILES_DIR, exist_ok=True)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_qr_code():
    url = f"http://{get_local_ip()}:5000"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join(app.static_folder, QR_CODE_FILE))
    return url

@app.route('/')
def index():
    return redirect('/upload')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename = os.path.join(FILES_DIR, file.filename)
            file.save(filename)
    
    # Generate QR code if it doesn't exist
    if not os.path.exists(os.path.join(app.static_folder, QR_CODE_FILE)):
        generate_qr_code()
    
    qr_url = url_for('static', filename=QR_CODE_FILE)
    qr_html = f'<img src="{qr_url}" alt="QR Code" style="max-width: 200px;">'
    return render_template('index.html', qr_html=qr_html)

@app.route('/files')
def list_files():
    files = []
    for filename in os.listdir(FILES_DIR):
        if os.path.isfile(os.path.join(FILES_DIR, filename)):
            files.append(filename)
    return render_template('files.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(FILES_DIR, filename, as_attachment=True)

@app.route('/qr_code')
def get_qr_code():
    if not os.path.exists(os.path.join(app.static_folder, QR_CODE_FILE)):
        generate_qr_code()
    return send_from_directory(app.static_folder, QR_CODE_FILE)

if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs(app.static_folder, exist_ok=True)
    
    print(f"\n🖥️  Server running at http://{get_local_ip()}:5000")
    print("📱 Scan the QR code with your phone to access")
    print(f"📁 Shared files directory: {FILES_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)