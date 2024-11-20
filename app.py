from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
from celery_tasks import celery_upload_pdf
import base64

app = Flask(__name__)
current_dir = os.getcwd()
FINAL_OUTPUT_FOLDER = os.path.join(current_dir, "./flask_received_images")
# 主页路由，返回简短的介绍
@app.route('/')
def index():
    """
    主页，展示简短的介绍信息。
    """
    return render_template_string("""
        <html>
            <head><title>Welcome to DeepFigures API</title></head>
            <body>
                <h1>Welcome to DeepFigures API</h1>
                <p>This is a simple Flask application for processing PDF files containing figures.</p>
                <p>You can upload a PDF file, and the system will extract images and provide download links.</p>
                <p>To get started, use the /upload endpoint to upload a PDF.</p>
            </body>
        </html>
    """)

@app.route('/upload', methods=['POST'])
def upload_pdf():
    try:
        # 获取文件并转为 base64 编码
        file = request.files['file']
        file_content = file.read()
        file_base64 = base64.b64encode(file_content).decode('utf-8')

        # 调用 Celery 任务并传递 base64 编码文件
        result = celery_upload_pdf.apply_async(args=[file_base64])
        result_json, result_code = result.get()

    except Exception as e:
        print("Exception occurred:", e)
        result_json = {"error": str(e)}
        result_code = 500

    return jsonify(result_json), result_code

@app.route('/download/<file_id>/<filename>', methods=['GET'])
def download_image(file_id, filename):
    """
    提供下载处理后图像的 API 端点。
    
    根据文件 ID 和文件名返回处理后的 PNG 图片。
    
    :param file_id: 文件的唯一 ID
    :param filename: 图片文件名
    :return: 图片文件或错误信息
    """
    # 构建图片的存储路径
    target_dir = os.path.join(FINAL_OUTPUT_FOLDER, file_id)
    
    # 检查图片文件是否存在
    if os.path.exists(os.path.join(target_dir, filename)):
        # 使用 Flask 的 `send_from_directory` 函数发送文件
        return send_from_directory(target_dir, filename)
    else:
        # 如果文件不存在，返回 404 错误
        return jsonify({"error": "File not found"}), 404
    
@app.route('/download/<file_id>/processed_figures.json', methods=['GET'])
def download_json(file_id):
    """
    提供下载处理后的 JSON 文件的 API 端点。
    
    :param file_id: 文件的唯一 ID
    :return: JSON 文件或错误信息
    """
    # 构建处理后的 JSON 文件路径
    json_file_path = os.path.join(FINAL_OUTPUT_FOLDER, file_id, 'processed_figures.json')
    
    # 检查 JSON 文件是否存在
    if os.path.exists(json_file_path):
        # 使用 Flask 的 `send_from_directory` 函数发送文件
        return send_from_directory(os.path.dirname(json_file_path), 'processed_figures.json')
    else:
        # 如果文件不存在，返回 404 错误
        return jsonify({"error": "JSON file not found"}), 404

@app.route('/results_upload', methods=['POST'])
def receive_file_result():

    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    
    # 获取 fileid 参数
    fileid = request.form.get('fileid')  # 从 form 数据中获取 fileid
    
    if not fileid:
        return 'No fileid provided', 400

    # 根据 fileid 创建文件夹
    upload_folder = os.path.join(FINAL_OUTPUT_FOLDER, fileid)  # 使用 fileid 构建文件夹路径
    os.makedirs(upload_folder, exist_ok=True)
    
    # 保存文件到对应的文件夹
    file.save(os.path.join(upload_folder, file.filename))
    
    return 'File uploaded successfully', 200

if __name__ == '__main__':
    # 启动 Flask 应用
    app.run(debug=False, host='0.0.0.0', port=5020, threaded=True)