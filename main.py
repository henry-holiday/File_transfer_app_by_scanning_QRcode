import os
import sys
import socket
import qrcode
import logging
import time
from threading import Thread
from flask import Flask, request, send_from_directory, redirect, render_template, url_for

# Initialize Flask app
app = Flask(__name__)

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局缓存变量
_cached_qr_code = None
_last_ip = None

# Configuration
def get_base_path():
    """Get the correct base path for both development and PyInstaller"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # Running in PyInstaller bundle
    return os.path.dirname(os.path.abspath(__file__))  # Running in Python

BASE_DIR = get_base_path()
FILES_DIR = os.path.join(BASE_DIR, 'shared_files')
QR_CODE_DIR = os.path.join(BASE_DIR, 'qr_codes')  # 使用项目目录下的qr_codes文件夹
QR_CODE_FILE = "qr_code.png"

# 确保目录存在
def create_directories():
    """确保必要的目录存在"""
    global QR_CODE_DIR
    try:
        os.makedirs(FILES_DIR, exist_ok=True)
        os.makedirs(QR_CODE_DIR, exist_ok=True)
        logger.info(f"共享文件目录: {FILES_DIR}")
        logger.info(f"QR码目录: {QR_CODE_DIR}")
    except Exception as e:
        logger.error(f"创建目录失败: {e}")
        # 尝试使用临时目录作为回退
        import tempfile
        QR_CODE_DIR = os.path.join(tempfile.gettempdir(), 'qr_codes')
        os.makedirs(QR_CODE_DIR, exist_ok=True)
        logger.warning(f"使用临时目录替代: {QR_CODE_DIR}")

# 创建目录
create_directories()

def get_local_ip():
    """获取本地IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception as e:
        logger.error(f"获取IP地址失败: {e}")
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def optimized_qr_code():
    """优化的QR码生成方法（缓存+异步+简化参数）"""
    global _cached_qr_code, _last_ip
    
    current_ip = get_local_ip()
    url = f"http://{current_ip}:5000"
    
    # 如果IP未变化且缓存存在
    if _last_ip == current_ip and _cached_qr_code is not None:
        return _cached_qr_code[0]
    
    _last_ip = current_ip
    
    # 检查文件是否已存在
    qr_path = os.path.join(QR_CODE_DIR, QR_CODE_FILE)
    if os.path.exists(qr_path):
        file_age = time.time() - os.path.getmtime(qr_path)
        if file_age < 3600:  # 1小时内不重新生成
            _cached_qr_code = (url, qr_path)
            return url
    
    # 异步生成
    def generate():
        try:
            # 使用最快的生成方式
            img = qrcode.make(
                url, 
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2
            )
            img.save(qr_path, optimize=True, quality=85)
            _cached_qr_code = (url, qr_path)
            logger.info(f"QR码已生成并保存到: {qr_path}")
        except Exception as e:
            logger.error(f"后台生成QR码失败: {e}")
    
    # 启动后台线程
    Thread(target=generate, daemon=True).start()
    return url

# 应用启动时预生成QR码
def initialize_qr_code():
    """应用启动时生成初始QR码"""
    qr_path = os.path.join(QR_CODE_DIR, QR_CODE_FILE)
    if not os.path.exists(qr_path):
        logger.info("正在生成初始QR码...")
        optimized_qr_code()  # 使用优化后的方法
    else:
        logger.info("检测到已存在的QR码")

# 在应用启动时调用初始化
initialize_qr_code()

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
            try:
                file.save(filename)
                logger.info(f"文件已保存: {filename}")
            except Exception as e:
                logger.error(f"保存文件失败: {e}")
    
    # 获取QR码URL（会自动处理生成逻辑）
    url = optimized_qr_code()
    
    qr_url = url_for('get_qr_code')
    qr_html = f'<img src="{qr_url}" alt="QR Code" style="max-width: 200px;">'
    return render_template('index.html', qr_html=qr_html)

@app.route('/files')
def list_files():
    try:
        files = [f for f in os.listdir(FILES_DIR) if os.path.isfile(os.path.join(FILES_DIR, f))]
        return render_template('files.html', files=files)
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return render_template('error.html', message="无法读取文件列表")

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(FILES_DIR, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"下载文件失败 {filename}: {e}")
        return render_template('error.html', message="文件下载失败"), 404

@app.route('/qr_code')
def get_qr_code():
    qr_path = os.path.join(QR_CODE_DIR, QR_CODE_FILE)
    if not os.path.exists(qr_path):
        logger.warning("未找到QR码，正在后台生成...")
        optimized_qr_code()  # 触发生成
        # 返回临时占位图像
        return send_from_directory(os.path.join(BASE_DIR, 'static'), 'loading.png', mimetype='image/png')
    try:
        return send_from_directory(QR_CODE_DIR, QR_CODE_FILE)
    except Exception as e:
        logger.error(f"提供QR码失败: {e}")
        return send_from_directory(os.path.join(BASE_DIR, 'static'), 'error.png', mimetype='image/png')

@app.route('/debug')
def debug_info():
    """调试端点，显示路径和状态信息"""
    info = {
        "base_dir": BASE_DIR,
        "files_dir": FILES_DIR,
        "qr_code_dir": QR_CODE_DIR,
        "qr_code_path": os.path.join(QR_CODE_DIR, QR_CODE_FILE),
        "qr_code_exists": os.path.exists(os.path.join(QR_CODE_DIR, QR_CODE_FILE)),
        "is_frozen": getattr(sys, 'frozen', False),
        "current_working_directory": os.getcwd(),
        "cached": _cached_qr_code is not None,
        "last_ip": _last_ip
    }
    return render_template('debug.html', info=info)

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"🖥️  服务器运行在: http://{get_local_ip()}:5000")
    print(f"📁 共享文件目录: {FILES_DIR}")
    print(f"🔳 QR码目录: {QR_CODE_DIR}")
    print(f"🔍 QR码路径: {os.path.join(QR_CODE_DIR, QR_CODE_FILE)}")
    print(f"🔧 调试信息: http://{get_local_ip()}:5000/debug")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=5000)