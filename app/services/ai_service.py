# -*- coding: utf-8 -*-
"""
AI模型集成服务模块

该模块提供与AI服务的交互功能，支持：
1. 文本生成（使用DeepSeek模型）
2. 图片生成（使用Doubao-Seedream-4.5模型）
3. 文本相似度计算
4. 图片视觉相似度计算（使用CLIP模型）
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

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

_initialized = False

if not _initialized:
    _initialized = True
    
    try:
        from app.services.github_service import upload_image_to_github, convert_github_url_to_cdn
        logger.info("✅ GitHub 图床模块导入成功")
    except Exception as e:
        logger.warning(f"❌ 导入 GitHub 图床模块失败: {e}")
        upload_image_to_github = None
        convert_github_url_to_cdn = None

    local_model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')

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
    return {
        "Authorization": f"Bearer {Config.DOUBAO_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def local_image_to_base64(image_path):
    logger.info(f"[local_image_to_base64] 开始处理: {image_path}")
    
    try:
        _, ext = os.path.splitext(image_path)
        ext = ext.lower()
        
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
        
        with open(image_path, "rb") as f:
            data = f.read()
        
        b64 = base64.b64encode(data).decode("utf-8")
        result = f"data:{mime_type};base64,{b64}"
        
        logger.info(f"[local_image_to_base64] ✅ 转换成功")
        return result
    except Exception as e:
        logger.error(f"[local_image_to_base64] ❌ 转换失败: {str(e)}")
        return None


def download_image_to_base64(image_url):
    try:
        logger.info(f"[download_image_to_base64] 开始下载: {image_url[:50]}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', 'image/jpeg')
        ext_map = {
            'image/jpeg': 'image/jpeg',
            'image/png': 'image/png',
            'image/webp': 'image/webp',
            'image/gif': 'image/gif',
            'image/bmp': 'image/bmp'
        }
        mime_type = ext_map.get(content_type, 'image/jpeg')
        
        base64_encoded = base64.b64encode(response.content).decode('utf-8')
        result = f"data:{mime_type};base64,{base64_encoded}"
        
        logger.info(f"[download_image_to_base64] ✅ 下载并转换成功")
        return result
    except Exception as e:
        logger.error(f"[download_image_to_base64] ❌ 下载失败: {str(e)}")
        return None


def ensure_image_url(image_source, force_download=False):
    logger.info(f"[ensure_image_url] 开始处理: {image_source[:80] if image_source else None}")
    
    if not image_source:
        logger.warning("[ensure_image_url] 输入为空")
        return None
    
    if image_source.startswith('data:image/'):
        logger.info(f"[ensure_image_url] ✅ 检测到Base64编码，直接返回")
        return image_source
    
    if image_source.startswith('http://') or image_source.startswith('https://'):
        if force_download:
            logger.info(f"[ensure_image_url] 强制下载并转换为Base64")
            return download_image_to_base64(image_source)
        else:
            logger.info(f"[ensure_image_url] ✅ 检测到HTTP/HTTPS URL，直接返回（不下载）")
            return image_source
    
    logger.info(f"[ensure_image_url] 尝试作为本地文件路径处理")
    
    if image_source.startswith('/'):
        image_path = image_source[1:]
    else:
        image_path = image_source
    
    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), image_path)
    
    if os.path.exists(full_path):
        logger.info(f"[ensure_image_url] ✅ 文件存在，调用local_image_to_base64转换")
        return local_image_to_base64(full_path)
    
    if os.path.exists(image_source):
        logger.info(f"[ensure_image_url] ✅ 绝对路径文件存在，调用local_image_to_base64转换")
        return local_image_to_base64(image_source)
    
    logger.warning(f"[ensure_image_url] ❌ 图片源未找到: {image_source}")
    return None


def generate_content(prompt, style=None):
    if not Config.DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API Key not configured")
        return None
    
    styles = ["幽默搞笑", "温情治愈", "专业测评", "故事叙述", "实用干货"]
    selected_style = style if style else random.choice(styles)
    
    style_temperature = {
        "幽默搞笑": 0.95,
        "温情治愈": 0.85,
        "专业测评": 0.7,
        "故事叙述": 0.9,
        "实用干货": 0.75
    }
    
    temperature = style_temperature.get(selected_style, 0.9)
    
    url = f"{Config.DEEPSEEK_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    styled_prompt = f"【写作风格：{selected_style}】\n{prompt}"
    
    data = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": Config.CONTENT_GENERATION_SYSTEM_PROMPT
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


def add_logo_to_image(image_url, logo_path=Config.LOGO_FILE_PATH, logo_size_ratio=0.15, position="bottom_left"):
    try:
        logger.info(f"开始合成logo到图片", extra={"image_url": image_url[:50], "logo_path": logo_path})
        
        if not os.path.exists(logo_path):
            logger.warning(f"Logo文件不存在: {logo_path}，将使用原图片")
            return image_url
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        base_img = Image.open(io.BytesIO(response.content))
        logo_img = Image.open(logo_path)
        
        if base_img.mode != 'RGBA':
            base_img = base_img.convert('RGBA')
        if logo_img.mode != 'RGBA':
            logo_img = logo_img.convert('RGBA')
        
        base_width, base_height = base_img.size
        logo_size = int(min(base_width, base_height) * logo_size_ratio)
        logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        
        if position == "top_left":
            logo_x, logo_y = 20, 20
        elif position == "top_right":
            logo_x, logo_y = base_width - logo_size - 20, 20
        elif position == "bottom_left":
            logo_x, logo_y = 20, base_height - logo_size - 20
        else:
            logo_x, logo_y = base_width - logo_size - 20, base_height - logo_size - 20
        
        base_img.paste(logo_img, (logo_x, logo_y), logo_img)
        
        if base_img.mode == 'RGBA':
            base_img = base_img.convert('RGB')
        
        filename = f"with_logo_{uuid.uuid4()}.jpg"
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        base_img.save(file_path, 'JPEG', quality=95)
        
        if upload_image_to_github:
            try:
                github_cdn_url = upload_image_to_github(file_path)
                if github_cdn_url:
                    logger.info("✅ 带Logo的图片已上传到 GitHub 图床", extra={"cdn_url": github_cdn_url})
                    return github_cdn_url
            except Exception as e:
                logger.warning(f"带Logo的图片上传到 GitHub 失败: {e}")
        
        from flask import request
        base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
        result_url = f"{base_url}/uploads/{filename}"
        
        logger.info(f"Logo合成成功: {result_url}", extra={"logo_position": position})
        return result_url
        
    except Exception as e:
        logger.error(f"合成logo失败: {str(e)}", extra={"image_url": image_url})
        return image_url


def generate_image(prompt, model_id=None, aspect_ratio=None, resolution=None, max_wait_seconds=120, image_reference_url=None, use_logo_as_reference=True):
    if not Config.DOUBAO_API_KEY:
        logger.error("Doubao API Key not configured")
        return None
    
    url = Config.DOUBAO_API_URL
    headers = get_doubao_headers()
    
    aspect_ratio = aspect_ratio or Config.DOUBAO_ASPECT_RATIO
    
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
    
    data = {
        "model": model_id or Config.DOUBAO_MODEL_ID,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled"
    }
    
    reference_images = []
    
    if image_reference_url:
        logger.info(f"[参考图片处理] 原始URL: {image_reference_url}")
        
        use_direct_url = hasattr(Config, 'DOUBAO_DIRECT_URL_SUPPORT') and Config.DOUBAO_DIRECT_URL_SUPPORT
        processed_image = ensure_image_url(image_reference_url, force_download=not use_direct_url)
        
        if processed_image:
            reference_images.append({"image": processed_image, "weight": 0.8})
            if use_direct_url:
                logger.info(f"✅ 直接传递URL作为参考图片 (权重: 0.8)")
            else:
                logger.info(f"✅ 添加产品参考图片成功 (权重: 0.8)")
        else:
            logger.warning(f"❌ 产品参考图片处理失败: {image_reference_url}")
    
    if use_logo_as_reference and os.path.exists(Config.LOGO_FILE_PATH):
        logger.info(f"[Logo参考图片处理] 文件存在: {Config.LOGO_FILE_PATH}")
        logo_base64 = local_image_to_base64(Config.LOGO_FILE_PATH)
        if logo_base64:
            reference_images.append({"image": logo_base64, "weight": 0.2})
            logger.info(f"✅ 添加Logo参考图片成功: {Config.LOGO_FILE_PATH} (权重: 0.2)")
        else:
            logger.warning(f"❌ Logo参考图片Base64转换失败: {Config.LOGO_FILE_PATH}")
    elif use_logo_as_reference and not os.path.exists(Config.LOGO_FILE_PATH):
        logger.warning(f"❌ Logo参考图片文件不存在: {Config.LOGO_FILE_PATH}")
    
    if reference_images:
        logger.info("[参考图片设置] 准备发送到Doubao", extra={"total_count": len(reference_images)})
        if len(reference_images) == 1:
            data["image"] = reference_images[0]["image"]
            data["image_weight"] = reference_images[0]["weight"]
        else:
            data["image"] = [img["image"] for img in reference_images]
            data["image_weight"] = [img["weight"] for img in reference_images]
    
    try:
        logger.info("调用Doubao API生成图片", extra={"prompt": prompt[:50]})
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        try:
            result = response.json()
        except:
            result = {}
        
        if "error" in result:
            error_code = result["error"].get("code", "")
            error_message = result["error"].get("message", "")
            logger.error(f"Doubao API返回错误: {error_code} - {error_message}", 
                        extra={"prompt": prompt[:50]})
            return None
        
        response.raise_for_status()
        
        if "data" in result and len(result["data"]) > 0:
            first_image = result["data"][0]
            
            if "error" in first_image:
                error_code = first_image["error"].get("code", "")
                error_message = first_image["error"].get("message", "")
                logger.error(f"Doubao图片生成失败: {error_code} - {error_message}", 
                            extra={"prompt": prompt[:50]})
                return None
            
            image_url = first_image.get("url")
            if image_url:
                logger.info("Doubao图片生成成功", extra={"image_url": image_url[:50]})
                
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
    except Exception as e:
        logger.error("Doubao图片生成失败", extra={"error": str(e), "prompt": prompt[:50]})
        return None


def calculate_similarity(text1, text2):
    from app.services.chroma_service import calculate_similarity as chroma_similarity
    return chroma_similarity(text1, text2)


def load_image_from_source(image_source):
    try:
        if image_source.startswith(('http://', 'https://')):
            response = requests.get(image_source, stream=True, timeout=10)
            response.raise_for_status()
            return Image.open(response.raw).convert("RGB")
        elif image_source.startswith('data:image/'):
            import io
            base64_data = image_source.split(',')[1]
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        else:
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
    if not CLIP_AVAILABLE:
        logger.warning("CLIP model not available, returning default similarity of 0")
        return 0.0
    
    try:
        image1 = load_image_from_source(image_url1)
        image2 = load_image_from_source(image_url2)
        
        if image1 is None or image2 is None:
            logger.error("Failed to load one or both images")
            return 0.0
        
        inputs = clip_processor(images=[image1, image2], return_tensors="pt").to(device)
        
        vision_model = clip_model.vision_model
        
        with torch.no_grad():
            outputs = vision_model(**inputs)
        
        feature1 = outputs.pooler_output[0:1]
        feature2 = outputs.pooler_output[1:2]
        
        similarity = torch.nn.functional.cosine_similarity(feature1, feature2).item()
        
        logger.debug(f"Image similarity calculated: {similarity}")
        return similarity
        
    except Exception as e:
        logger.error("Error calculating image similarity", extra={"error": str(e)})
        return 0.0


_embedding_cache = {}


def get_embedding(text):
    if text in _embedding_cache:
        return _embedding_cache[text]
    
    from app.services.chroma_service import sentence_transformer_ef
    embedding = sentence_transformer_ef([text])[0]
    _embedding_cache[text] = embedding
    
    if len(_embedding_cache) > 1000:
        keys = list(_embedding_cache.keys())[:500]
        for key in keys:
            del _embedding_cache[key]
    
    return embedding


def batch_calculate_similarity(new_embedding, existing_embeddings):
    if not existing_embeddings:
        return np.array([])
    
    existing_matrix = np.array(existing_embeddings)
    
    new_norm = np.linalg.norm(new_embedding)
    existing_norms = np.linalg.norm(existing_matrix, axis=1)
    
    mask = existing_norms > 0
    if not np.any(mask):
        return np.zeros(len(existing_embeddings))
    
    dot_products = existing_matrix @ new_embedding
    similarities = dot_products / (new_norm * existing_norms)
    
    similarities[~mask] = 0.0
    
    return similarities


def is_text_exact_duplicate(text1, text2):
    def clean_text(text):
        import re
        text = text.lower()
        text = re.sub(r'[^\w]', '', text)
        return text
    
    clean1 = clean_text(text1)
    clean2 = clean_text(text2)
    
    if clean1 == clean2:
        return True
    
    if any(ord(c) < 128 for c in text1):
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0
        if jaccard > 0.9:
            logger.info(f"检测到高Jaccard相似度: {jaccard:.2f}，判定为重复")
            return True
    
    return False


def is_content_unique_optimized(new_content, threshold=Config.SIMILARITY_THRESHOLD, top_k=20):
    from app.services.chroma_service import collection
    
    if not new_content or not new_content.strip():
        return False
    
    try:
        results = collection.query(
            query_texts=[new_content],
            n_results=top_k
        )
        
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
    valid_contents = [c for c in existing_contents if c and c.strip()]
    logger.info(f"开始生成唯一文案，待比较文案数量: {len(valid_contents)}")
    
    if len(valid_contents) == 0:
        logger.info("知识库为空，直接生成文案（不进行重复检测）")
        new_content = generate_content(base_prompt)
        return new_content
    
    use_optimized = len(valid_contents) > 50
    
    threshold_adjustments = [0, 0.05, 0.1]
    
    for attempt in range(Config.MAX_RETRY_ATTEMPTS):
        logger.info(f"文案生成尝试 {attempt + 1}/{Config.MAX_RETRY_ATTEMPTS}")
        new_content = generate_content(base_prompt)
        if not new_content:
            logger.warning(f"文案生成失败，继续重试")
            continue
        
        current_threshold = Config.SIMILARITY_THRESHOLD + threshold_adjustments[min(attempt, len(threshold_adjustments)-1)]
        logger.info(f"当前尝试阈值: {current_threshold:.2f}")
        
        is_exact_duplicate = False
        for existing in valid_contents:
            if is_text_exact_duplicate(new_content, existing):
                is_exact_duplicate = True
                logger.info(f"检测到精确重复文案，跳过")
                break
        
        if is_exact_duplicate:
            continue
        
        if use_optimized:
            is_unique = is_content_unique_optimized(new_content, threshold=current_threshold)
            
            if is_unique is None:
                use_optimized = False
                logger.info("Chroma索引检测失败，降级到批量比较")
            elif is_unique:
                logger.info(f"文案通过Chroma索引检测（唯一），生成成功")
                return new_content
            else:
                logger.info(f"内容重复检测(优化): 重试第 {attempt + 1} 次")
                continue
        
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
        
        if len(similarities) > 0:
            most_similar_idx = np.argmax(similarities)
            most_similar_content = valid_contents[most_similar_idx][:60] + "..."
            logger.info(f"最相似文案: {most_similar_content}，相似度: {max_similarity:.4f}")
        
        logger.info(f"内容重复检测(批量): 最高相似度 {max_similarity:.4f} >= {current_threshold:.2f}，重试第 {attempt + 1} 次")
    
    logger.warning(f"经过 {Config.MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一文案，返回最后一次结果")
    return new_content


def generate_unique_image(base_prompt, existing_images_info, model_id=None, reference_image_url=None):
    logger.info("开始生成唯一图片", extra={"prompt": base_prompt[:50], "attempts": Config.MAX_RETRY_ATTEMPTS})
    
    for attempt in range(Config.MAX_RETRY_ATTEMPTS):
        logger.debug(f"图片生成尝试 {attempt + 1}/{Config.MAX_RETRY_ATTEMPTS}")
        
        new_image_url = generate_image(base_prompt, model_id=model_id, image_reference_url=reference_image_url)
        if not new_image_url:
            logger.warning(f"图片生成失败，尝试 {attempt + 1}")
            continue
        
        is_unique = True
        
        if CLIP_AVAILABLE:
            for existing_image in existing_images_info:
                existing_image_url = existing_image.get('image_url')
                if existing_image_url:
                    similarity = calculate_image_similarity(new_image_url, existing_image_url)
                    if similarity >= Config.IMAGE_SIMILARITY_THRESHOLD:
                        logger.debug(f"视觉相似度 {similarity:.4f} 超过阈值 {Config.IMAGE_SIMILARITY_THRESHOLD}")
                        is_unique = False
                        break
        else:
            for existing_image in existing_images_info:
                existing_prompt = existing_image.get('prompt', '')
                if existing_prompt:
                    similarity = calculate_similarity(base_prompt, existing_prompt)
                    if similarity >= Config.SIMILARITY_THRESHOLD:
                        logger.debug(f"提示词相似度 {similarity:.4f} 超过阈值 {Config.SIMILARITY_THRESHOLD}")
                        is_unique = False
                        break
        
        if is_unique:
            logger.info("生成唯一图片成功", extra={"image_url": new_image_url})
            return new_image_url
    
    logger.warning(f"经过 {Config.MAX_RETRY_ATTEMPTS} 次尝试仍无法生成唯一图片")
    return None