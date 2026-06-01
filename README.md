# Buffer社交内容发布系统

基于Flask框架构建的社交媒体内容自动化发布系统，集成Chroma向量知识库、Doubao-Seedream-4.5 AI和Buffer API。

---

## 功能特性

| 功能模块 | 说明 |
|----------|------|
| 📚 **图文知识库** | 基于Chroma向量数据库，支持语义搜索 |
| 🤖 **AI内容生成** | 集成Doubao API生成文案和图片 |
| 🚀 **多平台发布** | 支持TikTok、Instagram、Facebook一键发布 |
| ⚡ **两种发布模式** | 全自动模式和半自动模式（预览确认后发布） |
| 🔍 **相似度检测** | 自动检测生成内容与知识库的相似度，避免重复 |
| 📤 **本地图片上传** | 支持上传本地图片到知识库 |

---

## 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Flask | 3.1.x |
| 编程语言 | Python | 3.13 |
| 向量数据库 | Chroma DB | 1.5.9 |
| 前端技术 | HTML5 + JavaScript + CSS3 | - |
| API集成 | Buffer API、Doubao API、DeepSeek API | - |

---

## 项目结构

```
c:\IDE_pro_Buffer/
├── app/                    # 应用代码目录
│   ├── __init__.py         # Flask应用工厂（支持多环境配置）
│   ├── config.py           # 配置管理（多环境支持）
│   ├── api/                # API路由层（蓝图模式）
│   │   ├── __init__.py     # 统一API蓝本定义
│   │   ├── knowledge.py    # 知识库API
│   │   ├── publish.py      # 内容生成与发布API
│   │   ├── products.py     # 产品管理API
│   │   └── utils.py        # 工具API
│   ├── services/           # 业务服务层（无Flask依赖）
│   │   ├── __init__.py
│   │   ├── chroma_service.py   # Chroma向量知识库操作
│   │   ├── buffer_service.py    # Buffer平台API集成
│   │   ├── ai_service.py        # AI内容/图像生成
│   │   ├── github_service.py    # GitHub图床服务
│   │   └── logger.py            # 日志模块
│   ├── static/             # 静态文件
│   │   ├── css/            # 样式文件
│   │   │   └── styles.css
│   │   └── js/             # JavaScript模块
│   │       ├── app.js      # 应用入口
│   │       ├── publish.js  # 内容发布模块
│   │       ├── knowledge.js# 知识库管理模块
│   │       ├── products.js # 产品管理模块
│   │       └── utils.js    # 工具函数模块
│   └── templates/          # HTML模板
│       └── index.html      # 主页面
├── data/                   # 数据目录
│   ├── chroma_db/          # Chroma向量数据库文件
│   ├── uploads/             # 上传图片存储目录
│   ├── logs/                # 日志文件目录
│   └── products.json        # 产品列表配置
├── models/                 # AI模型缓存目录
│   ├── huggingface/        # HuggingFace模型缓存
│   ├── clip-vit-base-patch32/  # CLIP图像模型
│   └── qwen3-embedding-0.6b/   # Qwen3嵌入模型
├── run.py                  # 开发环境启动脚本
├── wsgi.py                 # 生产环境WSGI入口
├── requirements.txt        # Python依赖列表
├── .env.example            # 环境变量示例文件
└── README.md               # 项目说明文档
```

**结构优化说明：**

| 优化点 | 说明 |
|--------|------|
| 🔧 **应用工厂模式** | `app/__init__.py` 中的 `create_app()` 支持多环境配置 |
| 📦 **服务层分离** | `services/` 目录包含纯Python业务逻辑，无Flask依赖 |
| 🗂️ **API模块化** | 使用Flask Blueprint统一管理API路由 |
| 📁 **数据目录集中** | 所有数据文件统一存放在 `data/` 目录 |

---

## 安装与运行

### 步骤1：进入项目目录

```powershell
cd c:\IDE_pro_Buffer
```

### 步骤2：激活虚拟环境

```powershell
.\myenv\Scripts\Activate.ps1
```

> **提示**：如果虚拟环境不存在，请先创建：
> ```powershell
> python -m venv myenv
> .\myenv\Scripts\Activate.ps1
> pip install flask flask-cors chromadb sentence-transformers requests
> ```

### 步骤3：安装依赖

依赖已预安装在虚拟环境中，包含以下包：

| 包名 | 版本 | 用途 |
|------|------|------|
| Flask | 3.1.3 | Web框架 |
| requests | 2.34.2 | HTTP请求 |
| flask-cors | 6.0.2 | 跨域支持 |
| chromadb | 1.5.9 | 向量数据库 |
| sentence-transformers | 5.5.1 | 文本向量化 |

如需手动安装：
```powershell
pip install flask==3.1.3 requests==2.34.2 flask-cors==6.0.2 chromadb==1.5.9 sentence-transformers==5.5.1
```

### 步骤4：配置API密钥

#### 方式A：使用.env文件（推荐）

1. 复制示例文件：
```powershell
Copy-Item .env.example .env
```

2. 编辑 `.env` 文件，填写实际的API密钥：
```powershell
notepad .env
```

#### 方式B：直接设置环境变量

```powershell
$env:BUFFER_API_TOKEN="your-buffer-api-token"
$env:DOUBAO_API_KEY="your-doubao-api-key"
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
```

**环境变量说明：**

| 环境变量 | 说明 | 必填 | 默认值 |
|----------|------|------|--------|
| BUFFER_API_TOKEN | Buffer平台API令牌 | 是 | 空 |
| DOUBAO_API_URL | 豆包图片生成API地址 | 否 | https://ark.cn-beijing.volces.com/api/v3/images/generations |
| DOUBAO_API_KEY | 豆包API密钥 | 是 | 空 |
| DOUBAO_MODEL_ID | 豆包模型ID | 否 | Doubao-Seedream-4.5 |
| DOUBAO_ASPECT_RATIO | 图片宽高比 | 否 | 1:1 |
| DEEPSEEK_API_URL | DeepSeek API地址 | 否 | https://api.deepseek.com/v1 |
| DEEPSEEK_API_KEY | DeepSeek API密钥 | 是 | 空 |
| DEEPSEEK_MODEL | DeepSeek模型名称 | 否 | deepseek-chat |

### 步骤5：启动服务

#### 开发环境
```powershell
python run.py
```

#### 生产环境（使用Gunicorn）
```powershell
gunicorn --workers=4 --bind=0.0.0.0:8000 wsgi:app
```

启动成功后，服务将运行在：**http://127.0.0.1:5000**

---

## API接口文档

### 基础接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/` | GET | 返回前端页面 |
| `/api/config/info` | GET | 获取系统配置信息 |

### 知识库接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/api/search?keyword=xxx` | GET | 语义搜索知识库 |
| `/api/search/suggestions` | GET | 获取搜索建议 |
| `/api/search/field` | GET | 按字段搜索 |
| `/api/search/tag` | GET | 按标签搜索 |
| `/api/entries` | GET | 获取所有知识库条目 |
| `/api/entries` | POST | 新增知识库内容（支持文件上传） |
| `/api/entries/<id>` | PUT | 更新指定条目 |
| `/api/entries/<id>` | DELETE | 删除指定条目 |
| `/api/entries/<id>` | GET | 获取单个条目详情 |

### 内容生成接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/api/generate` | POST | 生成内容（文案+图片） |
| `/api/regenerate` | POST | 重新生成内容（支持单独重作文案或图片） |
| `/api/generate-content` | POST | 仅生成文案内容 |

### 发布接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/api/publish` | POST | 发布到社交平台 |
| `/api/auto_publish` | POST | 全自动发布（搜索→生成→发布） |

### 产品管理接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/api/products` | GET | 获取产品列表 |
| `/api/products` | POST | 添加新产品 |
| `/api/products/<index>` | PUT | 更新指定产品 |
| `/api/products/<index>` | DELETE | 删除指定产品 |

### 工具接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/api/github/upload-history` | GET | 获取GitHub上传历史 |
| `/api/github/latest-upload` | GET | 获取最新上传记录 |
| `/api/utils/convert-github-url` | POST | 转换GitHub URL为CDN地址 |
| `/api/utils/batch-convert-urls` | POST | 批量转换知识库中的GitHub URL |

### 文件访问接口

| 接口路径 | HTTP方法 | 说明 |
|----------|----------|------|
| `/uploads/<filename>` | GET | 访问上传的图片 |

---

## 使用流程

### 一、模式选择

系统提供两种发布模式：

#### 模式1：全自动模式
1. 进入首页后，点击"全自动模式"选项
2. 输入产品关键词进行搜索
3. 选择搜索结果中的产品
4. 系统自动完成：
   - 生成社交媒体文案
   - 生成产品图片
   - 发布到选定平台

#### 模式2：半自动模式
1. 进入首页后，点击"半自动模式"选项
2. 输入产品关键词进行搜索
3. 选择搜索结果中的产品
4. 系统生成内容后，您可以：
   - 预览生成的文案和图片
   - 点击"重新生成文案"修改文案
   - 点击"重新生成图片"修改图片
   - 点击"重新生成全部"同时修改两者
5. 确认满意后点击"发布内容"

### 二、新增知识库内容

**步骤1：填写基本信息**
1. 点击顶部"知识库管理"标签
2. 在"产品名称"下拉框中选择产品（或等待加载后选择）
3. 查看产品描述确认选择正确

**步骤2：生成或填写文案**
1. 点击"✨ 生成文案"按钮，系统自动生成社交媒体文案
2. 或者手动在"文案内容"输入框中填写文案

**步骤3：填写图片提示词**
1. 在"Prompt"输入框中填写图片生成提示词
2. 建议包含：产品名称、品牌、使用场景、风格要求

**步骤4：上传图片**
1. 点击"选择图片"按钮
2. 选择本地图片文件（支持png、jpg、jpeg、gif、webp）
3. 查看图片预览确认

**步骤5：保存到知识库**
1. 点击"添加到知识库"按钮
2. 等待提示"添加成功"

### 三、发布流程

**步骤1：搜索产品**
1. 点击顶部"内容发布"标签
2. 在"输入产品关键词"输入框中输入关键词
3. 点击"搜索产品"按钮

**步骤2：选择产品**
1. 在搜索结果列表中点击想要发布的产品
2. 产品信息会显示在"已选择的产品"区域

**步骤3：选择发布平台**
1. 在平台选择区域勾选要发布的平台
2. 支持选择：TikTok、Instagram、Facebook

**步骤4：设置定时发布（可选）**
1. 勾选"启用定时"复选框
2. 设置发布时间（默认当前时间+1小时）
3. 如果不启用定时，内容将立即发布

**步骤5：执行发布**
- **直接发布知识库内容**：点击"📢 直接发布"按钮（使用知识库已有内容）
- **生成新内容后发布**：点击"🚀 生成新内容"按钮

**步骤6：查看发布结果**
1. 发布完成后，页面会显示发布结果
2. 每个平台的发布状态会单独显示

### 四、产品管理

**添加产品**
1. 点击顶部"产品管理"标签
2. 在"产品名称"输入框中输入产品名称
3. 可选：在"产品描述"输入框中填写产品描述
4. 点击"添加产品"按钮

**编辑产品**
1. 在产品列表中找到要编辑的产品
2. 点击"编辑"按钮
3. 在弹出的模态框中修改产品信息
4. 点击"保存"按钮

**删除产品**
1. 在产品列表中找到要删除的产品
2. 点击"删除"按钮
3. 在确认对话框中点击"确定"

---

## 配置说明

### 配置文件位置

配置文件位于 `app/config.py`，支持多环境配置：

| 配置类 | 说明 |
|--------|------|
| `Config` | 基础配置类 |
| `DevelopmentConfig` | 开发环境配置 |
| `ProductionConfig` | 生产环境配置 |
| `TestingConfig` | 测试环境配置 |

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| SIMILARITY_THRESHOLD | 相似度阈值（0-1），超过此值视为重复 | 0.85 |
| IMAGE_SIMILARITY_THRESHOLD | 图片相似度阈值 | 0.85 |
| MAX_RETRY_ATTEMPTS | API调用最大重试次数 | 1 |
| ALLOWED_IMAGE_EXTENSIONS | 允许上传的图片格式 | {'png', 'jpg', 'jpeg', 'gif', 'webp'} |
| MAX_UPLOAD_SIZE_MB | 最大上传文件大小（MB） | 10 |
| SEARCH_CACHE_MAX_SIZE | 搜索缓存最大条目数 | 100 |
| CORS_ORIGINS | 允许的跨域来源 | ["*"] |
| SUPPORTED_PLATFORMS | 支持的发布平台 | [TikTok, Instagram, Facebook] |

### 环境变量配置

通过 `.env` 文件设置以下环境变量：

| 环境变量 | 说明 |
|----------|------|
| FLASK_ENV | 运行环境：development/production/testing |
| SECRET_KEY | Flask密钥 |
| BUFFER_API_TOKEN | Buffer API令牌 |
| DOUBAO_API_KEY | 豆包API密钥 |
| DEEPSEEK_API_KEY | DeepSeek API密钥 |
| GITHUB_TOKEN | GitHub令牌（图床用） |
| GITHUB_USER | GitHub用户名 |
| GITHUB_REPO | GitHub仓库名 |

---

## 多环境配置

### 开发环境

```powershell
$env:FLASK_ENV="development"
python run.py
```

### 生产环境

```powershell
$env:FLASK_ENV="production"
gunicorn --workers=4 --bind=0.0.0.0:8000 wsgi:app
```

### 测试环境

```powershell
$env:FLASK_ENV="testing"
python -m pytest
```

---

## 知识库数据结构

```json
{
    "id": "uuid-string",
    "产品名称": "Bebcare夜灯",
    "文案内容": "给宝宝最温暖的夜晚陪伴！Bebcare夜灯，柔和暖光，呵护宝宝睡眠。",
    "prompt": "Bebcare品牌夜灯，柔和暖光，婴儿卧室场景，温馨氛围",
    "image_url": "/uploads/xxx-uuid-xxx.png",
    "来源": "manual",
    "标签": ["夜灯", "婴儿", "温馨"],
    "发布次数": 5,
    "创建时间": 1704067200
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 条目的唯一标识 |
| 产品名称 | string | 产品名称 |
| 文案内容 | string | 社交媒体文案内容 |
| prompt | string | 图片生成提示词 |
| image_url | string | 图片URL |
| 来源 | string | 'manual'（手动录入）或 'published'（已发布） |
| 标签 | array | 标签列表（用于分类和搜索） |
| 发布次数 | number | 该条目被发布的次数 |
| 创建时间 | number | Unix时间戳 |

---

## 注意事项

### 首次启动
1. 首次启动时，Chroma数据库会自动初始化
2. 如果 `products.json` 文件不存在，系统会自动创建空文件
3. 数据目录 `data/` 会自动创建（包含 chroma_db、uploads、logs）

### API密钥
1. **Buffer API Token**：需要在Buffer官网申请开发者账号获取
2. **Doubao API Key**：需要在阿里云或火山引擎平台申请
3. **DeepSeek API Key**：需要在DeepSeek官网注册获取

### 图片上传
1. 支持的格式：png、jpg、jpeg、gif、webp
2. 文件名使用UUID自动生成，避免重复
3. 上传的图片存储在 `data/uploads/` 目录

### 定时发布
1. 定时发布时间使用ISO 8601格式
2. 时间必须设置为未来时间
3. 如果设置的时间已过期，系统会立即发布

### 日志
1. 日志文件存储在 `data/logs/app.log`
2. 包含API调用、错误信息、警告等
3. 日志级别可在 `app/services/logger.py` 中配置

---

## 故障排除

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 启动失败：找不到模块 | 虚拟环境未激活 | 运行 `.\\myenv\\Scripts\\Activate.ps1` |
| API调用失败 | 网络问题或API密钥错误 | 检查网络连接和密钥配置 |
| 图片上传失败 | 文件格式不支持 | 确保上传的是支持的图片格式 |
| 发布失败 | Buffer Token无效 | 检查BUFFER_API_TOKEN配置 |
| 搜索结果为空 | 知识库没有数据 | 先添加知识库内容 |
| 模块导入错误 | 路径问题 | 检查导入语句是否正确 |

---

## 更新日志

### v2.0.0（架构优化）
- ✅ 采用Flask应用工厂模式，支持多环境配置
- ✅ 分离API层与业务服务层，降低耦合
- ✅ 集中数据目录（chroma_db、uploads、logs）
- ✅ 使用Blueprint统一管理API路由
- ✅ 添加生产环境WSGI入口（wsgi.py）
- ✅ 统一配置管理（app/config.py）

### v1.0.0
- 初始版本发布
- 支持图文知识库管理
- 集成Doubao AI生成内容
- 支持Buffer多平台发布
- 提供全自动和半自动两种发布模式