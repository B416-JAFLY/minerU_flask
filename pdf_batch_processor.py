import os
import glob
import requests
import json
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import shutil
import time
from datetime import datetime

BASE_URL = os.getenv('FLASK_BASE_URL', 'http://127.0.0.1:5020')

MAX_RETRIES = 3  # 最大重试次数

def log_with_timestamp(message: str):
    """带时间戳的日志输出"""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def rename_files_with_spaces(directory: str):
    """
    检查目录下的 PDF 文件名是否包含空格，若有，则替换为空格并重命名。
    """
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"), recursive=True)
    for file_path in pdf_files:
        file_dir, file_name = os.path.split(file_path)
        if " " in file_name:
            new_file_name = file_name.replace(" ", "_")
            new_file_path = os.path.join(file_dir, new_file_name)
            os.rename(file_path, new_file_path)
            log_with_timestamp(f"重命名文件: {file_path} -> {new_file_path}")

def clear_environment(pdf_path: str):
    """清理与 PDF 文件相关的文件夹"""
    pdf_name = os.path.basename(pdf_path).split(".")[0]
    md_dir = f"md_{pdf_name}"
    img_dir = f"images_{pdf_name}"
    for dir_path in [md_dir, img_dir]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            log_with_timestamp(f"清理文件夹: {dir_path}")

def download_md(file_id: str, md_url: str, pdf_path: str) -> str:
    """
    下载 MD 文件并保存到本地。
    """
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    md_dir = f"md_{pdf_name}"
    os.makedirs(md_dir, exist_ok=True)

    try:
        full_md_url = f"{BASE_URL}{md_url}"
        response = requests.get(full_md_url)
        response.raise_for_status()
        md_file_path = os.path.join(md_dir, f"{pdf_name}.md")
        with open(md_file_path, 'w', encoding='utf-8') as md_file:
            md_file.write(response.text)
        log_with_timestamp(f"MD 文件已保存到 {md_file_path}")
        return md_file_path
    except requests.RequestException as e:
        log_with_timestamp(f"下载 MD 数据失败: {e}")
        raise
    except Exception as e:
        log_with_timestamp(f"保存 MD 文件失败: {e}")
        raise

def process_pdf_with_flask(pdf_path: str) -> list:
    """
    处理 PDF 文件，获取 MD 和图片信息。
    """
    url = f"{BASE_URL}/upload"
    files = {'file': open(pdf_path, 'rb')}
    try:
        response = requests.post(url, files=files)
        response.raise_for_status()
        json_response = response.json()

        if 'images' in json_response and 'md' in json_response:
            md_url = json_response['md']
            image_urls = json_response['images']

            file_id = os.path.basename(pdf_path).split('.')[0]
            download_md(file_id, md_url, pdf_path)
            return download_images(image_urls, pdf_path)
        else:
            error_msg = json_response.get('error', 'Unknown error occurred')
            log_with_timestamp(f"Error: {error_msg}")
            raise Exception(f"Flask 返回错误信息: {error_msg}")
    except requests.RequestException as e:
        log_with_timestamp(f"Failed to process PDF with Flask: {e}")
        raise
    finally:
        files['file'].close()

def download_images(image_urls: list, pdf_path: str) -> list:
    """
    下载图片列表并保存到本地。
    """
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    img_dir = f"images_{pdf_name}"
    os.makedirs(img_dir, exist_ok=True)
    img_list = []
    for i, img_url in enumerate(image_urls):
        try:
            full_img_url = f"{BASE_URL}{img_url}"
            img_response = requests.get(full_img_url)
            img_response.raise_for_status()
            img = Image.open(BytesIO(img_response.content))
            file_name = os.path.basename(urlparse(img_url).path)
            file_path = os.path.join(img_dir, file_name)
            img.save(file_path)
            img_list.append(file_path)
        except requests.RequestException as e:
            log_with_timestamp(f"Failed to download image {img_url}: {e}")
            raise
        except IOError as e:
            log_with_timestamp(f"Failed to save image {img_url}: {e}")
            raise
    return img_list

def process_pdf_with_retry(pdf_path: str):
    """带重试机制的 PDF 处理"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log_with_timestamp(f"正在处理 PDF 文件: {pdf_path} (第 {attempt} 次尝试)")
            process_pdf_with_flask(pdf_path)
            log_with_timestamp(f"处理完成: {pdf_path}")
            return
        except Exception as e:
            log_with_timestamp(f"处理失败: {pdf_path} (第 {attempt} 次尝试)")
            clear_environment(pdf_path)
            if attempt < MAX_RETRIES:
                log_with_timestamp("等待重试...")
                time.sleep(2)
            else:
                log_with_timestamp(f"已达到最大重试次数，放弃处理: {pdf_path}")

def process_all_pdfs_in_directory(directory: str, max_workers: int = 4):
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"), recursive=True)
    if not pdf_files:
        log_with_timestamp("目录中没有找到 PDF 文件。")
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_pdf_with_retry, pdf_files)

if __name__ == "__main__":
    directory = input("请输入包含 PDF 文件的目录路径: ").strip()
    if os.path.isdir(directory):
        rename_files_with_spaces(directory)

        max_threads = input("请输入最大线程数（默认4）: ").strip()
        max_threads = int(max_threads) if max_threads.isdigit() else 4
        process_all_pdfs_in_directory(directory, max_workers=max_threads)
    else:
        log_with_timestamp("输入的路径不是有效目录，请重新输入。")