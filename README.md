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
                "/download/cab31e26-a581-4a19-9ea5-037f1cf62bb8/9d23c0f11167aadb6dae34f59e58ed7d705ae8b68f5585ebc8795b8bc6693b3e.jpg",
                "/download/cab31e26-a581-4a19-9ea5-037f1cf62bb8/39ac92725c835dae36f776498b30ffefaa564403c318f8bdc8d708a6c019d2af.jpg",
                "/download/cab31e26-a581-4a19-9ea5-037f1cf62bb8/483cb11d21e10cac152a41f8d07fe4c18edc95b8ec890e4827a7d3d32afd1398.jpg"
            ]
        }
      ```
      

3. **下载图像接口 `/download/<file_id>/<filename>`**

    - **请求方式**：`GET`
    - **描述**：根据文件 ID 和图像文件名提供下载链接。
    
    - **请求参数**：
      - `file_id`：上传 PDF 时生成的唯一 ID
      - `filename`：图片文件名（例如：`figure1.jpg`）
    
    - **返回示例**：
      - 返回图片文件：图片数据
