import os
import sys
import bluetooth
import threading
from flask import Flask, render_template, request, send_from_directory
import qrcode
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QObject, pyqtSignal

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
FILES_DIR = os.path.join(os.path.expanduser('~'), 'BluetoothFileTransfer')
os.makedirs(FILES_DIR, exist_ok=True)

class BluetoothServer(QObject):
    signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.server_sock = None
        self.client_sock = None
        self.running = False
    
    def start_server(self):
        self.running = True
        self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.server_sock.bind(("", bluetooth.PORT_ANY))
        self.server_sock.listen(1)
        port = self.server_sock.getsockname()[1]
        
        bluetooth.advertise_service(
            self.server_sock,
            "FileTransferService",
            service_id="00001101-0000-1000-8000-00805F9B34FB",
            service_classes=["00001101-0000-1000-8000-00805F9B34FB"],
            profiles=[bluetooth.SERIAL_PORT_PROFILE]
        )
        
        self.signal.emit(f"⚡ Bluetooth server started on port {port}\nWaiting for connection...")
        
        try:
            self.client_sock, client_info = self.server_sock.accept()
            self.signal.emit(f"📱 Connected to {client_info[0]}")
            
            while self.running:
                data = self.client_sock.recv(1024)
                if not data:
                    break
                # Handle file transfer here
                
        except Exception as e:
            self.signal.emit(f"❌ Error: {str(e)}")
        finally:
            self.stop_server()
    
    def stop_server(self):
        self.running = False
        if self.client_sock:
            self.client_sock.close()
        if self.server_sock:
            self.server_sock.close()
        self.signal.emit("🔴 Server stopped")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/files')
def list_files():
    files = [f for f in os.listdir(FILES_DIR) if os.path.isfile(os.path.join(FILES_DIR, f))]
    return render_template('files.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(FILES_DIR, filename, as_attachment=True)

def create_tray_app():
    app_qt = QApplication(sys.argv)
    
    # Create tray icon
    tray = QSystemTrayIcon()
    tray.setIcon(QIcon(os.path.join('static', 'icon.png')))
    tray.setVisible(True)
    
    # Create menu
    menu = QMenu()
    action_open = menu.addAction("Open")
    action_exit = menu.addAction("Exit")
    tray.setContextMenu(menu)
    
    # Start Bluetooth server
    bt_server = BluetoothServer()
    bt_thread = threading.Thread(target=bt_server.start_server)
    bt_thread.daemon = True
    bt_thread.start()
    
    # Start Flask server in separate thread
    flask_thread = threading.Thread(target=lambda: app.run(port=5000))
    flask_thread.daemon = True
    flask_thread.start()
    
    sys.exit(app_qt.exec_())

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Start the application
    create_tray_app()