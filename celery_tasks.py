from flask import request
from celery  import Celery
import os
import uuid
import subprocess
import shutil
from werkzeug.utils import secure_filename
import json
import sys
import requests
import base64

# 创建一个Celery实例，并指定消息代理（broker）为Redis
app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')
flask_server_url ='http://192.168.1.110:5020/results_upload'

def upload_folder(folder_path, fileid):
    # 遍历文件夹并上传每个文件
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            
            with open(file_path, 'rb') as f:
                # 使用 data 传递 fileid，files 上传文件
                files = {'file': f}
                data = {'fileid': fileid}  # 添加 fileid 信息
                response = requests.post(flask_server_url, files=files, data=data)
                print(response.status_code, response.text)

# 打印检查
current_dir = os.path.dirname(os.path.abspath(__file__))
target_path = os.path.join(current_dir, 'workspaces/deepfigures-open')
sys.path.append(os.path.join(target_path))
import cut_images as cut

# 默认目录路径
PATH_CONFIG = {
    "UPLOAD_FOLDER": "./uploads",
    "OUTPUT_FOLDER": "./workspaces/deepfigures-open/output",
    "FINAL_OUTPUT_FOLDER": "./celery_worker_processed_images"
}

# 获取当前工作目录
current_dir = os.getcwd()

# 将相对路径拼接为绝对路径
UPLOAD_FOLDER = os.path.join(current_dir, PATH_CONFIG["UPLOAD_FOLDER"])
OUTPUT_FOLDER = os.path.join(current_dir, PATH_CONFIG["OUTPUT_FOLDER"])
FINAL_OUTPUT_FOLDER = os.path.join(current_dir, PATH_CONFIG["FINAL_OUTPUT_FOLDER"])

# 创建必要的文件夹（如果不存在则创建）
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FINAL_OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    """
    检查文件的扩展名是否为允许的类型（只允许 PDF 文件）。
    
    :param filename: 上传文件的文件名
    :return: 如果文件是 PDF 格式返回 True，否则返回 False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def get_first_subdirectory(directory):
    """
    获取指定目录中的第一个子目录。
    
    :param directory: 待查找的父目录
    :return: 第一个子目录的路径，如果没有找到则返回 None
    """
    for subdir in os.listdir(directory):
        subdir_path = os.path.join(directory, subdir)
        if os.path.isdir(subdir_path):
            return subdir_path
    return None

def move_images_to_final_folder(source_dir, dest_dir, file_id):
    """
    将 source_dir 中的 PNG 图片移动到 dest_dir，保存在以 UUID 命名的子目录中。

    :param source_dir: 源目录，包含处理后的图片
    :param dest_dir: 目标目录，保存图片的最终目录
    :param file_id: 用于命名目标目录的 UUID
    :return: 移动的图片文件名列表
    """
    # 创建以 UUID 命名的目标子目录
    target_dir = os.path.join(dest_dir, file_id)
    os.makedirs(target_dir, exist_ok=True)

    # 移动 PNG 图片并返回图片文件名列表
    moved_images = []
    for file in os.listdir(source_dir):
        if file.endswith('.png'):
            source_file = os.path.join(source_dir, file)
            target_file = os.path.join(target_dir, file)
            shutil.move(source_file, target_file)
            moved_images.append(file)
    
    return moved_images


def process_json_file(json_file_path, file_id, dest_dir):
    """
    处理 JSON 文件，只保留 "regionless-captions" 中的每一项并移除 "boundary"。
    
    :param json_file_path: 原始 JSON 文件路径
    :param file_id: 文件的唯一 ID
    :param dest_dir: 目标目录
    :return: 处理后的 JSON 文件路径
    """
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    # 只保留 regionless-captions 中的每一项，并去掉 "boundary"
    if 'regionless-captions' in data:
        # 创建一个新的列表来存储更新后的 captions
        updated_captions = []
        for caption in data['regionless-captions']:
            # 移除 "boundary" 键
            updated_caption = {key: value for key, value in caption.items() if key != 'boundary'}
            updated_captions.append(updated_caption)
        
        # 更新 data 字典中的 regionless-captions 键对应的值
        data['regionless-captions'] = updated_captions
    
    # 生成处理后的 JSON 文件路径
    target_json_path = os.path.join(dest_dir, file_id, 'processed_figures.json')
    
    # 创建以 UUID 命名的目标子目录（如果不存在）
    os.makedirs(os.path.join(dest_dir, file_id), exist_ok=True)

    # 保存处理后的 JSON 文件
    with open(target_json_path, 'w') as f:
        json.dump(data, f, indent=4)

    return target_json_path

def clear_output_directory(directory):
    """
    清空指定目录及其子目录中的所有内容。
    
    :param directory: 需要清空的目录
    """
    if not os.path.exists(directory):
        print(f"目录 {directory} 不存在")
        return
    
    if not os.access(directory, os.W_OK):
        print(f"没有权限访问目录 {directory}")
        return
    
    try:
        shutil.rmtree(directory)
        print(f"目录 {directory} 已清理")
    except Exception as e:
        print(f"清空目录 {directory} 时出错: {e}")

@app.task
def celery_upload_pdf(file_base64):
    """
    处理 PDF 文件上传的 API 端点。
    
    1. 检查是否有文件上传。
    2. 检查文件是否是 PDF 格式。
    3. 保存文件到 uploads 目录。
    4. 使用 `python manage.py detectfigures` 处理 PDF。
    5. 使用 `cut_images.py` 进一步处理生成的图片。
    6. 返回生成的图片 URL 列表给前端。
    
    :return: JSON 响应，包含生成的图片列表或错误信息。
    """

    # 为文件生成一个唯一的 ID，避免文件名冲突
    file_id = str(uuid.uuid4())
    try:
        # 解码 base64 字符串为文件内容
        file_content = base64.b64decode(file_base64)

        # 保存文件到本地（根据需要选择保存路径）
        pdf_save_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
        with open(pdf_save_path, 'wb') as f:
            f.write(file_content)

    except Exception as e:
        return {"error": str(e)}, 500

    output_path = os.path.join(OUTPUT_FOLDER, file_id)

    # Step 2: 调用 `manage.py detectfigures` 处理 PDF 文件
    try:
        # 构建命令行参数，调用 detectfigures
        detectfigures_command = [
            'python', 'manage.py', 'detectfigures',
            output_path, pdf_save_path
        ]
        # 使用 subprocess 调用命令，指定工作目录为 `deepfigures-open`
        subprocess.run(detectfigures_command, check=True, cwd='./workspaces/deepfigures-open')

    except subprocess.CalledProcessError as e:
        # 如果命令执行失败，返回错误信息
        return {"error": f"Failed to run detectfigures: {str(e)}"}, 500

    # Step 3: 调用 `cut_images.py` 进一步处理生成的图片
    try:
        cut.process_output_directory(output_path)
        cut.process_output_directory(output_path)
    except subprocess.CalledProcessError as e:
        # 如果命令执行失败，返回错误信息
        return {"error": f"Failed to run cut_images: {str(e)}"}, 500

    # Step 4: 查找生成的图片和 JSON 文件
    first_subdir = get_first_subdirectory(output_path)
    if not first_subdir:
        return {"error": "No output directory found after processing"}, 404

    # 检查 pdffigures 子目录是否存在
    pdffigures_dir = os.path.join(first_subdir, 'pdffigures')
    json_file = None
    if os.path.exists(pdffigures_dir):
        for file in os.listdir(pdffigures_dir):
            if file.endswith('.json'):
                json_file = os.path.join(pdffigures_dir, file)
                break

    if json_file:
        # 预处理 JSON 文件
        try:
            processed_json_path = process_json_file(json_file, file_id, FINAL_OUTPUT_FOLDER)
        except Exception as e:
            return {"error": f"Failed to process JSON file: {str(e)}"}, 500

    # Step 5: 检查并移动图片
    images_dir = os.path.join(first_subdir, 'images')
    if not os.path.exists(images_dir):
        return {"error": "No images directory found in output"}, 404

    # Move images to final output folder
    moved_images = move_images_to_final_folder(images_dir, FINAL_OUTPUT_FOLDER, file_id)

    # Step 6: 清理 output 目录
    clear_output_directory(output_path)

    # 构建图片和 JSON 文件的下载 URL 列表
    image_urls = [f"/download/{file_id}/{img}" for img in moved_images]
    json_url = f"/download/{file_id}/processed_figures.json" if json_file else None

    response_data = {"images": image_urls}
    if json_url:
        response_data["json"] = json_url
    # 将图片和 JSON 文件返回给flask服务端
    upload_dir = os.path.join(FINAL_OUTPUT_FOLDER, file_id)
    upload_folder(upload_dir,file_id)

    return response_data, 200


    # 如果文件类型不允许，返回错误信息
    return {"error": "Invalid file type. Only PDF is allowed."}, 400