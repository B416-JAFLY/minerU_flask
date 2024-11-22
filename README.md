# minerU_flask
基于Flask和Celery为minerU搭建API服务

### 部署方法

1. **安装环境**：
    - 使用conda管理依赖：
      ```bash
      conda env create -f environment.yml
      conda activate mineru
      ```
    - 检查mineru版本：
      ```bash
      magic-pdf --version
      ```
    - mineru版本应为0.9.3，如果不是，需要参考[这里](https://github.com/opendatalab/MinerU/blob/master/docs/README_Ubuntu_CUDA_Acceleration_zh_CN.md)安装：
      ```bash
      pip install -U magic-pdf[full] --extra-index-url https://wheels.myhloli.com -i https://mirrors.aliyun.com/pypi/simple
      ```

2. **启动应用**：
    - 服务端
      ```bash
      python app.py
      ```
    - 消息队列
      ```bash
      docker run -p 6379:6379 redis
      ```     
    - 在celery_tasks.py填写服务端与消息队列的地址：
      ```python
      app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')
      flask_server_url ='http://localhost:5020/results_upload'
      ```
    - 启动分布式celery worker：
      ```bash
      sudo celery -A celery_tasks worker --loglevel=info
      ```
---
### API 用法

1. **主页接口 `/`**

    - **请求方式**：`GET`
    - **描述**：确认一下服务器是否搭建成功。

    - **返回示例**：
      ```html
      <html>
          <head><title>Welcome to DeepFigures API</title></head>
          <body>
              <h1>Welcome to DeepFigures API</h1>
              <p>This is a simple Flask application for processing PDF files containing figures.</p>
              <p>You can upload a PDF file, and the system will extract images and provide download links.</p>
              <p>To get started, use the /upload endpoint to upload a PDF.</p>
          </body>
      </html>
      ```

2. **文件上传接口 `/upload`**

    - **请求方式**：`POST`
    - **描述**：上传一个 PDF 文件，系统会提取其中的图像，并返回图像的下载链接,以及图像对应的标题的.json文件。
    
    - **请求参数**：
      - `file`：PDF 文件（必填）

    - **返回示例**：
      ```json
        {
          "images": [
              "/download/416a0eff-638c-41bc-aeb6-9e958c8838a9/86017a6aff5535bc2e188e14cc5f10ad6795938dbf546fbd7bdd51f1004ed2ec.jpg",
              "/download/416a0eff-638c-41bc-aeb6-9e958c8838a9/d2bc63122929dc94c3dac3442055728346c062c1f23588af8981026336d77357.jpg"
          ],
          "md": "/download/416a0eff-638c-41bc-aeb6-9e958c8838a9/416a0eff-638c-41bc-aeb6-9e958c8838a9.md"
        }
      ```
      

3. **下载文件接口 `/download/<file_id>/<filename>`**

    - **请求方式**：`GET`
    - **描述**：根据文件 ID 和文件名提供下载链接。
    
    - **请求参数**：
      - `file_id`：上传 PDF 时生成的唯一 ID
      - `filename`：文件名（例如：`figure1.jpg`，`file.md`）
    
    - **返回示例**：
      - 返回文件：图片数据或markdown文件
      
---

### 批量处理 PDF 文件

脚本 `pdf_batch_process.py` 用于批量处理 PDF 文件。

#### 运行

```bash
python pdf_batch_process.py
```

#### 输出

- 提取的 Markdown 文件保存在 `md_` 开头的文件夹中。
- 提取的图片保存在 `images_` 开头的文件夹中。

