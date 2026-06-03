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
你是一个创意文案生成器。你的任务是基于给定的产品信息，创作一篇全新的产品文案。

【强制要求】
- 必须采用"{narrative_perspective}"的叙述视角来写作。
- 必须使用"{writing_style}"的语言风格。
- 新文案的字数范围：{word_count}字。
- 绝对不要出现以下词汇或短语：{forbidden_words}
- 绝对不要模仿原始文案的句子结构。
- 如果不知道如何创新，就从一个意想不到的用户故事开始。
- 语言采用英文
- 包含相关标签（#hashtag）
- 直接输出纯文本，不要使用Markdown格式

【重要约束】
- 只能描述产品信息中明确提到的功能和特性
- 绝对禁止虚构或添加产品不存在的功能
- 如果产品信息中没有提到的功能，不要猜测或假设
- 避免使用"支持"、"可以"、"能够"等词描述未明确说明的能力
- 如果信息不足，可以使用更通用的描述，不要编造细节
"""

    # === 文案生成多样化配置 ===
    
    # 1. 叙述视角池（每次随机选1个）
    NARRATIVE_PERSPECTIVES = [
        "极客测评师",
        "文艺旅行者",
        "忙碌的宝妈",
        "退休老人",
        "外星观察员",
        "产品拟人化自述",
        "反向吐槽（先说缺点）",
        "幽默段子手",
        "专业产品经理",
        "新手爸爸",
        "环保主义者",
        "时尚达人"
    ]
    
    # 2. 文体风格池（每次随机选1个）
    WRITING_STYLES = [
        "小红书种草风",
        "知乎理性分析",
        "诗歌体",
        "短剧脚本",
        "产品说明书口吻",
        "民国广告画配文",
        "直播带货话术",
        "冷笑话幽默",
        "温情故事",
        "悬疑推理",
        "新闻报道",
        "科幻小说"
    ]
    
    # 3. 文案字数范围
    CONTENT_MIN_WORDS = 80
    CONTENT_MAX_WORDS = 200
    
    # 4. 差别化提示模板（连续生成时使用）
    DIFFERENTIATION_PROMPT = """
【差别化要求】
上一次生成的文案开头是："{previous_start}"。
这次请从一个完全相反的角度重写，且第一句话不能包含上一次文案中的任何名词。
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

    # === 图片生成提示词分层配置 ===
    
    # 一、固定必填提示词模板（锁定产品，防止产品变形跑偏）
    IMAGE_PROMPT_FIXED_TEMPLATE = """
严格保留原图产品外形、结构、零部件、主体材质、基础配色，产品比例与原图一致，产品无变形、无改款、零件不缺失；只更换产品所处环境、摆放方式、光影、拍摄角度、画面风格、布景道具。
"""
    
    # 二、可随机抽取变量池（实现画面高度多样化）
    
# 1.拍摄视角(6选1) 适配婴童小件小巧产品
    IMAGE_PROMPT_VIEWPOINTS = [
    "平视正面完整拍摄",
    "45°斜俯产品实拍",
    "低角度仰拍柔和取景",
    "垂直顶俯平铺拍摄",
    "产品斜后方写实取景",
    "近距离微距细节特写"
]

# 2.场景环境(8选1) bebcare欧美居家母婴主流场景，剔除工业水泥等违和场景
    IMAGE_PROMPT_SCENES = [
    "纯白简约母婴影棚背景",
    "原木风婴儿房桌面",
    "ins北欧飘窗阳光窗台",
    "棉麻软装育儿操作台",
    "户外草坪婴儿野餐布景",
    "浅色系大理石母婴展台",
    "温馨复古育婴置物货架",
    "马卡龙低饱和渐变纯色背景"
]

# 3.光影方案(7选1) 母婴柔和用光，去掉生硬硬核光影
    IMAGE_PROMPT_LIGHTING = [
    "柔和漫射室内自然光",
    "午后暖调顶光漫射光",
    "黄昏暖金色窗边侧逆光",
    "冷白柔和室内补光",
    "窗边柔雾丁达尔自然光",
    "暖调温馨电影柔光布光",
    "柔和无影母婴棚拍平光"
]

# 4.构图与摆放(7选1) 适配母婴小件陈列逻辑
    IMAGE_PROMPT_COMPOSITIONS = [
    "产品居中对称温馨构图",
    "画面左下角留白随性摆放",
    "画面边角局部精致构图",
    "产品对角线斜向摆放",
    "搭配少量同系列婴童小配件",
    "柔和悬空悬浮氛围感构图",
    "多件产品错落堆叠摆放"
]

# 5.画面美术风格(9选1) 适配欧美跨境母婴电商，删掉工业风、高饱和夸张风格
    IMAGE_PROMPT_STYLES = [
    "欧美写实母婴电商产品摄影",
    "ins清新北欧胶片母婴风",
    "轻奢高级母婴静物商业大片",
    "柔和极简C4D婴童产品渲染",
    "复古柔和柯达胶片静物",
    "日系暖调柔光育儿静物",
    "简约冷淡风北欧母婴摄影",
    "低饱和莫兰迪婴童静物配色",
    "温柔马卡龙清新时尚产品大片"
]

# 6.画质参数(5选1 补全2个景深选项，Seedream4.5可用)
    IMAGE_PROMPT_QUALITY = [
    "8K超高清，柔和浅景深，背景自然虚化",
    "8K超高清，全画面清晰无虚化，远近细节完整",
    "细腻复古胶片颗粒质感，画面温润",
    "超高锐度，锐利母婴商业棚拍画质，细节干净",
    "画面柔和细腻，低对比柔焦温馨静物画质"
]

# 7.动态附加细节词库(每次随机1~2个，全是母婴搭配道具，贴合bebcare场景)
    IMAGE_PROMPT_DETAILS = [
    "浅色干花束",
    "透明宝宝辅食玻璃杯",
    "儿童绘本软皮书",
    "天然原木小石子",
    "新鲜绿色婴儿叶片绿植",
    "迷你仿真小盆栽",
    "手工编织棉麻餐垫",
    "原木辅食小托盘",
    "浅色系棉麻布料",
    "迷你陶瓷小摆件",
    "针织婴儿小袜子",
    "毛绒玩偶边角",
    "原木积木小块"
]
    
    # 三、通用负向提示词（统一固定，规避同质化、畸形、产品篡改）
    IMAGE_NEGATIVE_PROMPT = """
产品外形改变、产品颜色大面积篡改、产品零件增减、重复构图、同款布景、模糊畸形、水印、文字、多余杂物堆砌、劣质贴图、低画质、雷同色调、平台Logo、品牌标识、社交媒体图标、二维码、网址、URL、商标、标签、边框、角标、水印文字、品牌名称、TikTok、小红书、Instagram、Facebook、抖音、微博、微信、twitter、youtube
"""
    
    # 四、提示词拼接模板
    IMAGE_PROMPT_TEMPLATE = """
【{product_description}】
{fixed_constraints}
【{random_elements}】，商业产品实拍，细节丰富，色彩自然
"""

    # === 相似度和重试配置 ===
    SIMILARITY_THRESHOLD = 0.85
    IMAGE_SIMILARITY_THRESHOLD = 0.85
    MAX_RETRY_ATTEMPTS = 1
    
    # === 图片相似度优化配置 ===
    IMAGE_FEATURE_CACHE_SIZE = 100  # 图片特征缓存大小
    ENABLE_IMAGE_FEATURE_CACHE = True  # 是否启用图片特征缓存
    ENABLE_MULTI_FEATURE_FUSION = False  # 是否启用多特征融合（颜色直方图等）
    PRELOAD_IMAGE_FEATURES = True  # 是否在启动时预加载图片特征

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