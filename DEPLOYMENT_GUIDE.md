# 项目部署指南

本指南详细说明了如何将项目的后端代码部署到 **Railway**，前端代码部署到 **Vercel**。

---

## 目录

1. [前置准备](#前置准备)
2. [后端部署 - Railway](#后端部署---railway)
3. [前端部署 - Vercel](#前端部署---vercel)
4. [环境变量配置](#环境变量配置)
5. [部署验证](#部署验证)

---

## 前置准备

### 1.1 代码仓库准备

确保你的代码已经推送到 GitHub/GitLab 等代码托管平台。

### 1.2 安装必要工具

- **Railway CLI**（可选）：用于本地调试和部署
  ```bash
  npm install -g @railway/cli
  ```

- **Vercel CLI**（可选）：用于本地调试和部署
  ```bash
  npm install -g vercel
  ```

---

## 后端部署 - Railway

### 2.1 创建 Railway 项目

1. 访问 [Railway](https://railway.app/) 并登录
2. 点击 **New Project** -> **Deploy from GitHub repo**
3. 选择你的项目仓库

### 2.2 配置 Railway

#### 2.2.1 添加环境变量

在 Railway 项目的 **Settings** -> **Variables** 中添加以下环境变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `FLASK_ENV` | `production` | 生产环境模式 |
| `FLASK_DEBUG` | `false` | 关闭调试模式 |
| `PORT` | `5000` | 服务端口 |
| `BUFFER_API_TOKEN` | `your-buffer-api-token` | Buffer API 令牌 |
| `DOUBAO_API_KEY` | `your-doubao-api-key` | 豆包 API 密钥 |
| `DEEPSEEK_API_KEY` | `your-deepseek-api-key` | DeepSeek API 密钥 |
| `CORS_ORIGINS` | `https://your-vercel-app.vercel.app` | Vercel 前端域名 |
| `SECRET_KEY` | `your-secret-key` | 应用密钥（随机生成） |

#### 2.2.2 配置构建命令

Railway 会自动检测 `Procfile` 文件。我们已创建了 `Procfile`：

```
web: gunicorn wsgi:app --log-file -
```

如果需要自定义构建命令，可以在 **Settings** -> **Build & Deploy** 中配置：

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn wsgi:app --log-file -`

### 2.3 部署后端

1. 推送代码到 GitHub 仓库
2. Railway 会自动触发部署
3. 部署完成后，Railway 会分配一个域名（如 `your-app.up.railway.app`）

---

## 前端部署 - Vercel

### 3.1 创建 Vercel 项目

1. 访问 [Vercel](https://vercel.com/) 并登录
2. 点击 **New Project** -> **Import** 选择你的项目仓库

### 3.2 配置 Vercel

#### 3.2.1 添加环境变量

在 Vercel 项目的 **Settings** -> **Environment Variables** 中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `API_BASE_URL` | `https://your-railway-app.up.railway.app` | 后端 API 地址 |

#### 3.2.2 配置构建

Vercel 会自动检测静态文件。我们已创建了 `vercel.json` 配置文件：

```json
{
  "builds": [
    {
      "src": "app/static/**/*",
      "use": "@vercel/static"
    },
    {
      "src": "app/templates/index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/app/templates/index.html"
    }
  ],
  "env": {
    "API_BASE_URL": "@api_base_url"
  }
}
```

### 3.3 部署前端

1. 推送代码到 GitHub 仓库
2. Vercel 会自动触发部署
3. 部署完成后，Vercel 会分配一个域名（如 `your-app.vercel.app`）

---

## 环境变量配置

### 完整环境变量列表

#### 后端环境变量（Railway）

```bash
# Flask 配置
FLASK_ENV=production
FLASK_DEBUG=false
PORT=5000
SECRET_KEY=your-random-secret-key

# Buffer API
BUFFER_API_TOKEN=your-buffer-api-token

# 豆包 AI API
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/images/generations
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_MODEL_ID=Doubao-Seedream-4.5
DOUBAO_ASPECT_RATIO=1:1

# DeepSeek API
DEEPSEEK_API_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-chat

# CORS 配置
CORS_ORIGINS=https://your-vercel-app.vercel.app

# GitHub 图床（可选）
GITHUB_IMAGE_BED_ENABLED=false
GITHUB_TOKEN=your-github-token
GITHUB_USER=your-github-username
GITHUB_REPO=your-repo-name
GITHUB_BRANCH=main
GITHUB_IMAGE_FOLDER=images
```

#### 前端环境变量（Vercel）

```bash
API_BASE_URL=https://your-railway-app.up.railway.app
```

---

## 部署验证

### 验证后端

1. 访问后端地址：`https://your-railway-app.up.railway.app`
2. 应该能看到应用首页
3. 测试 API：`https://your-railway-app.up.railway.app/api/products`

### 验证前端

1. 访问前端地址：`https://your-vercel-app.vercel.app`
2. 应该能看到应用首页
3. 检查浏览器控制台是否有跨域错误

### 测试完整流程

1. 在前端页面搜索产品
2. 选择产品后生成内容
3. 发布到社交平台
4. 检查发布结果

---

## 注意事项

### 1. CORS 配置

确保 Railway 的 `CORS_ORIGINS` 环境变量包含你的 Vercel 域名，格式如下：
```
CORS_ORIGINS=https://your-app.vercel.app
```

### 2. 环境变量敏感信息

- **不要**将敏感信息（如 API 密钥）提交到代码仓库
- 使用平台提供的环境变量管理功能
- 参考 `.env.example` 文件了解所需的环境变量

### 3. Railway 部署问题

如果部署失败，检查：
- Python 版本是否兼容（推荐 Python 3.10+）
- 依赖安装是否成功
- Procfile 配置是否正确

### 4. Vercel 部署问题

如果部署失败，检查：
- vercel.json 配置是否正确
- 静态文件路径是否正确
- 环境变量是否设置正确

---

## 本地开发

### 后端开发

```bash
# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
cp .env.example .env
# 编辑 .env 文件，填入必要的 API 密钥

# 启动开发服务器
python run.py
```

### 前端开发

前端代码已集成在 Flask 应用中，后端启动后即可访问。

---

## 项目结构

```
├── app/                    # Flask 应用目录
│   ├── api/               # API 路由
│   ├── services/          # 业务逻辑服务
│   ├── static/            # 静态文件（CSS、JS、图片）
│   ├── templates/         # HTML 模板
│   ├── __init__.py        # 应用工厂
│   └── config.py          # 配置文件
├── .env.example          # 环境变量示例
├── Procfile              # Railway 部署配置
├── requirements.txt      # Python 依赖
├── run.py                # 开发服务器启动脚本
├── vercel.json           # Vercel 部署配置
└── wsgi.py               # WSGI 入口
```