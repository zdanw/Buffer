# -*- coding: utf-8 -*-
"""
配置文件 - 优化版（应用工厂模式）

该文件包含系统的所有配置参数，支持多环境配置：
1. Config: 基础配置类
2. DevelopmentConfig: 开发环境配置
3. ProductionConfig: 生产环境配置
4. TestingConfig: 测试环境配置

配置自动从 .env 文件加载环境变量。
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(env_path=".env"):
    """从 .env 文件中加载环境变量"""
    if not os.path.exists(env_path):
        return False
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    os.environ[key] = value
        return True
    except Exception as e:
        print(f"Warning: Failed to load .env file: {e}")
        return False


load_env_file(os.path.join(BASE_DIR, '.env'))


class Config:
    """基础配置类"""
    
    # === 基础路径配置 ===
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
    CHROMA_DB_DIR = os.path.join(DATA_DIR, 'chroma_db')
    LOG_DIR = os.path.join(DATA_DIR, 'logs')
    LOCAL_EMBEDDING_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'qwen3-embedding-0.6b')
    LOGO_FILE_PATH = "https://cdn.jsdelivr.net/gh/zdanw/my-image-bed@main/images/logo.png"
    PRODUCTS_FILE = os.path.join(DATA_DIR, 'products.json')

    # === Buffer平台API配置 ===
    BUFFER_API_TOKEN = os.getenv("BUFFER_API_TOKEN", "")
    BUFFER_API_URL = "https://api.buffer.com"
    BUFFER_REST_API_URL = "https://api.buffer.com/1"

    # === Doubao AI API配置（图片生成）===
    DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
    DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_MODEL_ID = os.getenv("DOUBAO_MODEL_ID", "doubao-seedream-4.5")
    DOUBAO_ASPECT_RATIO = os.getenv("DOUBAO_ASPECT_RATIO", "1:1")

    # === DeepSeek API配置（文本生成）===
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # === AI生成约束配置 ===
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
10. 图片上不得显示任何文件路径、URL地址或版权信息
"""

    # === 相似度和重试配置 ===
    SIMILARITY_THRESHOLD = 0.85
    IMAGE_SIMILARITY_THRESHOLD = 0.85
    MAX_RETRY_ATTEMPTS = 1

    # === 上传文件配置 ===
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_UPLOAD_SIZE_MB = 10

    # === 搜索缓存配置 ===
    SEARCH_CACHE_MAX_SIZE = 100

    # === 安全配置 ===
    CORS_ORIGINS = ["*"]
    API_RATE_LIMIT = "100/hour"
    SECRET_KEY = os.getenv("SECRET_KEY", "buffer-social-publisher-secret-key")

    # === 业务规则配置 ===
    SOURCE_MANUAL = "manual"
    SOURCE_AI = "ai"
    SOURCE_PUBLISHED = "published"

    # === GitHub 图床配置 ===
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USER = os.getenv("GITHUB_USER", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "")
    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
    GITHUB_IMAGE_BED_ENABLED = os.getenv("GITHUB_IMAGE_BED_ENABLED", "false").lower() == "true"
    GITHUB_IMAGE_FOLDER = os.getenv("GITHUB_IMAGE_FOLDER", "images")

    # === 支持的发布平台 ===
    SUPPORTED_PLATFORMS = [
        {"id": "tiktok", "name": "TikTok", "icon": "🎵"},
        {"id": "instagram", "name": "Instagram", "icon": "📷"},
        {"id": "facebook", "name": "Facebook", "icon": "📘"}
    ]

    # === Doubao API 配置 ===
    DOUBAO_DIRECT_URL_SUPPORT = os.getenv("DOUBAO_DIRECT_URL_SUPPORT", "true").lower() == "true"
    
    # === 图片生成配置 ===
    IMAGE_GENERATION_PROMPT = os.getenv("IMAGE_GENERATION_PROMPT", '''
1.给我生成电商宣传图片
2.图片上的文字采用英文，不能出现任何中文字符
3.图片上不允许出现除了Bebcare以外的任何logo
''').strip()


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


class TestingConfig(Config):
    """测试环境配置"""
    DEBUG = False
    TESTING = True
    CHROMA_DB_DIR = os.path.join(Config.DATA_DIR, 'test_chroma_db')


# 配置映射
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}