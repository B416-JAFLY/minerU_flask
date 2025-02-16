from celery  import Celery
import os
import uuid
import subprocess
import shutil
import json
import sys
import requests
import base64

# 创建一个Celery实例，并指定消息代理（broker）为Redis
# 创建一个Celery实例，并指定消息代理（broker）为Redis
app = Celery(
    'tasks',
    broker='redis://192.168.1.110:6379/0',
    backend='redis://192.168.1.110:6379/0'
)

# 设置任务结果的过期时间为5分钟（300秒）
app.conf.result_expires = 300

flask_server_url ='http://192.168.1.110:5020/results_upload'

# 默认目录路径
PATH_CONFIG = {
    "UPLOAD_FOLDER": "./uploads",
    "OUTPUT_FOLDER": "./mineru_output",
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
        if file.endswith('.jpg'):
            source_file = os.path.join(source_dir, file)
            target_file = os.path.join(target_dir, file)
            shutil.move(source_file, target_file)
            moved_images.append(file)
    
    return moved_images

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

    # 处理 PDF 文件
    try:
        # 构建命令行参数，调用 detectfigures
        detectfigures_command = [
            'magic-pdf', '-p', pdf_save_path, '-o',
            f"{output_path}/.."
        ]
        # 使用 subprocess 调用命令
        subprocess.run(detectfigures_command, check=True, cwd='./')

    except subprocess.CalledProcessError as e:
        # 如果命令执行失败，返回错误信息
        return {"error": f"Failed to run detectfigures: {str(e)}"}, 500

    first_subdir = get_first_subdirectory(output_path)
    if not first_subdir:
        return {"error": "No output directory found after processing"}, 404

    # 在first_subdir下寻找以_content_list.json结尾的文件
    content_list_file = None
    for fname in os.listdir(first_subdir):
        if fname.endswith("_content_list.json"):
            content_list_file = os.path.join(first_subdir, fname)
            break

    if not content_list_file:
        return {"error": "No _content_list.json file found in output directory"}, 404

    # 读取该JSON文件
    with open(content_list_file, 'r') as json_file:
        content_list = json.load(json_file)

    # 创建一个字典，用于跟踪每页的图片计数
    page_image_counter = {}

    for item in content_list:
        if item['type'] == 'image':
            img_path = item.get('img_path')
            page_idx = item.get('page_idx')

            if img_path and page_idx is not None:
                # 初始化当前页的计数器
                if page_idx not in page_image_counter:
                    page_image_counter[page_idx] = 0

                # 获取计数器值并生成文件名
                counter = page_image_counter[page_idx]
                page_image_counter[page_idx] += 1  # 更新计数器

                original_img_path = os.path.join(first_subdir, img_path)
                if os.path.exists(original_img_path):
                    # 保留文件扩展名
                    file_extension = os.path.splitext(img_path)[-1]
                    new_img_name = f"page_{page_idx}_img_{counter}{file_extension}"

                    # 目标目录假定为 "images"
                    images_dir = os.path.join(first_subdir, "images")
                    if not os.path.exists(images_dir):
                        return {"error": "No images directory found in output"}, 404

                    new_img_path = os.path.join(images_dir, new_img_name)
                    os.rename(original_img_path, new_img_path)
    # 检查并移动图片
    images_dir = os.path.join(first_subdir, "images")
    if not os.path.exists(images_dir):
        return {"error": "No images directory found in output"}, 404

    # Move images to final output folder
    moved_images = move_images_to_final_folder(images_dir, FINAL_OUTPUT_FOLDER, file_id)
    
    md_file=None
    for file in os.listdir(first_subdir):
        if file.endswith('.md'):
            md_file = os.path.join(first_subdir, file)
            break

    if md_file:
        target_md_path = os.path.join(FINAL_OUTPUT_FOLDER, file_id)
        shutil.copy(md_file, target_md_path)
    # 清理 output 目录
    clear_output_directory(output_path)

    # 构建图片下载 URL 列表
    image_urls = [f"/download/{file_id}/{img}" for img in moved_images]
    md_url = f"/download/{file_id}/{file_id}.md"

    response_data = {"images": image_urls}
    if md_url:
        response_data["md"] = md_url

    # 将结果返回给flask服务端
    upload_dir = os.path.join(FINAL_OUTPUT_FOLDER, file_id)
    upload_folder(upload_dir,file_id)

    return response_data, 200