# -*- coding: utf-8 -*-
"""
AI模型集成服务模块

该模块提供与AI服务的交互功能，支持：
1. 文本生成（使用DeepSeek模型）
2. 图片生成（使用Doubao-Seedream-4.5模型）
3. 文本相似度计算
4. 图片视觉相似度计算（使用CLIP模型）

模块结构：
- 初始化部分：加载GitHub图床模块和CLIP视觉模型
- 基础工具函数：图片URL处理、请求头生成
- 提示词生成：build_image_prompt（根据配置生成多样化提示词）
- 文本生成：generate_content、generate_unique_content
- 图片生成：generate_image、generate_unique_image
- 相似度计算：calculate_similarity、calculate_image_similarity
- 嵌入向量处理：get_embedding、batch_calculate_similarity
"""

import requests
import time
import torch
import random
import base64
import os
import io
import uuid
import numpy as np
from urllib.parse import quote
from PIL import Image


def build_image_prompt(product_description):
    """
    根据配置生成多样化的图片提示词
    
    核心思路：固定产品本体约束 + 随机化全维度场景/光影/构图/风格/环境变量
    
    Args:
        product_description (str): 产品描述（从知识库提取）
    
    Returns:
        str: 完整的图片生成提示词
    """
    # 从配置中读取随机变量池
    viewpoints = Config.IMAGE_PROMPT_VIEWPOINTS
    scenes = Config.IMAGE_PROMPT_SCENES
    lighting = Config.IMAGE_PROMPT_LIGHTING
    compositions = Config.IMAGE_PROMPT_COMPOSITIONS
    styles = Config.IMAGE_PROMPT_STYLES
    quality = Config.IMAGE_PROMPT_QUALITY
    details = Config.IMAGE_PROMPT_DETAILS
    
    # 从每类随机抽取1项
    random_viewpoint = random.choice(viewpoints)
    random_scene = random.choice(scenes)
    random_lighting = random.choice(lighting)
    random_composition = random.choice(compositions)
    random_style = random.choice(styles)
    random_quality = random.choice(quality)
    
    # 随机追加1~2个细节词
    num_details = random.randint(1, 2)
    random_details = random.sample(details, num_details)
    
    # 拼接随机元素
    random_elements = " ".join([
        random_viewpoint,
        random_scene,
        random_lighting,
        random_composition,
        random_style,
        random_quality,
        *random_details
    ])
    
    # 使用配置中的模板拼接完整提示词
    prompt = Config.IMAGE_PROMPT_TEMPLATE.format(
        product_description=product_description,
        fixed_constraints=Config.IMAGE_PROMPT_FIXED_TEMPLATE.strip(),
        random_elements=random_elements
    )
    
    return prompt.strip()

# 设置HuggingFace镜像源，加速模型下载
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

# 模块初始化标志，确保只初始化一次
_initialized = False

if not _initialized:
    _initialized = True
    
    # 尝试导入GitHub图床服务
    try:
        from app.services.github_service import upload_image_to_github, convert_github_url_to_cdn
        logger.info("✅ GitHub 图床模块导入成功")
    except Exception as e:
        logger.warning(f"❌ 导入 GitHub 图床模块失败: {e}")
        upload_image_to_github = None
        convert_github_url_to_cdn = None

    # 构建本地模型目录路径
    local_model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')

    # 尝试加载CLIP视觉模型（用于图片相似度计算）
    try:
        from transformers import CLIPProcessor, CLIPModel
        
        local_model_path = os.path.join(local_model_dir, 'huggingface', 'hub', 'models--openai--clip-vit-base-patch32', 'snapshots', 'main')
        
        clip_model = CLIPModel.from_pretrained(local_model_path, local_files_only=True)
        clip_processor = CLIPProcessor.from_pretrained(local_model_path, local_files_only=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        clip_model = clip_model.to(device)
        clip_model.eval()
        CLIP_AVAILABLE = True
        logger.info("✅ CLIP模型加载成功")
    except Exception as e:
        logger.warning(f"CLIP model loading failed: {e}, using fallback")
        CLIP_AVAILABLE = False


def get_doubao_headers():
    """
    获取Doubao API请求头
    
    Returns:
        dict: 包含Authorization和Content-Type的请求头字典
    """
    return {
        "Authorization": f"Bearer {Config.DOUBAO_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def ensure_image_url(image_source, upload_to_github=False):
    """
    确保图片源转换为有效的URL
    
    支持多种图片来源类型：
    1. Base64编码字符串（以data:image/开头）
    2. HTTP/HTTPS URL
    3. 本地文件路径（可选择上传到GitHub图床）
    
    Args:
        image_source (str): 图片来源，可以是URL、Base64编码或本地路径
        upload_to_github (bool): 是否将本地文件上传到GitHub图床
    
    Returns:
        str | None: 有效的图片URL，处理失败返回None
    """
    logger.info(f"[ensure_image_url] 开始处理: {image_source[:80] if image_source else None}")
    
    # 空输入检查
    if not image_source:
        logger.warning("[ensure_image_url] 输入为空")
        return None
    
    # Base64编码直接返回
    if image_source.startswith('data:image/'):
        logger.info(f"[ensure_image_url] ✅ 检测到Base64编码，直接返回")
        return image_source
    
    # HTTP/HTTPS URL直接返回
    if image_source.startswith('http://') or image_source.startswith('https://'):
        logger.info(f"[ensure_image_url] ✅ 检测到HTTP/HTTPS URL，直接返回")
        return image_source
    
    # 尝试作为本地文件路径处理
    logger.info(f"[ensure_image_url] 尝试作为本地文件路径处理")
    
    # 移除路径开头的斜杠
    if image_source.startswith('/'):
        image_path = image_source[1:]
    else:
        image_path = image_source
    
    # 构建完整路径
    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), image_path)
    
    # 检查路径是否存在
    if os.path.exists(full_path):
        image_path = full_path
    elif os.path.exists(image_source):
        image_path = image_source
    else:
        logger.warning(f"[ensure_image_url] ❌ 图片源未找到: {image_source}")
        return None
    
    # 上传到GitHub图床
    if upload_to_github and upload_image_to_github:
        logger.info(f"[ensure_image_url] ✅ 文件存在，上传到GitHub")
        github_url = upload_image_to_github(image_path)
        if github_url:
            if convert_github_url_to_cdn:
                cdn_url = convert_github_url_to_cdn(github_url)
                if cdn_url:
                    github_url = cdn_url
            logger.info(f"[ensure_image_url] ✅ 上传成功: {github_url}")
            return github_url
        else:
            logger.warning(f"[ensure_image_url] ❌ 上传GitHub失败")
            return None
    else:
        if not upload_to_github:
            logger.info(f"[ensure_image_url] 跳过GitHub上传（upload_to_github=False）")
        else:
            logger.warning(f"[ensure_image_url] ❌ GitHub图床未配置")
        return None


# 全局变量：维护最近生成的文案摘要，用于差别化约束
recent_generations = []

def extract_keywords(text, top_n=10):
    """
    从文本中提取高频关键词（简单实现）
    
    Args:
        text (str): 输入文本
        top_n (int): 返回的关键词数量
    
    Returns:
        list: 关键词列表
    """
    if not text:
        return []
    
    import re
    # 移除标点符号和标签
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    cleaned_text = re.sub(r'#\w+', '', cleaned_text)
    
    # 分词并统计频率（英文）
    words = cleaned_text.lower().split()
    word_counts = {}
    for word in words:
        if len(word) > 2:  # 过滤短词
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # 返回频率最高的词
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_n]]


def build_content_prompt(product_description, original_content="", previous_generation=""):
    """
    根据配置生成多样化的文案提示词
    
    核心思路：随机风格角色 + 反约束模板
    
    Args:
        product_description (str): 产品描述
        original_content (str): 原始文案（用于提取禁用词）
        previous_generation (str): 上一次生成的文案（用于差别化约束）
    
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    # 随机选择叙述视角和写作风格
    perspective = random.choice(Config.NARRATIVE_PERSPECTIVES)
    writing_style = random.choice(Config.WRITING_STYLES)
    
    # 随机选择字数范围
    min_words = Config.CONTENT_MIN_WORDS
    max_words = Config.CONTENT_MAX_WORDS
    target_word_count = random.randint(min_words, max_words)
    
    # 从原始文案提取禁用词
    forbidden_words = extract_keywords(original_content, top_n=10)
    forbidden_words_str = ", ".join(forbidden_words) if forbidden_words else "无"
    
    # 构建系统提示词（填充模板变量）
    system_prompt = Config.CONTENT_GENERATION_SYSTEM_PROMPT.format(
        narrative_perspective=perspective,
        writing_style=writing_style,
        word_count=f"{min_words}-{max_words}",
        forbidden_words=forbidden_words_str
    )
    
    # 构建用户提示词（产品信息）
    user_prompt = f"基于以下产品信息，生成社交媒体文案：\n\n{product_description}"
    
    # 如果有上一次生成的内容，添加差别化提示
    if previous_generation:
        # 提取上一次的开头部分
        previous_start = previous_generation[:50] if len(previous_generation) > 50 else previous_generation
        differentiation_hint = Config.DIFFERENTIATION_PROMPT.format(previous_start=previous_start)
        user_prompt = differentiation_hint + "\n\n" + user_prompt
    
    return system_prompt, user_prompt


def generate_content(prompt, style=None):
    """
    使用DeepSeek模型生成社交媒体文案
    
    支持多种写作风格和叙述视角，自动实现多样化生成
    
    Args:
        prompt (str): 生成文案的提示词（产品信息）
        style (str, optional): 指定写作风格，不指定则随机选择
    
    Returns:
        str | None: 生成的文案内容，失败返回None
    """
    # 检查API配置
    if not Config.DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API Key not configured")
        return None
    
    # 获取上一次生成的文案用于差别化约束
    previous_generation = recent_generations[-1] if recent_generations else ""
    
    # 构建提示词
    system_prompt, user_prompt = build_content_prompt(prompt, original_content="", previous_generation=previous_generation)
    
    # 选择temperature（根据写作风格调整）
    temperature = random.uniform(0.7, 1.0)
    
    # API请求配置
    url = f"{Config.DEEPSEEK_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 请求数据
    data = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "max_tokens": 500,
        "temperature": temperature,
        "top_p": 0.9,
        "frequency_penalty": 0.3,
        "presence_penalty": 0.2,
        "stream": False
    }
    
    try:
        logger.debug("调用DeepSeek API生成文案", extra={"prompt_length": len(prompt)})
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # 解析响应结果
        choices = result.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "").strip()
            logger.info("文案生成成功", extra={"content_length": len(content)})
            
            # 记录最近生成的文案，用于差别化约束（最多保留3条）
            recent_generations.append(content)
            if len(recent_generations) > 3:
                recent_generations.pop(0)
            
            return content
        
        logger.warning("DeepSeek API返回空结果")
        return None
    except Exception as e:
        logger.error("DeepSeek API调用失败", extra={"error": str(e), "prompt_length": len(prompt)})
        return None


def generate_image(prompt, model_id=None, aspect_ratio=None, resolution=None, 
                   max_wait_seconds=120, image_reference_url=None, 
                   use_logo_as_reference=True, upload_to_github=False):
    """
    使用Doubao API生成图片（支持参考图片和Logo）
    
    功能特性：
    1. 支持多种宽高比（1:1, 9:16, 16:9等）
    2. 支持参考图片引导生成
    3. 支持Logo作为参考图片
    4. 支持上传到GitHub图床
    5. 支持超时重试机制（最多3次）
    
    Args:
        prompt (str): 图片生成提示词
        model_id (str, optional): 模型ID，默认使用配置中的模型
        aspect_ratio (str, optional): 宽高比，如"1:1", "9:16"
        resolution (str, optional): 分辨率（暂未使用）
        max_wait_seconds (int, optional): 最大等待时间，默认120秒
        image_reference_url (str, optional): 参考图片URL
        use_logo_as_reference (bool, optional): 是否使用Logo作为参考，默认True
        upload_to_github (bool, optional): 是否上传到GitHub图床，默认False
    
    Returns:
        str | None: 生成的图片URL，失败返回None
    """
    # 检查API配置
    if not Config.DOUBAO_API_KEY:
        logger.error("Doubao API Key not configured")
        return None
    
    url = Config.DOUBAO_API_URL
    headers = get_doubao_headers()
    
    # 确定宽高比
    aspect_ratio = aspect_ratio or Config.DOUBAO_ASPECT_RATIO
    
    # 宽高比到分辨率的映射
    size_map = {
        "1:1": "2048x2048",
        "9:16": "1600x2848",
        "16:9": "2848x1600",
        "4:3": "2304x1728",
        "3:4": "1728x2304",
        "3:2": "2496x1664",
        "2:3": "1664x2496",
        "21:9": "3136x1344"
    }
    size = size_map.get(aspect_ratio, "2048x2048")
    
    # 使用配置中的负向提示词
    negative_prompt = Config.IMAGE_NEGATIVE_PROMPT
    
    # 请求数据
    data = {
        "model": model_id or Config.DOUBAO_MODEL_ID,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled",
        "negative_prompt": negative_prompt
    }
    
    reference_images = []
    
    # 处理产品参考图片
    if image_reference_url:
        logger.info(f"[参考图片处理] 原始URL: {image_reference_url}")
        
        processed_image = ensure_image_url(image_reference_url, upload_to_github=True)
        
        if processed_image:
            # URL编码处理（防止双重编码问题）
            if processed_image.startswith('http://') or processed_image.startswith('https://'):
                try:
                    from urllib.parse import urlparse, urlunparse, unquote
                    parsed = urlparse(processed_image)
                    decoded_path = unquote(parsed.path)
                    encoded_path = quote(decoded_path, safe='/@')
                    processed_image = urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))
                    logger.info(f"[参考图片处理] URL编码完成: {processed_image[:50]}")
                except Exception as e:
                    logger.warning(f"[参考图片处理] URL编码失败: {e}")
            
            reference_images.append({"image": processed_image, "weight": 0.8})
            logger.info(f"✅ 添加产品参考图片成功 (权重: 0.8)")
        else:
            logger.warning(f"❌ 产品参考图片处理失败: {image_reference_url}")
    
    # 处理Logo参考图片（可选）
    if use_logo_as_reference and Config.LOGO_FILE_PATH:
        try:
            if Config.LOGO_FILE_PATH.startswith(('http://', 'https://')):
                logger.info(f"[Logo参考图片处理] 使用远程URL: {Config.LOGO_FILE_PATH}")
                # 先验证URL是否可访问
                try:
                    response = requests.head(Config.LOGO_FILE_PATH, timeout=5)
                    if response.status_code == 200:
                        logo_url = Config.LOGO_FILE_PATH
                        reference_images.append({"image": logo_url, "weight": 0.2})
                        logger.info(f"✅ 添加Logo参考图片成功: {logo_url} (权重: 0.2)")
                    else:
                        logger.warning(f"⚠️ Logo URL不可访问，跳过Logo参考图片")
                except Exception as e:
                    logger.warning(f"⚠️ Logo URL验证失败，跳过Logo参考图片: {e}")
            elif os.path.exists(Config.LOGO_FILE_PATH):
                logger.info(f"[Logo参考图片处理] 文件存在，准备上传到GitHub: {Config.LOGO_FILE_PATH}")
                if upload_image_to_github:
                    github_url = upload_image_to_github(Config.LOGO_FILE_PATH)
                    if github_url:
                        if convert_github_url_to_cdn:
                            cdn_url = convert_github_url_to_cdn(github_url)
                            if cdn_url:
                                github_url = cdn_url
                        reference_images.append({"image": github_url, "weight": 0.2})
                        logger.info(f"✅ Logo上传GitHub成功，使用URL: {github_url} (权重: 0.2)")
                    else:
                        logger.warning(f"⚠️ Logo上传GitHub失败，跳过Logo参考图片")
                else:
                    logger.warning(f"⚠️ GitHub图床未配置，跳过Logo参考图片")
            else:
                logger.warning(f"⚠️ Logo参考图片文件不存在，跳过Logo参考图片: {Config.LOGO_FILE_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ 处理Logo参考图片时发生错误，跳过Logo参考图片: {e}")
    
    # 添加参考图片到请求数据
    if reference_images:
        logger.info("[参考图片设置] 准备发送到Doubao", extra={"total_count": len(reference_images)})
        if len(reference_images) == 1:
            data["image"] = reference_images[0]["image"]
            data["image_weight"] = reference_images[0]["weight"]
        else:
            data["image"] = [img["image"] for img in reference_images]
            data["image_weight"] = [img["weight"] for img in reference_images]
    
    # 超时重试配置
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"调用Doubao API生成图片 (尝试 {attempt + 1}/{max_retries})", extra={"prompt": prompt[:50]})
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            try:
                result = response.json()
            except:
                result = {}
            
            # 处理API错误
            if "error" in result:
                error_code = result["error"].get("code", "")
                error_message = result["error"].get("message", "")
                
                # 下载超时重试
                if "Timeout while downloading" in error_message and attempt < max_retries - 1:
                    logger.warning(f"Doubao API下载超时，将在 {retry_delay} 秒后重试", 
                                extra={"prompt": prompt[:50], "attempt": attempt + 1})
                    time.sleep(retry_delay)
                    continue
                
                logger.error(f"Doubao API返回错误: {error_code} - {error_message}", 
                            extra={"prompt": prompt[:50]})
                return None
            
            response.raise_for_status()
            
            # 解析成功响应
            if "data" in result and len(result["data"]) > 0:
                first_image = result["data"][0]
                
                # 处理图片级别的错误
                if "error" in first_image:
                    error_code = first_image["error"].get("code", "")
                    error_message = first_image["error"].get("message", "")
                    
                    # 下载超时重试
                    if "Timeout while downloading" in error_message and attempt < max_retries - 1:
                        logger.warning(f"Doubao图片生成超时，将在 {retry_delay} 秒后重试", 
                                    extra={"prompt": prompt[:50], "attempt": attempt + 1})
                        time.sleep(retry_delay)
                        continue
                    
                    logger.error(f"Doubao图片生成失败: {error_code} - {error_message}", 
                                extra={"prompt": prompt[:50]})
                    return None
                
                image_url = first_image.get("url")
                if image_url:
                    logger.info("Doubao图片生成成功", extra={"image_url": image_url[:50]})
                    
                    # 上传到GitHub图床
                    if upload_to_github:
                        try:
                            if convert_github_url_to_cdn:
                                image_url = convert_github_url_to_cdn(image_url)
                            
                            if upload_image_to_github:
                                github_cdn_url = upload_image_to_github(image_url)
                                if github_cdn_url:
                                    logger.info("✅ 图片已上传到 GitHub 图床", extra={"cdn_url": github_cdn_url})
                                    return github_cdn_url
                        except Exception as e:
                            logger.error(f"❌ GitHub 图床处理失败: {e}", extra={"error": str(e)})
                    
                    return image_url
            
            logger.warning("Doubao API返回结果格式异常", extra={"result": result})
            return None
        except requests.exceptions.Timeout:
            # 请求超时重试
            if attempt < max_retries - 1:
                logger.warning(f"Doubao API请求超时，将在 {retry_delay} 秒后重试", 
                            extra={"prompt": prompt[:50], "attempt": attempt + 1})
                time.sleep(retry_delay)
                continue
            else:
                logger.error("Doubao图片生成失败: 请求超时", extra={"prompt": prompt[:50]})
                return None
        except Exception as e:
            logger.error("Doubao图片生成失败", extra={"error": str(e), "prompt": prompt[:50]})
            return None
    
    logger.error(f"Doubao图片生成失败: 已达到最大重试次数 ({max_retries})", extra={"prompt": prompt[:50]})
    return None


def calculate_similarity(text1, text2):
    """
    计算两段文本的相似度（委托给Chroma服务）
    
    Args:
        text1 (str): 第一段文本
        text2 (str): 第二段文本
    
    Returns:
        float: 相似度分数（0-1）
    """
    from app.services.chroma_service import calculate_similarity as chroma_similarity
    return chroma_similarity(text1, text2)


def load_image_from_source(image_source):
    """
    从多种来源加载图片
    
    支持的来源类型：
    1. HTTP/HTTPS URL
    2. Base64编码字符串
    3. 本地文件路径
    
    Args:
        image_source (str): 图片来源
    
    Returns:
        PIL.Image | None: 加载的PIL图片对象，失败返回None
    """
    if not image_source:
        logger.debug("Image source is None or empty")
        return None
    
    try:
        if image_source.startswith(('http://', 'https://')):
            # 跳过占位图片
            if 'example.com' in image_source:
                logger.debug(f"Skipping placeholder image URL: {image_source}")
                return None
            
            # 从URL加载图片
            response = requests.get(image_source, stream=True, timeout=10)
            response.raise_for_status()
            return Image.open(response.raw).convert("RGB")
        elif image_source.startswith('data:image/'):
            # 从Base64编码加载图片
            import io
            base64_data = image_source.split(',')[1]
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        else:
            # 从本地文件加载
            local_path = image_source
            if local_path.startswith('/'):
                local_path = local_path[1:]
            
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), local_path)
            
            if os.path.exists(full_path):
                return Image.open(full_path).convert("RGB")
            
            if os.path.exists(image_source):
                return Image.open(image_source).convert("RGB")
            
            logger.error(f"Image file not found: {image_source} (tried: {full_path})")
            return None
    except Exception as e:
        logger.error(f"Failed to load image from {image_source}", extra={"error": str(e)})
        return None


def calculate_image_similarity(image_url1, image_url2):
    """
    使用CLIP模型计算两张图片的视觉相似度
    
    Args:
        image_url1 (str): 第一张图片的URL
        image_url2 (str): 第二张图片的URL
    
    Returns:
        float: 视觉相似度分数（0-1），CLIP不可用时返回0
    """
    if not CLIP_AVAILABLE:
        logger.warning("CLIP model not available, returning default similarity of 0")
        return 0.0
    
    try:
        # 加载两张图片
        image1 = load_image_from_source(image_url1)
        image2 = load_image_from_source(image_url2)
        
        if image1 is None or image2 is None:
            logger.error("Failed to load one or both images")
            return 0.0
        
        # 使用CLIP处理器准备输入
        inputs = clip_processor(images=[image1, image2], return_tensors="pt").to(device)
        
        # 提取视觉特征
        vision_model = clip_model.vision_model
        
        with torch.no_grad():
            outputs = vision_model(**inputs)
        
        # 获取特征向量
        feature1 = outputs.pooler_output[0:1]
        feature2 = outputs.pooler_output[1:2]
        
        # 计算余弦相似度
        similarity = torch.nn.functional.cosine_similarity(feature1, feature2).item()
        
        logger.debug(f"Image similarity calculated: {similarity}")
        return similarity
        
    except Exception as e:
        logger.error("Error calculating image similarity", extra={"error": str(e)})
        return 0.0


# 嵌入向量缓存，避免重复计算
_embedding_cache = {}

# 图片特征缓存，避免重复计算
_image_feature_cache = {}


def extract_clip_feature(image_url):
    """
    提取单张图片的CLIP特征
    
    Args:
        image_url (str): 图片URL
    
    Returns:
        torch.Tensor: CLIP特征向量，失败返回None
    """
    if not CLIP_AVAILABLE:
        logger.warning("CLIP model not available")
        return None
    
    try:
        image = load_image_from_source(image_url)
        if image is None:
            logger.error(f"Failed to load image: {image_url}")
            return None
        
        inputs = clip_processor(images=[image], return_tensors="pt").to(device)
        
        with torch.no_grad():
            vision_model = clip_model.vision_model
            outputs = vision_model(**inputs)
            feature = outputs.pooler_output[0]
        
        return feature
    
    except Exception as e:
        logger.error(f"Error extracting CLIP feature: {e}")
        return None


def get_image_feature(image_url):
    """
    获取图片特征，带缓存机制
    
    Args:
        image_url (str): 图片URL
    
    Returns:
        torch.Tensor: CLIP特征向量，失败返回None
    """
    # 如果缓存未启用，直接计算
    if not Config.ENABLE_IMAGE_FEATURE_CACHE:
        return extract_clip_feature(image_url)
    
    # 检查缓存
    if image_url in _image_feature_cache:
        return _image_feature_cache[image_url]
    
    # 计算特征
    feature = extract_clip_feature(image_url)
    if feature is None:
        return None
    
    # 缓存管理（FIFO策略）
    if len(_image_feature_cache) >= Config.IMAGE_FEATURE_CACHE_SIZE:
        # 删除最早添加的缓存
        oldest_key = next(iter(_image_feature_cache))
        del _image_feature_cache[oldest_key]
    
    _image_feature_cache[image_url] = feature
    logger.debug(f"Cached image feature for: {image_url}")
    return feature


def batch_calculate_image_similarity(new_feature, existing_features):
    """
    批量计算相似度（向量化操作）
    
    Args:
        new_feature (torch.Tensor): 新图片特征
        existing_features (list): 已有图片特征列表
    
    Returns:
        list: 相似度分数列表
    """
    if not existing_features:
        return []
    
    try:
        # 转换为张量进行批量计算
        existing_tensor = torch.stack(existing_features).to(device)
        new_tensor = new_feature.unsqueeze(0).to(device)
        
        # 计算余弦相似度（批量）
        similarities = torch.nn.functional.cosine_similarity(new_tensor, existing_tensor)
        
        return similarities.cpu().numpy().tolist()
    
    except Exception as e:
        logger.error(f"Error in batch image similarity calculation: {e}")
        return []


def get_adaptive_image_threshold(existing_count):
    """
    根据已有图片数量动态调整阈值
    
    Args:
        existing_count (int): 已有图片数量
    
    Returns:
        float: 自适应阈值
    """
    base_threshold = Config.IMAGE_SIMILARITY_THRESHOLD
    
    # 图片越多，阈值越低（允许更多变化）
    if existing_count < 10:
        return base_threshold  # 严格模式
    elif existing_count < 50:
        return base_threshold * 0.95
    else:
        return base_threshold * 0.9  # 宽松模式


def is_image_unique_optimized(new_image_url, existing_images_info, threshold=None):
    """
    优化版图片唯一性检测
    
    Args:
        new_image_url (str): 新图片URL
        existing_images_info (list): 已有图片信息列表
        threshold (float, optional): 相似度阈值
    
    Returns:
        bool | None: True=唯一, False=重复, None=检测失败
    """
    if not existing_images_info:
        return True
    
    # 获取自适应阈值
    if threshold is None:
        threshold = get_adaptive_image_threshold(len(existing_images_info))
    
    # 获取新图片特征（带缓存）
    new_feature = get_image_feature(new_image_url)
    if new_feature is None:
        logger.warning("获取新图片特征失败")
        return None
    
    # 批量获取已有图片特征
    existing_features = []
    valid_urls = []
    
    for info in existing_images_info:
        url = info.get('url')
        if url:
            feature = get_image_feature(url)
            if feature is not None:
                existing_features.append(feature)
                valid_urls.append(url)
    
    # 批量计算相似度
    if not existing_features:
        return True
    
    similarities = batch_calculate_image_similarity(new_feature, existing_features)
    if not similarities:
        return True
    
    max_similarity = max(similarities)
    logger.info(f"图片相似度检测: 最高相似度 {max_similarity:.4f} (阈值: {threshold})")
    
    return max_similarity < threshold


def preload_image_features():
    """
    启动时预加载知识库中的图片特征
    """
    if not Config.PRELOAD_IMAGE_FEATURES:
        return
    
    try:
        from app.services.chroma_service import get_all_entries
        
        entries = get_all_entries()
        image_urls = [entry.get('image_url') for entry in entries if entry.get('image_url')]
        
        logger.info(f"预加载 {len(image_urls)} 张图片特征...")
        
        for url in image_urls:
            try:
                get_image_feature(url)
            except Exception as e:
                logger.warning(f"预加载失败: {url}, {e}")
        
        logger.info(f"图片特征预加载完成，已缓存 {len(_image_feature_cache)} 个特征")
    
    except Exception as e:
        logger.warning(f"图片特征预加载失败: {e}")


def get_embedding(text):
    """
    获取文本的嵌入向量（带缓存）
    
    Args:
        text (str): 需要获取嵌入向量的文本
    
    Returns:
        numpy.ndarray: 文本的嵌入向量
    """
    # 检查缓存
    if text in _embedding_cache:
        return _embedding_cache[text]
    
    # 计算嵌入向量
    from app.services.chroma_service import sentence_transformer_ef
    embedding = sentence_transformer_ef([text])[0]
    _embedding_cache[text] = embedding
    
    # 限制缓存大小（最多1000条）
    if len(_embedding_cache) > 1000:
        keys = list(_embedding_cache.keys())[:500]
        for key in keys:
            del _embedding_cache[key]
    
    return embedding


def batch_calculate_similarity(new_embedding, existing_embeddings):
    """
    批量计算新嵌入向量与已有嵌入向量的相似度
    
    Args:
        new_embedding (numpy.ndarray): 新文本的嵌入向量
        existing_embeddings (list): 已有文本的嵌入向量列表
    
    Returns:
        numpy.ndarray: 相似度分数数组
    """
    if not existing_embeddings:
        return np.array([])
    
    # 转换为矩阵
    existing_matrix = np.array(existing_embeddings)
    
    # 计算归一化
    new_norm = np.linalg.norm(new_embedding)
    existing_norms = np.linalg.norm(existing_matrix, axis=1)
    
    # 处理零向量情况
    mask = existing_norms > 0
    if not np.any(mask):
        return np.zeros(len(existing_embeddings))
    
    # 批量计算余弦相似度
    dot_products = existing_matrix @ new_embedding
    similarities = dot_products / (new_norm * existing_norms)
    
    # 零向量相似度设为0
    similarities[~mask] = 0.0
    
    return similarities


def is_text_exact_duplicate(text1, text2):
    """
    判断两段文本是否为精确重复或高度相似
    
    判断逻辑：
    1. 去除标点符号后完全相同 → 重复
    2. Jaccard相似度 > 0.9 → 高度相似，判定为重复
    
    Args:
        text1 (str): 第一段文本
        text2 (str): 第二段文本
    
    Returns:
        bool: 是否为重复
    """
    def clean_text(text):
        """清理文本：转小写并去除非字母数字字符"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w]', '', text)
        return text
    
    clean1 = clean_text(text1)
    clean2 = clean_text(text2)
    
    # 完全匹配检查
    if clean1 == clean2:
        return True
    
    # Jaccard相似度检查（仅对包含ASCII字符的文本）
    if any(ord(c) < 128 for c in text1):
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0
        if jaccard > 0.9:
            logger.info(f"检测到高Jaccard相似度: {jaccard:.2f}，判定为重复")
            return True
    
    return False


def is_content_unique_optimized(new_content, threshold=Config.SIMILARITY_THRESHOLD, top_k=20):
    """
    使用Chroma索引快速检测内容唯一性（优化版）
    
    Args:
        new_content (str): 新内容
        threshold (float, optional): 相似度阈值，默认使用配置值
        top_k (int, optional): 检索的top-k数量，默认20
    
    Returns:
        bool | None: True表示唯一，False表示重复，None表示检测失败
    """
    from app.services.chroma_service import collection
    
    if not new_content or not new_content.strip():
        return False
    
    try:
        # 查询相似内容
        results = collection.query(
            query_texts=[new_content],
            n_results=top_k
        )
        
        # 计算相似度
        if results['distances'][0]:
            similarities = [1 - d for d in results['distances'][0]]
            max_similarity = max(similarities)
            if max_similarity >= threshold:
                logger.debug(f"找到相似内容，相似度: {max_similarity:.4f}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"使用Chroma索引检测失败，降级到逐条比较: {str(e)}")
        return None


def generate_unique_content(base_prompt, existing_contents):
    """
    生成与已有内容不重复的唯一文案
    
    功能特性：
    1. 支持精确重复检测
    2. 支持基于Chroma索引的快速检测（内容超过50条时启用）
    3. 支持批量嵌入向量比较
    4. 支持多轮重试机制
    
    Args:
        base_prompt (str): 基础提示词
        existing_contents (list): 已有文案列表
    
    Returns:
        str | None: 生成的唯一文案，失败返回最后一次生成的结果
    """
    valid_contents = [c for c in existing_contents if c and c.strip()]
    logger.info(f"开始生成唯一文案，待比较文案数量: {len(valid_contents)}")
    
    # 知识库为空时直接生成
    if len(valid_contents) == 0:
        logger.info("知识库为空，直接生成文案（不进行重复检测）")
        new_content = generate_content(base_prompt)
        return new_content
    
    # 决定使用哪种检测方式
    use_optimized = len(valid_contents) > 50
    
    # 阈值调整策略（随重试次数增加而提高阈值）
    threshold_adjustments = [0, 0.05, 0.1]
    
    for attempt in range(Config.MAX_RETRY_ATTEMPTS):
        logger.info(f"文案生成尝试 {attempt + 1}/{Config.MAX_RETRY_ATTEMPTS}")
        new_content = generate_content(base_prompt)
        if not new_content:
            logger.warning(f"文案生成失败，继续重试")
            continue
        
        # 动态调整阈值
        current_threshold = Config.SIMILARITY_THRESHOLD + threshold_adjustments[min(attempt, len(threshold_adjustments)-1)]
        logger.info(f"当前尝试阈值: {current_threshold:.2f}")
        
        # 精确重复检测
        is_exact_duplicate = False
        for existing in valid_contents:
            if is_text_exact_duplicate(new_content, existing):
                is_exact_duplicate = True
                logger.info(f"检测到精确重复文案，跳过")
                break
        
        if is_exact_duplicate:
            continue
        
        # 使用Chroma索引检测（优化版）
        if use_optimized:
            is_unique = is_content_unique_optimized(new_content, threshold=current_threshold)
            
            if is_unique is None:
                # 降级到批量比较
                use_optimized = False
                logger.info("Chroma索引检测失败，降级到批量比较")
            elif is_unique:
                logger.info(f"文案通过Chroma索引检测（唯一），生成成功")
                return new_content
            else:
                logger.info(f"内容重复检测(优化): 重试第 {attempt + 1} 次")
                continue
        
        # 批量嵌入向量比较
        existing_embeddings = []
        for content in valid_contents:
            if content.strip():
                existing_embeddings.append(get_embedding(content))
        
        new_embedding = get_embedding(new_content)
        similarities = batch_calculate_similarity(new_embedding, existing_embeddings)
        
        max_similarity = np.max(similarities) if len(similarities) > 0 else 0.0
        
        # 判断是否通过检测
        if len(similarities) == 0 or max_similarity < current_threshold:
            logger.info(f"文案通过相似度检测（相似度: {max_similarity:.4f} < {current_threshold:.2f}），生成成功")
            return new_content
        
        # 输出最相似内容信息
        if len(similarities) > 0:
            most_similar_idx = np.argmax(similarities)
            most_similar_content = valid_contents[most_similar_idx][:60] + "..."
            logger.info(f"最相似文案: {most_similar_content}，相似度: {max_similarity:.4f}")
        
        logger.info(f"内容重复检测(批量): 最高相似度 {max_similarity:.4f} >= {current_threshold:.2f}，重试第 {attempt + 1} 次")
    
    # 达到最大重试次数，返回最后一次结果
    logger.warning(f"经过 {Config.MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一文案，返回最后一次结果")
    return new_content


def generate_unique_image(base_prompt, existing_images_info, model_id=None, reference_image_url=None, upload_to_github=False):
    """
    生成与已有图片不重复的唯一图片（优化版）
    
    功能特性：
    1. 使用CLIP模型进行视觉相似度检测（带缓存优化）
    2. 支持批量相似度计算，提升性能
    3. 自适应阈值调整（根据已有图片数量）
    4. CLIP不可用时降级为提示词相似度检测
    5. 支持多轮重试机制
    
    Args:
        base_prompt (str): 图片生成提示词
        existing_images_info (list): 已有图片信息列表，每项包含image_url和prompt
        model_id (str, optional): 模型ID
        reference_image_url (str, optional): 参考图片URL
        upload_to_github (bool, optional): 是否上传到GitHub图床
    
    Returns:
        str | None: 生成的唯一图片URL，失败返回最后一次生成的结果
    """
    logger.info("开始生成唯一图片", extra={"prompt": base_prompt[:50], "attempts": Config.MAX_RETRY_ATTEMPTS, "existing_count": len(existing_images_info)})
    
    last_generated_image = None
    
    # 获取自适应阈值
    adaptive_threshold = get_adaptive_image_threshold(len(existing_images_info))
    
    for attempt in range(Config.MAX_RETRY_ATTEMPTS):
        logger.info(f"图片生成尝试 {attempt + 1}/{Config.MAX_RETRY_ATTEMPTS}")
        
        # 生成图片
        new_image_url = generate_image(base_prompt, model_id=model_id, image_reference_url=reference_image_url, upload_to_github=upload_to_github)
        if not new_image_url:
            logger.warning(f"图片生成失败，尝试 {attempt + 1}")
            continue
        
        last_generated_image = new_image_url
        
        # 使用优化版唯一性检测
        if CLIP_AVAILABLE and existing_images_info:
            is_unique = is_image_unique_optimized(new_image_url, existing_images_info, threshold=adaptive_threshold)
            
            if is_unique is None:
                # 检测失败，降级为提示词检测
                logger.info("图片唯一性检测失败，降级为提示词相似度检测")
                is_unique = True
                
                for existing_image in existing_images_info:
                    existing_prompt = existing_image.get('prompt', '')
                    if existing_prompt:
                        similarity = calculate_similarity(base_prompt, existing_prompt)
                        logger.info(f"提示词相似度检测: {similarity:.4f} (阈值: {Config.SIMILARITY_THRESHOLD})")
                        if similarity >= Config.SIMILARITY_THRESHOLD:
                            logger.info(f"提示词相似度 {similarity:.4f} 超过阈值 {Config.SIMILARITY_THRESHOLD}，尝试重新生成")
                            is_unique = False
                            break
            elif not is_unique:
                logger.info(f"图片相似度超过阈值 {adaptive_threshold}，尝试重新生成")
                continue
        elif existing_images_info:
            # CLIP不可用，降级为提示词相似度检测
            is_unique = True
            for existing_image in existing_images_info:
                existing_prompt = existing_image.get('prompt', '')
                if existing_prompt:
                    similarity = calculate_similarity(base_prompt, existing_prompt)
                    logger.info(f"提示词相似度检测: {similarity:.4f} (阈值: {Config.SIMILARITY_THRESHOLD})")
                    if similarity >= Config.SIMILARITY_THRESHOLD:
                        logger.info(f"提示词相似度 {similarity:.4f} 超过阈值 {Config.SIMILARITY_THRESHOLD}，尝试重新生成")
                        is_unique = False
                        break
        
        if is_unique:
            logger.info("生成唯一图片成功", extra={"image_url": new_image_url})
            return new_image_url
    
    logger.warning(f"经过 {Config.MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一图片")
    
    # 返回最后生成的图片（降级策略）
    if last_generated_image:
        logger.info(f"降级策略：返回最后生成的图片", extra={"image_url": last_generated_image})
        return last_generated_image
    
    return None