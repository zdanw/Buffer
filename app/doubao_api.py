# -*- coding: utf-8 -*-
"""
AI模型集成模块

该模块提供与AI服务的交互功能，支持：
1. 文本生成（使用DeepSeek模型）
2. 图片生成（使用Doubao-Seedream-4.5模型）
3. 文本相似度计算（使用本地Chroma向量数据库）
4. 图片视觉相似度计算（使用CLIP模型）

依赖：
- requests: HTTP请求库
- time: 用于异步轮询
- transformers: CLIP模型库
- torch: PyTorch深度学习框架
- config.py: 配置文件
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
from PIL import Image
from config import (
    DOUBAO_API_URL,
    DOUBAO_API_KEY,
    DOUBAO_MODEL_ID,
    DOUBAO_ASPECT_RATIO,
    SIMILARITY_THRESHOLD,
    IMAGE_SIMILARITY_THRESHOLD,
    MAX_RETRY_ATTEMPTS,
    DEEPSEEK_API_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    CONTENT_GENERATION_SYSTEM_PROMPT,
    UPLOAD_DIR,
    LOGO_FILE_PATH
)

# 导入日志模块
from app.logger import get_logger
logger = get_logger(__name__)

try:
    from transformers import CLIPProcessor, CLIPModel
    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    clip_model = clip_model.to(device)
    clip_model.eval()
    CLIP_AVAILABLE = True
except Exception as e:
    logger.warning(f"CLIP model loading failed: {e}, using fallback")
    CLIP_AVAILABLE = False


def get_doubao_headers():
    """
    获取Doubao API请求头
    """
    return {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def local_image_to_base64(image_path):
    """
    将本地图片转换为Base64格式
    
    Args:
        image_path (str): 本地图片路径
        
    Returns:
        str or None: Base64编码的图片字符串（带data:image前缀），失败返回None
    """
    logger.info(f"[local_image_to_base64] 开始处理: {image_path}")
    
    try:
        # 获取文件扩展名以确定MIME类型
        _, ext = os.path.splitext(image_path)
        ext = ext.lower()
        logger.info(f"[local_image_to_base64] 检测文件扩展名: {ext}")
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.gif': 'image/gif'
        }
        
        mime_type = mime_types.get(ext, 'image/png')
        logger.info(f"[local_image_to_base64] 确定MIME类型: {mime_type}")
        
        with open(image_path, "rb") as f:
            data = f.read()
        logger.info(f"[local_image_to_base64] 图片已读取，大小: {len(data)} bytes")
        
        b64 = base64.b64encode(data).decode("utf-8")
        logger.info(f"[local_image_to_base64] Base64编码完成，长度: {len(b64)}")
        
        result = f"data:{mime_type};base64,{b64}"
        logger.info(f"[local_image_to_base64] ✅ 转换成功，前缀: {result[:60]}...")
        return result
    except Exception as e:
        logger.error(f"[local_image_to_base64] ❌ 转换失败: {image_path}, 错误: {str(e)}")
        return None


def ensure_image_url(image_source):
    """
    确保图片源是有效的URL或Base64编码
    
    Args:
        image_source (str): 图片路径、URL或Base64字符串
        
    Returns:
        str or None: 有效的图片引用（URL或Base64），失败返回None
    """
    logger.info(f"[ensure_image_url] 开始处理: {image_source[:80] if image_source else None}")
    
    if not image_source:
        logger.warning("[ensure_image_url] 输入为空")
        return None
    
    # 如果已经是URL或Base64，直接返回
    if image_source.startswith('http://') or image_source.startswith('https://'):
        logger.info(f"[ensure_image_url] ✅ 检测到HTTP/HTTPS URL，直接返回: {image_source}")
        return image_source
    
    if image_source.startswith('data:image/'):
        logger.info(f"[ensure_image_url] ✅ 检测到Base64编码，直接返回: {image_source[:60]}...")
        return image_source
    
    # 尝试作为本地文件路径处理
    logger.info(f"[ensure_image_url] 尝试作为本地文件路径处理")
    # 处理相对路径（相对于项目根目录）
    if image_source.startswith('/'):
        # 移除开头的斜杠
        image_path = image_source[1:]
    else:
        image_path = image_source
    
    # 构建完整路径
    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path)
    logger.info(f"[ensure_image_url] 构建完整路径: {full_path}")
    
    # 如果文件存在，转换为Base64
    if os.path.exists(full_path):
        logger.info(f"[ensure_image_url] ✅ 文件存在，调用local_image_to_base64转换")
        return local_image_to_base64(full_path)
    
    # 尝试直接作为绝对路径检查
    if os.path.exists(image_source):
        logger.info(f"[ensure_image_url] ✅ 绝对路径文件存在，调用local_image_to_base64转换")
        return local_image_to_base64(image_source)
    
    logger.warning(f"[ensure_image_url] ❌ 图片源未找到: {image_source}")
    return None


def generate_content(prompt, style=None):
    """
    使用DeepSeek文本模型生成文案内容

    DeepSeek API采用类似OpenAI的格式。
    
    Args:
        prompt (str): 生成提示词
        style (str, optional): 指定写作风格（幽默搞笑、温情治愈、专业测评、故事叙述、实用干货）
        
    Returns:
        str or None: 生成的文案内容或None（失败时）
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API Key not configured")
        return None
    
    # 可选的写作风格列表
    styles = ["幽默搞笑", "温情治愈", "专业测评", "故事叙述", "实用干货"]
    
    # 如果未指定风格，随机选择一个
    selected_style = style if style else random.choice(styles)
    
    # 根据风格调整温度参数
    style_temperature = {
        "幽默搞笑": 0.95,
        "温情治愈": 0.85,
        "专业测评": 0.7,
        "故事叙述": 0.9,
        "实用干货": 0.75
    }
    
    temperature = style_temperature.get(selected_style, 0.9)
    
    url = f"{DEEPSEEK_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 在prompt中添加风格指示
    styled_prompt = f"【写作风格：{selected_style}】\n{prompt}"
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": CONTENT_GENERATION_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": styled_prompt
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
        
        choices = result.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "").strip()
            logger.info("文案生成成功", extra={"content_length": len(content)})
            return content
        
        logger.warning("DeepSeek API返回空结果")
        return None
    except Exception as e:
        logger.error("DeepSeek API调用失败", extra={"error": str(e), "prompt_length": len(prompt)})
        return None


def add_logo_to_image(image_url, logo_path=LOGO_FILE_PATH, logo_size_ratio=0.15, position="bottom_left"):
    """
    将指定logo合成到生成的图片上
    
    Args:
        image_url (str): 原始图片URL
        logo_path (str): logo文件路径
        logo_size_ratio (float): logo占图片的比例（0-1）
        position (str): logo位置（top_left, top_right, bottom_left, bottom_right）
        
    Returns:
        str: 合成后的图片URL
    """
    try:
        logger.info(f"开始合成logo到图片", extra={"image_url": image_url[:50], "logo_path": logo_path})
        
        # 1. 检查logo文件是否存在
        if not os.path.exists(logo_path):
            logger.warning(f"Logo文件不存在: {logo_path}，将使用原图片")
            return image_url
        
        # 2. 下载原始图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # 3. 打开原始图片和logo
        base_img = Image.open(io.BytesIO(response.content))
        logo_img = Image.open(logo_path)
        
        # 4. 转换为RGBA模式以支持透明度
        if base_img.mode != 'RGBA':
            base_img = base_img.convert('RGBA')
        if logo_img.mode != 'RGBA':
            logo_img = logo_img.convert('RGBA')
        
        # 5. 计算logo尺寸
        base_width, base_height = base_img.size
        logo_size = int(min(base_width, base_height) * logo_size_ratio)
        logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        
        # 6. 计算logo位置
        if position == "top_left":
            logo_x, logo_y = 20, 20
        elif position == "top_right":
            logo_x, logo_y = base_width - logo_size - 20, 20
        elif position == "bottom_left":
            logo_x, logo_y = 20, base_height - logo_size - 20
        else:  # bottom_right
            logo_x, logo_y = base_width - logo_size - 20, base_height - logo_size - 20
        
        # 7. 合成logo到图片
        base_img.paste(logo_img, (logo_x, logo_y), logo_img)
        
        # 8. 转换为RGB模式并保存
        if base_img.mode == 'RGBA':
            base_img = base_img.convert('RGB')
        
        filename = f"with_logo_{uuid.uuid4()}.jpg"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, filename)
        base_img.save(file_path, 'JPEG', quality=95)
        
        # 9. 返回本地 URL
        # 这里假设本地服务器运行在 http://localhost:5000
        from flask import request
        base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
        result_url = f"{base_url}/uploads/{filename}"
        
        logger.info(f"Logo合成成功: {result_url}", extra={"logo_position": position})
        return result_url
        
    except Exception as e:
        logger.error(f"合成logo失败: {str(e)}", extra={"image_url": image_url})
        return image_url  # 失败时返回原URL


def upload_image_to_ngrok(image_url, ngrok_base_url="https://12f4-183-53-254-187.ngrok-free.app"):
    """
    将图片URL转换为ngrok可访问的URL
    
    由于ngrok服务器不支持POST上传接口，我们将图片保存到本地uploads目录，
    然后通过ngrok转发访问本地服务器的/uploads路由。
    
    Args:
        image_url (str): 原始图片URL或本地URL
        ngrok_base_url (str): ngrok服务器的基础URL
        
    Returns:
        str or None: ngrok可访问的图片URL，失败返回原URL
    """
    try:
        logger.info(f"开始处理图片URL", extra={"original_url": image_url[:50]})
        
        # 检查是否已经是本地URL或ngrok URL
        if image_url.startswith('http://localhost:') or image_url.startswith('http://127.0.0.1:'):
            # 本地URL，提取文件名
            if '/uploads/' in image_url:
                filename = image_url.split('/uploads/')[-1]
                ngrok_image_url = f"{ngrok_base_url}/uploads/{filename}"
                logger.info(f"本地URL直接转换为ngrok URL: {ngrok_image_url}")
                return ngrok_image_url
            else:
                # 不是uploads目录下的，重新下载
                pass
        
        if image_url.startswith('https://12f4-183-53-254-187.ngrok-free.app/'):
            # 已经是ngrok URL，直接返回
            logger.info(f"已经是ngrok URL: {image_url}")
            return image_url
        
        # 1. 从原URL下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # 2. 获取文件扩展名
        content_type = response.headers.get('content-type', 'image/jpeg')
        ext_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif'
        }
        ext = ext_map.get(content_type, '.jpg')
        
        # 3. 生成唯一文件名并保存到本地上传目录
        filename = f"{uuid.uuid4()}{ext}"
        
        # 确保上传目录存在
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 保存图片
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        # 记录保存路径用于调试
        logger.info(f"图片已保存到本地: {file_path}", extra={"file_size": len(response.content)})
        
        # 4. 构建ngrok可访问的URL
        ngrok_image_url = f"{ngrok_base_url}/uploads/{filename}"
        
        logger.info(f"图片保存成功，ngrok URL: {ngrok_image_url}")
        return ngrok_image_url
            
    except Exception as e:
        logger.error(f"保存图片到本地失败: {str(e)}", extra={"original_url": image_url})
        return image_url  # 失败时返回原URL


def convert_to_ngrok_url(image_url, ngrok_base_url="https://12f4-183-53-254-187.ngrok-free.app"):
    """
    将图片URL转换为ngrok可访问的URL格式
    
    如果图片已经是http/https URL，则下载并保存到本地，返回ngrok URL
    如果图片是本地路径，则上传到本地uploads目录，返回ngrok URL
    
    Args:
        image_url (str): 原始图片URL或本地路径
        ngrok_base_url (str): ngrok服务器的基础URL
        
    Returns:
        str: ngrok可访问的图片URL
    """
    logger.info(f"[convert_to_ngrok_url] 开始处理: {image_url}")
    
    if not image_url:
        logger.warning("[convert_to_ngrok_url] 输入为空")
        return None
    
    try:
        # 如果已经是http/https URL
        if image_url.startswith('http://') or image_url.startswith('https://'):
            logger.info("[convert_to_ngrok_url] 检测到HTTP/HTTPS URL")
            # 检查是否已经是ngrok URL
            if 'ngrok-free.app' in image_url:
                logger.info(f"[convert_to_ngrok_url] 已经是ngrok URL，直接返回: {image_url}")
                return image_url
            # 下载并保存到本地
            logger.info("[convert_to_ngrok_url] 调用upload_image_to_ngrok处理")
            result = upload_image_to_ngrok(image_url, ngrok_base_url)
            logger.info(f"[convert_to_ngrok_url] upload_image_to_ngrok返回: {result}")
            return result
        
        # 如果是本地路径（以/开头或相对路径）
        logger.info("[convert_to_ngrok_url] 检测到本地路径")
        # 处理相对路径（相对于项目根目录）
        if image_url.startswith('/'):
            image_path = image_url[1:]
        else:
            image_path = image_url
        
        # 构建完整路径
        full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path)
        logger.info(f"[convert_to_ngrok_url] 构建本地完整路径: {full_path}")
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            logger.warning(f"[convert_to_ngrok_url] ❌ 参考图片不存在: {full_path}")
            return None
        logger.info(f"[convert_to_ngrok_url] ✅ 参考图片文件存在")
        
        # 检查图片是否已经在 uploads 目录中
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
        if full_path.startswith(uploads_dir):
            # 图片已经在 uploads 目录中，直接返回对应的 ngrok URL
            filename = os.path.basename(full_path)
            ngrok_image_url = f"{ngrok_base_url}/uploads/{filename}"
            logger.info(f"[convert_to_ngrok_url] ✅ 图片已在uploads目录中，直接返回: {ngrok_image_url}")
            return ngrok_image_url
        
        # 图片不在 uploads 目录中，需要复制到 uploads 目录
        # 读取图片并上传
        with open(full_path, 'rb') as f:
            image_data = f.read()
        logger.info(f"[convert_to_ngrok_url] 图片已读取，大小: {len(image_data)} bytes")
        
        # 获取文件扩展名
        _, ext = os.path.splitext(full_path)
        ext = ext.lower() if ext else '.jpg'
        
        # 生成唯一文件名
        filename = f"{uuid.uuid4()}{ext}"
        
        # 确保上传目录存在
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 保存图片
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(image_data)
        logger.info(f"[convert_to_ngrok_url] 图片已保存到uploads: {file_path}")
        
        # 构建ngrok URL
        ngrok_image_url = f"{ngrok_base_url}/uploads/{filename}"
        
        logger.info(f"[convert_to_ngrok_url] ✅ 转换成功: {ngrok_image_url}")
        return ngrok_image_url
        
    except Exception as e:
        logger.error(f"[convert_to_ngrok_url] ❌ 转换参考图片URL失败: {image_url}, 错误: {str(e)}")
        return image_url  # 失败时返回原URL


def generate_image(prompt, model_id=None, aspect_ratio=None, resolution=None, max_wait_seconds=120, image_reference_url=None, use_logo_as_reference=True):
    """
    使用Doubao-Seedream-4.5图片模型生成图片

    Args:
        prompt (str): 图片生成提示词
        model_id (str, optional): 模型ID
        aspect_ratio (str): 图片宽高比（可选：1:1, 9:16, 16:9, 4:3, 3:4）
        resolution (str): 图片分辨率（可选：720p, 1080p, 2k, 4k）
        max_wait_seconds (int): 最大等待时间（秒）
        image_reference_url (str, optional): 参考图片URL，用于图像参考生成
        use_logo_as_reference (bool): 是否将logo作为参考图片传入
        
    Returns:
        str or None: 生成的图片URL或None（失败时）
    """
    if not DOUBAO_API_KEY:
        logger.error("Doubao API Key not configured")
        return None
    
    url = DOUBAO_API_URL
    headers = get_doubao_headers()
    
    # 设置默认参数
    aspect_ratio = aspect_ratio or DOUBAO_ASPECT_RATIO
    
    # 根据宽高比选择合适的尺寸（火山引擎推荐尺寸）
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
    
    # 构建请求数据（火山引擎OpenAI兼容格式）
    data = {
        "model": model_id or DOUBAO_MODEL_ID,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled"
    }
    
    # 准备参考图片列表（支持多个参考图片）
    reference_images = []
    
    # 如果提供了产品参考图片，添加到参考列表
    if image_reference_url:
        logger.info(f"[参考图片处理] 原始URL: {image_reference_url}")
        processed_url = convert_to_ngrok_url(image_reference_url)
        if processed_url:
            logger.info(f"[参考图片处理] 转换后URL: {processed_url}")
            processed_image = ensure_image_url(processed_url)
            if processed_image:
                reference_images.append({"image": processed_image, "weight": 0.8})
                logger.info(f"✅ 添加产品参考图片成功: {processed_url} (权重: 0.8)")
            else:
                logger.warning(f"❌ 产品参考图片处理失败: {processed_url}")
        else:
            logger.warning(f"❌ 产品参考图片URL转换失败: {image_reference_url}")
    
    # 如果启用logo作为参考图片，添加logo到参考列表
    if use_logo_as_reference and os.path.exists(LOGO_FILE_PATH):
        logger.info(f"[Logo参考图片处理] 文件存在: {LOGO_FILE_PATH}")
        # 直接将logo文件转换为Base64，不需要通过ngrok
        logo_base64 = local_image_to_base64(LOGO_FILE_PATH)
        if logo_base64:
            reference_images.append({"image": logo_base64, "weight": 0.2})
            logger.info(f"✅ 添加Logo参考图片成功: {LOGO_FILE_PATH} (权重: 0.2)")
        else:
            logger.warning(f"❌ Logo参考图片Base64转换失败: {LOGO_FILE_PATH}")
    elif use_logo_as_reference and not os.path.exists(LOGO_FILE_PATH):
        logger.warning(f"❌ Logo参考图片文件不存在: {LOGO_FILE_PATH}")
    
    # 设置参考图片
    if reference_images:
        logger.info("[参考图片设置] 准备发送到Doubao", extra={"total_count": len(reference_images)})
        # 如果只有一个参考图片，使用单图片模式
        if len(reference_images) == 1:
            data["image"] = reference_images[0]["image"]
            data["image_weight"] = reference_images[0]["weight"]
            logger.info(f"使用单张参考图片生成", extra={"type": "single", "weight": reference_images[0]["weight"]})
        else:
            # 多个参考图片，使用数组模式
            data["image"] = [img["image"] for img in reference_images]
            data["image_weight"] = [img["weight"] for img in reference_images]
            logger.info(f"使用多张参考图片生成", extra={"type": "multiple", "count": len(reference_images), "weights": data["image_weight"]})
    
    try:
        logger.info("调用Doubao API生成图片", extra={"prompt": prompt[:50]})
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        # 尝试解析响应，即使状态码不是200也解析错误信息
        try:
            result = response.json()
        except:
            result = {}
        
        # 检查API错误
        if "error" in result:
            error_code = result["error"].get("code", "")
            error_message = result["error"].get("message", "")
            logger.error(f"Doubao API返回错误: {error_code} - {error_message}", 
                        extra={"prompt": prompt[:50]})
            return None
        
        # 如果HTTP状态码不是200，抛出异常
        response.raise_for_status()
        
        # 解析成功响应
        if "data" in result and len(result["data"]) > 0:
            first_image = result["data"][0]
            
            # 检查单张图片是否有错误
            if "error" in first_image:
                error_code = first_image["error"].get("code", "")
                error_message = first_image["error"].get("message", "")
                logger.error(f"Doubao图片生成失败: {error_code} - {error_message}", 
                            extra={"prompt": prompt[:50]})
                return None
            
            # 获取图片URL
            image_url = first_image.get("url")
            if image_url:
                logger.info("Doubao图片生成成功", extra={"image_url": image_url[:50]})
                # 上传到ngrok服务器（不再合成logo，让模型自己生成）
                ngrok_url = upload_image_to_ngrok(image_url)
                return ngrok_url
        
        logger.warning("Doubao API返回结果格式异常", extra={"result": result})
        return None
    except Exception as e:
        logger.error("Doubao图片生成失败", extra={"error": str(e), "prompt": prompt[:50]})
        return None


def calculate_similarity(text1, text2):
    """
    计算两段文本的语义相似度
    
    Args:
        text1 (str): 第一段文本
        text2 (str): 第二段文本
        
    Returns:
        float: 相似度分数（0-1）
    """
    from app.chroma_knowledge_base import calculate_similarity as chroma_similarity
    return chroma_similarity(text1, text2)


def load_image_from_source(image_source):
    """
    从URL或本地文件路径加载图片
    
    Args:
        image_source (str): 图片的URL或本地文件路径
        
    Returns:
        PIL.Image or None: 加载的图片对象
    """
    try:
        # 1. 优先检查是否是HTTP URL（包括ngrok URL）
        if image_source.startswith(('http://', 'https://')):
            # 尝试先从本地加载（如果是ngrok URL）
            ngrok_base = "https://12f4-183-53-254-187.ngrok-free.app"
            if image_source.startswith(ngrok_base):
                # 提取文件名部分
                relative_path = image_source.replace(ngrok_base, '')
                if relative_path.startswith('/'):
                    relative_path = relative_path[1:]
                
                # 构建本地完整路径
                local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)
                
                if os.path.exists(local_path):
                    logger.debug(f"从本地路径加载ngrok URL: {local_path}")
                    return Image.open(local_path).convert("RGB")
                else:
                    logger.debug(f"ngrok URL对应的本地文件不存在，尝试从网络下载: {image_source}")
            
            # 从网络下载
            response = requests.get(image_source, stream=True, timeout=10)
            response.raise_for_status()
            return Image.open(response.raw).convert("RGB")
        # 3. 判断是否为Base64编码
        elif image_source.startswith('data:image/'):
            # 解析Base64编码的图片
            import io
            # 移除前缀
            base64_data = image_source.split(',')[1]
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        else:
            # 4. 本地文件路径 - 处理相对路径（如 /uploads/xxx.jpg）
            local_path = image_source
            if local_path.startswith('/'):
                # 移除开头的斜杠
                local_path = local_path[1:]
            
            # 构建完整路径（相对于项目根目录）
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), local_path)
            
            # 尝试完整路径
            if os.path.exists(full_path):
                return Image.open(full_path).convert("RGB")
            
            # 如果不存在，尝试直接使用原始路径（可能是绝对路径）
            if os.path.exists(image_source):
                return Image.open(image_source).convert("RGB")
            
            # 如果还是不存在，记录错误
            logger.error(f"Image file not found: {image_source} (tried: {full_path})")
            return None
    except Exception as e:
        logger.error(f"Failed to load image from {image_source}", extra={"error": str(e)})
        return None


def calculate_image_similarity(image_url1, image_url2):
    """
    计算两张图片的视觉相似度（使用CLIP模型）
    
    Args:
        image_url1 (str): 第一张图片的URL或本地路径
        image_url2 (str): 第二张图片的URL或本地路径
        
    Returns:
        float: 视觉相似度分数（0-1），1表示完全相同
    """
    if not CLIP_AVAILABLE:
        logger.warning("CLIP model not available, returning default similarity of 0")
        return 0.0
    
    try:
        # 加载图片（支持URL和本地路径）
        image1 = load_image_from_source(image_url1)
        image2 = load_image_from_source(image_url2)
        
        if image1 is None or image2 is None:
            logger.error("Failed to load one or both images")
            return 0.0
        
        # 使用CLIP处理器预处理图片（同时处理两张）
        inputs = clip_processor(images=[image1, image2], return_tensors="pt").to(device)
        
        # 获取图像编码器
        vision_model = clip_model.vision_model
        
        # 使用图像编码器获取特征
        with torch.no_grad():
            outputs = vision_model(**inputs)
        
        # 提取每张图片的特征
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


def get_embedding(text):
    """
    获取文本的嵌入向量（带缓存）
    
    Args:
        text (str): 输入文本
        
    Returns:
        numpy.ndarray: 嵌入向量
    """
    if text in _embedding_cache:
        return _embedding_cache[text]
    
    from app.chroma_knowledge_base import sentence_transformer_ef
    embedding = sentence_transformer_ef([text])[0]
    _embedding_cache[text] = embedding
    
    # 限制缓存大小，防止内存溢出
    if len(_embedding_cache) > 1000:
        # 删除最旧的一半缓存
        keys = list(_embedding_cache.keys())[:500]
        for key in keys:
            del _embedding_cache[key]
    
    return embedding


def batch_calculate_similarity(new_embedding, existing_embeddings):
    """
    批量计算新向量与多个已有向量的相似度
    
    Args:
        new_embedding (numpy.ndarray): 新内容的嵌入向量
        existing_embeddings (list): 已有内容的嵌入向量列表
        
    Returns:
        numpy.ndarray: 相似度数组
    """
    if not existing_embeddings:
        return np.array([])
    
    # 将列表转换为矩阵
    existing_matrix = np.array(existing_embeddings)
    
    # 计算余弦相似度（向量化操作，比循环快10-100倍）
    new_norm = np.linalg.norm(new_embedding)
    existing_norms = np.linalg.norm(existing_matrix, axis=1)
    
    # 避免除以零
    mask = existing_norms > 0
    if not np.any(mask):
        return np.zeros(len(existing_embeddings))
    
    dot_products = existing_matrix @ new_embedding
    similarities = dot_products / (new_norm * existing_norms)
    
    # 处理零范数的情况
    similarities[~mask] = 0.0
    
    return similarities


def is_text_exact_duplicate(text1, text2):
    """
    检查两段文本是否为精确重复（非语义，简单检查）
    
    Args:
        text1 (str): 文本1
        text2 (str): 文本2
        
    Returns:
        bool: 是否为精确重复
    """
    # 移除标点符号和空格后的比较
    def clean_text(text):
        import re
        text = text.lower()
        # 移除标点和空格
        text = re.sub(r'[^\w]', '', text)
        return text
    
    clean1 = clean_text(text1)
    clean2 = clean_text(text2)
    
    # 精确匹配或几乎完全匹配
    if clean1 == clean2:
        return True
    
    # 检查是否只是顺序或部分内容变化
    # 如果是英文，检查是否只是单词顺序变化
    if any(ord(c) < 128 for c in text1):
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0
        if jaccard > 0.9:
            logger.info(f"检测到高Jaccard相似度: {jaccard:.2f}，判定为重复")
            return True
    
    return False


def is_content_unique_optimized(new_content, threshold=SIMILARITY_THRESHOLD, top_k=20):
    """
    使用Chroma向量索引快速检测内容是否唯一（适用于大规模知识库）
    
    算法原理：
    1. 使用Chroma的近似最近邻搜索（HNSW算法）快速找到最相似的top_k条内容
    2. 只对这top_k条进行精确相似度计算
    3. 复杂度从O(n)降为O(log n) + O(k)
    
    Args:
        new_content (str): 新内容
        threshold (float): 相似度阈值
        top_k (int): 检索的候选数量
        
    Returns:
        bool: 是否唯一（True=唯一，False=重复）
    """
    from app.chroma_knowledge_base import collection
    
    if not new_content or not new_content.strip():
        return False
    
    try:
        # 使用Chroma索引快速搜索最相似的top_k条内容
        results = collection.query(
            query_texts=[new_content],
            n_results=top_k
        )
        
        # 获取距离并转换为相似度
        if results['distances'][0]:
            # 距离越小越相似，转换为相似度：similarity = 1 - distance
            similarities = [1 - d for d in results['distances'][0]]
            
            # 检查是否有超过阈值的相似度
            max_similarity = max(similarities)
            if max_similarity >= threshold:
                logger.debug(f"找到相似内容，相似度: {max_similarity:.4f}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"使用Chroma索引检测失败，降级到逐条比较: {str(e)}")
        return None  # 返回None表示降级


def generate_unique_content(base_prompt, existing_contents):
    """
    生成不重复的文案内容（优化版，支持大规模知识库）
    
    Args:
        base_prompt (str): 基础提示词
        existing_contents (list): 已存在的文案列表
        
    Returns:
        str or None: 生成的唯一文案或None
    """
    # 记录待比较的文案数量
    valid_contents = [c for c in existing_contents if c and c.strip()]
    logger.info(f"开始生成唯一文案，待比较文案数量: {len(valid_contents)}", extra={"existing_count": len(valid_contents)})
    
    # 如果没有现有文案，直接生成并返回（不重试）
    if len(valid_contents) == 0:
        logger.info("知识库为空，直接生成文案（不进行重复检测）")
        new_content = generate_content(base_prompt)
        return new_content
    
    # 判断是否使用优化算法（大规模数据时使用Chroma索引）
    use_optimized = len(valid_contents) > 50  # 超过50条时使用Chroma索引
    
    # 优化：降低初始重试的严格度，逐步放宽要求
    # 第1次尝试：严格阈值（SIMILARITY_THRESHOLD）
    # 第2次尝试：中等阈值（SIMILARITY_THRESHOLD + 0.05）
    # 第3次尝试：宽松阈值（SIMILARITY_THRESHOLD + 0.1）
    threshold_adjustments = [0, 0.05, 0.1]
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        logger.info(f"文案生成尝试 {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
        new_content = generate_content(base_prompt)
        if not new_content:
            logger.warning(f"文案生成失败，继续重试")
            continue
        
        # 逐步放宽阈值，避免无限循环
        current_threshold = SIMILARITY_THRESHOLD + threshold_adjustments[min(attempt, len(threshold_adjustments)-1)]
        logger.info(f"当前尝试阈值: {current_threshold:.2f}（原始: {SIMILARITY_THRESHOLD}）")
        
        # 先做快速精确重复检查
        is_exact_duplicate = False
        for existing in valid_contents:
            if is_text_exact_duplicate(new_content, existing):
                is_exact_duplicate = True
                logger.info(f"检测到精确重复文案，跳过")
                break
        
        if is_exact_duplicate:
            continue
        
        if use_optimized:
            # 大规模数据：使用Chroma索引快速检测
            is_unique = is_content_unique_optimized(new_content, threshold=current_threshold)
            
            if is_unique is None:
                # 降级到逐条比较
                use_optimized = False
                logger.info("Chroma索引检测失败，降级到批量比较")
            elif is_unique:
                logger.info(f"文案通过Chroma索引检测（唯一），生成成功")
                return new_content
            else:
                logger.info(f"内容重复检测(优化): 重试第 {attempt + 1} 次")
                continue
        
        # 小规模数据或降级情况：使用向量化批量比较
        existing_embeddings = []
        for content in valid_contents:
            if content.strip():
                existing_embeddings.append(get_embedding(content))
        
        new_embedding = get_embedding(new_content)
        similarities = batch_calculate_similarity(new_embedding, existing_embeddings)
        
        max_similarity = np.max(similarities) if len(similarities) > 0 else 0.0
        
        if len(similarities) == 0 or max_similarity < current_threshold:
            logger.info(f"文案通过相似度检测（相似度: {max_similarity:.4f} < {current_threshold:.2f}），生成成功")
            return new_content
        
        # 找出最相似的文案用于调试
        if len(similarities) > 0:
            most_similar_idx = np.argmax(similarities)
            most_similar_content = valid_contents[most_similar_idx][:60] + "..."
            logger.info(f"最相似文案: {most_similar_content}，相似度: {max_similarity:.4f}")
        
        logger.info(f"内容重复检测(批量): 最高相似度 {max_similarity:.4f} >= {current_threshold:.2f}，重试第 {attempt + 1} 次")
    
    logger.warning(f"经过 {MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一文案，返回最后一次结果")
    return new_content


def generate_unique_image(base_prompt, existing_images_info, model_id=None, reference_image_url=None):
    """
    生成不重复的图片（使用视觉相似度检测）
    
    Args:
        base_prompt (str): 基础图片提示词
        existing_images_info (list): 已存在的图片信息列表，每个元素包含 'image_url' 和 'prompt' 字段
        model_id (str, optional): 图片生成模型ID
        reference_image_url (str, optional): 参考图片URL，用于图像参考生成
        
    Returns:
        str or None: 生成的图片URL或None
    """
    logger.info("开始生成唯一图片", extra={"prompt": base_prompt[:50], "attempts": MAX_RETRY_ATTEMPTS})
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        logger.debug(f"图片生成尝试 {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
        
        new_image_url = generate_image(base_prompt, model_id=model_id, image_reference_url=reference_image_url)
        if not new_image_url:
            logger.warning(f"图片生成失败，尝试 {attempt + 1}")
            continue
        
        is_unique = True
        
        if CLIP_AVAILABLE:
            # 使用CLIP进行视觉相似度比较
            for existing_image in existing_images_info:
                existing_image_url = existing_image.get('image_url')
                if existing_image_url:
                    similarity = calculate_image_similarity(new_image_url, existing_image_url)
                    if similarity >= IMAGE_SIMILARITY_THRESHOLD:
                        logger.debug(f"视觉相似度 {similarity:.4f} 超过阈值 {IMAGE_SIMILARITY_THRESHOLD}")
                        is_unique = False
                        break
        else:
            # 降级方案：使用文本相似度比较
            for existing_image in existing_images_info:
                existing_prompt = existing_image.get('prompt', '')
                if existing_prompt:
                    similarity = calculate_similarity(base_prompt, existing_prompt)
                    if similarity >= SIMILARITY_THRESHOLD:
                        logger.debug(f"提示词相似度 {similarity:.4f} 超过阈值 {SIMILARITY_THRESHOLD}")
                        is_unique = False
                        break
        
        if is_unique:
            logger.info("生成唯一图片成功", extra={"image_url": new_image_url})
            return new_image_url
    
    logger.warning(f"经过 {MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一图片")
    return None
