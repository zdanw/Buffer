# -*- coding: utf-8 -*-
"""
配置文件 - 优化版

该文件包含系统的所有配置参数：
1. API密钥和URL
2. 相似度阈值和重试次数
3. 路径配置
4. 业务规则配置
5. 安全配置

注意：
- 请在使用前填写有效的API密钥
- 敏感信息不应提交到版本控制系统
- 生产环境建议使用环境变量管理敏感配置
"""

import os

# 首先加载 .env 文件中的环境变量
try:
    from app.env_loader import load_env_file
    load_env_file()
except ImportError:
    # 如果导入失败，尝试直接加载
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    except:
        pass

# === 基础路径配置 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
CHROMA_DB_DIR = os.path.join(DATA_DIR, 'chroma_db')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOCAL_EMBEDDING_MODEL_PATH = os.path.join(BASE_DIR, 'qwen3-embedding-0.6b')
LOGO_FILE_PATH = os.path.join(UPLOAD_DIR, 'logo.png')  # 固定logo文件路径

# === Buffer平台API配置 ===
# 从Buffer开发者控制台获取：https://buffer.com/developers/api
# 通过环境变量 BUFFER_API_TOKEN 设置
BUFFER_API_TOKEN = os.getenv("BUFFER_API_TOKEN", "")

# === Doubao AI API配置（图片生成） ===
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
# 通过环境变量 DOUBAO_API_KEY 设置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_MODEL_ID = os.getenv("DOUBAO_MODEL_ID", "doubao-seedream-4.5")
DOUBAO_ASPECT_RATIO = os.getenv("DOUBAO_ASPECT_RATIO", "1:1")  # 可选：1:1, 9:16, 16:9, 4:3, 3:4

# === DeepSeek API配置（文本生成） ===
# 注册地址: https://platform.deepseek.com/
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
# 通过环境变量 DEEPSEEK_API_KEY 设置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# === AI生成约束配置 ===
# 文案生成系统提示词
CONTENT_GENERATION_SYSTEM_PROMPT = """
你是一个专业的社交媒体文案生成助手，专门为Bebcare品牌产品创作吸引人的种草文案，语言采用英文。

要求：
1. 语言生动活泼，适合tiktok、facebook、Instagram等社交平台
2. 突出产品特点
3. 字数控制在100-300字之间
4. 包含相关标签（#hashtag）
5. 保持积极、友好的语气
6. **禁止使用Markdown格式（如**加粗**、##标题等），直接输出纯文本**

多样性要求：
- 每次生成使用不同的写作风格（幽默搞笑、温情治愈、专业测评、故事叙述、实用干货）
- 使用不同的开头方式（提问式、痛点式、惊喜式、悬念式）
- 避免重复的句式结构和表达方式
- 使用多样化的emoji表情，避免单调
"""

# 图片生成强制约束（会自动拼接到prompt末尾）
IMAGE_GENERATION_CONSTRAINTS = """
[重要约束：必须严格遵守]
1. 按照各大电商平台商品宣传图片风格进行生成，风格多样化，避免重复。
2. 图片上的文字必须采用英文
3. 产品主体必须保持不变，产品形态、颜色、功能必须准确
4. 使用提供的Bebcare品牌Logo参考图片进行生成，必须完全按照参考图片中的Logo样式、颜色和形状
5. 合理生成Logo的位置，保持清晰可见
6. 禁止生成TikTok、Instagram、Facebook等任何平台的图标或水印
7. 禁止生成与参考Logo不同的任何品牌标识或商标
8. 保持产品的专业感和高端质感
9. 禁止修改产品的核心设计
10. 风格统一，符合Bebcare品牌调性
11. 图片上不得显示任何文件路径、URL地址或版权信息
"""

# === 相似度和重试配置 ===
SIMILARITY_THRESHOLD = 0.85  # 内容相似度阈值（0-1）
IMAGE_SIMILARITY_THRESHOLD = 0.85  # 图片视觉相似度阈值（0-1）
MAX_RETRY_ATTEMPTS = 1  # 最大重试次数（避免重复生成多次）

# === 上传文件配置 ===
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_UPLOAD_SIZE_MB = 10  # 最大上传文件大小（MB）

# === 搜索缓存配置 ===
SEARCH_CACHE_MAX_SIZE = 100  # 搜索缓存最大容量（LRU策略）

# === 安全配置 ===
CORS_ORIGINS = ["*"]  # 允许的跨域来源
API_RATE_LIMIT = "100/hour"  # API速率限制

# === 业务规则配置 ===

# === 来源枚举 ===
SOURCE_MANUAL = "manual"  # 手动录入
SOURCE_AI = "ai"  # AI自动生成
SOURCE_PUBLISHED = "published"  # 发布后自动入库

# === 支持的发布平台 ===
SUPPORTED_PLATFORMS = [
    {"id": "tiktok", "name": "TikTok", "icon": "🎵"},
    {"id": "instagram", "name": "Instagram", "icon": "📷"},
    {"id": "facebook", "name": "Facebook", "icon": "📘"}
]
