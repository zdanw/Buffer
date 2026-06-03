# -*- coding: utf-8 -*-
"""
内容发布API蓝本

该模块提供内容生成和发布接口，主要功能包括：
1. 内容生成：生成社交媒体文案和图片
2. 内容重新生成：支持单独重新生成文案或图片
3. 内容发布：发布到指定的社交平台
4. 全自动发布：一键完成内容生成和发布
5. 知识库内容生成：为知识库条目生成文案
6. 保存到知识库：将生成的内容保存到知识库（无需发布）

API端点列表：
- POST /api/generate - 生成内容（文案+图片）
- POST /api/regenerate - 重新生成内容
- POST /api/publish - 发布内容到社交平台
- POST /api/auto_publish - 全自动发布
- POST /api/generate-content - 为知识库生成文案
- POST /api/save-to-knowledge - 保存生成的内容到知识库
"""

from flask import request, jsonify

from app.services.buffer_service import publish_to_platforms
from app.services.ai_service import generate_unique_content, generate_unique_image, generate_content, build_image_prompt
from app.services.chroma_service import get_random_entry_by_product, get_all_entries, add_entry, get_entry_by_id, update_publish_count
from app.services.github_service import upload_image_to_github, is_configured as is_github_configured, convert_github_url_to_cdn
from app.services.logger import get_logger
from app.config import Config
from app.api import api_bp

logger = get_logger(__name__)


@api_bp.route('/generate', methods=['POST'])
def generate():
    """
    生成社交媒体内容（文案+图片）
    
    根据产品名称生成独特的社交媒体文案和图片，确保与已有内容不重复。
    
    请求参数（JSON）：
    - product_name (str): 产品名称
    - mode (str, optional): 生成模式，默认'semi_auto'
    - entry_id (str, optional): 指定的条目ID
    
    返回值（JSON）：
    {
        "original_entry": 原始条目信息,
        "generated_content": 生成的文案内容,
        "generated_image": 生成的图片URL,
        "mode": 生成模式
    }
    """
    data = request.json
    product_name = data.get('product_name', '')
    mode = data.get('mode', 'semi_auto')
    entry_id = data.get('entry_id')
    
    logger.info("开始生成内容", extra={"product_name": product_name, "mode": mode, "entry_id": entry_id})
    
    try:
        entry = None
        # 如果指定了条目ID，使用指定条目
        if entry_id:
            entry = get_entry_by_id(entry_id)
            logger.info(f"使用前端指定的条目: {entry_id}")
        
        # 如果没有指定条目或指定条目不存在，随机获取一个相关条目
        if not entry:
            entry = get_random_entry_by_product(product_name)
        
        if not entry:
            logger.warning("未找到相关产品", extra={"product_name": product_name})
            return jsonify({"error": "未找到相关产品"}), 404
        
        logger.info("找到相关条目", extra={"entry_id": entry.get('id'), "product_name": entry.get('产品名称')})
        
        # 获取所有已有内容用于去重检测
        all_entries = get_all_entries()
        existing_contents = [e['文案内容'] for e in all_entries]
        existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in all_entries]
        
        # 获取参考图片
        reference_image_url = entry.get('image_url')
        
        # 生成独特文案（直接传递产品信息）
        product_description = f"产品名称: {entry['产品名称']}"
        if '文案内容' in entry and entry['文案内容']:
            product_description += f"\n参考文案: {entry['文案内容'][:100]}..."
        content_result = generate_unique_content(product_description, existing_contents)
        new_content = content_result["content"] if content_result else None
        content_prompt = content_result["prompt"] if content_result else ""
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        # 生成独特图片（使用配置化的提示词生成函数）
        product_description = entry.get('产品名称', '') + ' ' + entry.get('文案内容', '')[:100]
        image_prompt = build_image_prompt(product_description)
        new_image = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        logger.info("图片生成完成", extra={"image_url": new_image})
        
        result = {
            "original_entry": entry,
            "generated_content": new_content,
            "generated_image": new_image,
            "content_prompt": content_prompt,
            "image_prompt": image_prompt,
            "mode": mode
        }
        
        logger.info("内容生成成功", extra={"product_name": product_name, "mode": mode})
        return jsonify(result)
        
    except Exception as e:
        logger.error("内容生成失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"内容生成失败: {str(e)}"}), 500


@api_bp.route('/regenerate', methods=['POST'])
def regenerate():
    """
    重新生成内容（支持单独重新生成文案或图片）
    
    请求参数（JSON）：
    - original_entry (dict): 原始条目信息（必须包含'产品名称'字段）
    - type (str, optional): 重新生成类型，可选'content'、'image'、'both'，默认'both'
    
    返回值（JSON）：
    {
        "generated_content": 重新生成的文案（如果type包含'content'）,
        "generated_image": 重新生成的图片（如果type包含'image'）
    }
    """
    data = request.json
    original_entry = data.get('original_entry')
    regenerate_type = data.get('type', 'both')
    
    # 参数校验
    if not original_entry:
        return jsonify({"error": "缺少必要参数: original_entry"}), 400
    
    # 获取已有内容用于去重检测
    existing_contents = [e['文案内容'] for e in get_all_entries()]
    existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in get_all_entries()]
    
    # 获取参考图片
    reference_image_url = original_entry.get('image_url')
    
    result = {}
    
    # 重新生成文案（直接传递产品信息）
    if regenerate_type == 'content' or regenerate_type == 'both':
        if '产品名称' not in original_entry:
            return jsonify({"error": "original_entry 缺少必要字段: 产品名称"}), 400
        product_description = f"产品名称: {original_entry['产品名称']}"
        if '文案内容' in original_entry and original_entry['文案内容']:
            product_description += f"\n参考文案: {original_entry['文案内容'][:100]}..."
        content_result = generate_unique_content(product_description, existing_contents)
        result['generated_content'] = content_result["content"] if content_result else None
        result['content_prompt'] = content_result["prompt"] if content_result else ""
    
    # 重新生成图片（使用配置化的提示词生成函数）
    if regenerate_type == 'image' or regenerate_type == 'both':
        product_description = original_entry.get('产品名称', '') + ' ' + original_entry.get('文案内容', '')[:100]
        image_prompt = build_image_prompt(product_description)
        result['generated_image'] = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        result['image_prompt'] = image_prompt
    
    return jsonify(result)


@api_bp.route('/publish', methods=['POST'])
def publish():
    """
    发布内容到社交平台
    
    将指定的文案和图片发布到指定的社交平台，并将发布成功的内容保存到知识库。
    
    请求参数（JSON）：
    - text (str): 文案内容
    - image_url (str): 图片URL
    - platforms (list, optional): 目标平台列表，默认['tiktok', 'instagram', 'facebook']
    - product_name (str, optional): 产品名称
    - immediate (bool, optional): 是否立即发布，默认False（定时发布）
    - source (str, optional): 内容来源，'knowledge'表示来自知识库，'new'表示新生成，默认'new'
    - entry_id (str, optional): 知识库条目ID（当source为'knowledge'时需要）
    - schedule_time (str, optional): 定时发布时间（ISO格式）
    
    返回值（JSON）：
    {
        "status": "completed",
        "publish_results": 各平台发布结果列表,
        "success_count": 成功发布的平台数量
    }
    """
    data = request.json
    text = data.get('text', '')
    image_url = data.get('image_url', '')
    platforms = data.get('platforms', ['tiktok', 'instagram', 'facebook'])
    product_name = data.get('产品名称', '')
    immediate = data.get('immediate', False)
    source = data.get('source', 'new')
    entry_id = data.get('entry_id')
    schedule_time = data.get('schedule_time')
    
    logger.info("开始发布内容", extra={
        "product_name": product_name, 
        "platforms": platforms, 
        "text_length": len(text), 
        "immediate": immediate, 
        "source": source,
        "schedule_time": schedule_time
    })
    
    try:
        uploaded_image_url = image_url
        
        # 如果图片不在GitHub CDN上，先上传到GitHub图床
        if image_url and is_github_configured(log_enabled=False):
            logger.info("发布前上传图片到 GitHub 图床", extra={"image_url": image_url[:50]})
            try:
                if "cdn.jsdelivr.net" not in image_url and "github.com" not in image_url:
                    github_url = upload_image_to_github(image_url, product_name=product_name)
                    if github_url:
                        cdn_url = convert_github_url_to_cdn(github_url) if convert_github_url_to_cdn else github_url
                        uploaded_image_url = cdn_url
                        logger.info("✅ 图片上传到 GitHub 成功", extra={"cdn_url": uploaded_image_url})
                    else:
                        logger.warning("❌ 图片上传到 GitHub 失败，将使用原URL")
                else:
                    logger.info("图片已在 GitHub CDN，无需重新上传")
            except Exception as e:
                logger.error(f"❌ 上传图片到 GitHub 时发生错误: {e}")
        
        # 发布到各个平台
        results = publish_to_platforms(text, uploaded_image_url, platforms, immediate, schedule_time, product_name=product_name)
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info("发布完成", extra={"success_count": success_count, "total_platforms": len(platforms)})
        
        # 获取调整后的图片URL（TikTok或Facebook）
        tiktok_resized_url = None
        for r in results:
            if r['status'] == 'success' and r.get('resized_url'):
                tiktok_resized_url = r['resized_url']
                logger.info(f"图片已调整尺寸: {tiktok_resized_url[:50]} (平台: {r.get('platform')})")
                break
        
        # 如果发布成功，保存到知识库
        if success_count > 0:
            if source == 'knowledge' and entry_id:
                # 更新已存在条目的发布次数
                try:
                    updated_entry = update_publish_count(entry_id)
                    if updated_entry:
                        logger.info("知识库内容发布次数已更新", extra={"entry_id": entry_id, "publish_count": updated_entry.get('发布次数')})
                    else:
                        logger.warning("更新发布次数失败，条目可能不存在", extra={"entry_id": entry_id})
                except Exception as e:
                    logger.error("更新知识库条目失败", extra={"entry_id": entry_id, "error": str(e)})
            else:
                # 创建新条目
                try:
                    new_entry = {
                        "产品名称": data.get('产品名称', ''),
                        "文案内容": text,
                        "prompt": data.get('prompt', ''),
                        "image_url": uploaded_image_url,
                        "image_url_tiktok": tiktok_resized_url,
                        "来源": Config.SOURCE_PUBLISHED,
                        "发布次数": 1
                    }
                    logger.info("准备保存内容到知识库", extra={"product_name": product_name, "has_image": bool(uploaded_image_url)})
                    add_entry(new_entry)
                    logger.info("内容已保存到知识库", extra={"product_name": product_name})
                except Exception as e:
                    logger.error("保存内容到知识库失败", extra={"product_name": product_name, "error": str(e), "entry_data": str(new_entry)[:500]})
        
        return jsonify({
            "status": "completed",
            "publish_results": results,
            "success_count": success_count
        })
        
    except Exception as e:
        logger.error("发布失败", extra={"product_name": product_name, "platforms": platforms, "error": str(e)})
        return jsonify({"error": f"发布失败: {str(e)}"}), 500


@api_bp.route('/auto_publish', methods=['POST'])
def auto_publish():
    """
    全自动发布（一键生成+发布）
    
    根据产品名称自动完成：
    1. 获取产品信息
    2. 生成独特文案和图片
    3. 上传图片到GitHub图床
    4. 发布到指定社交平台
    5. 保存到知识库
    
    请求参数（JSON）：
    - product_name (str): 产品名称
    - platforms (list, optional): 目标平台列表，默认['tiktok', 'instagram', 'facebook']
    - immediate (bool, optional): 是否立即发布，默认True
    - schedule_time (str, optional): 定时发布时间（ISO格式）
    
    返回值（JSON）：
    {
        "status": "completed",
        "product_name": 产品名称,
        "generated_content": 生成的文案,
        "generated_image": 生成的图片URL,
        "publish_results": 各平台发布结果列表
    }
    """
    data = request.json
    product_name = data.get('product_name', '')
    platforms = data.get('platforms', ['tiktok', 'instagram', 'facebook'])
    immediate = data.get('immediate', True)
    schedule_time = data.get('schedule_time')
    
    logger.info("全自动发布模式启动", extra={
        "product_name": product_name, 
        "platforms": platforms, 
        "immediate": immediate,
        "schedule_time": schedule_time
    })
    
    try:
        # 获取产品信息
        entry = get_random_entry_by_product(product_name)
        if not entry:
            logger.warning("未找到相关产品", extra={"product_name": product_name})
            return jsonify({"error": "未找到相关产品"}), 404
        
        logger.info("找到相关条目", extra={"entry_id": entry.get('id'), "product_name": entry.get('产品名称')})
        
        # 获取所有已有内容用于去重检测
        all_entries = get_all_entries()
        existing_contents = [e['文案内容'] for e in all_entries]
        existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in all_entries]
        
        # 获取参考图片
        reference_image_url = entry.get('image_url')
        
        # 生成独特文案（直接传递产品信息）
        product_description = f"产品名称: {entry['产品名称']}"
        if '文案内容' in entry and entry['文案内容']:
            product_description += f"\n参考文案: {entry['文案内容'][:100]}..."
        content_result = generate_unique_content(product_description, existing_contents)
        new_content = content_result["content"] if content_result else None
        content_prompt = content_result["prompt"] if content_result else ""
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        # 生成独特图片（使用配置化的提示词生成函数）
        product_description = entry.get('产品名称', '') + ' ' + entry.get('文案内容', '')[:100]
        image_prompt = build_image_prompt(product_description)
        new_image = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        logger.info("图片生成完成", extra={"image_url": new_image})
        
        uploaded_image_url = new_image
        
        logger.debug(f"[调试] new_image: {new_image[:50] if new_image else None}")
        logger.debug(f"[调试] is_github_configured: {is_github_configured(log_enabled=True)}")
        
        # 上传图片到GitHub图床
        if new_image and is_github_configured(log_enabled=False):
            logger.info("发布前上传图片到 GitHub 图床", extra={"image_url": new_image[:50]})
            try:
                if "cdn.jsdelivr.net" not in new_image and "github.com" not in new_image:
                    github_url = upload_image_to_github(new_image, product_name=entry.get('产品名称'))
                    if github_url:
                        cdn_url = convert_github_url_to_cdn(github_url) if convert_github_url_to_cdn else github_url
                        uploaded_image_url = cdn_url
                        logger.info("✅ 图片上传到 GitHub 成功", extra={"cdn_url": uploaded_image_url})
                    else:
                        logger.warning("❌ 上传图片到 GitHub 失败，将使用原URL")
                else:
                    logger.info("图片已在 GitHub CDN，无需重新上传")
            except Exception as e:
                logger.error(f"❌ 上传图片到 GitHub 时发生错误: {e}")
        else:
            if not new_image:
                logger.warning("⚠️  图片为空，跳过上传")
            else:
                logger.warning("⚠️  GitHub 图床未配置或未启用")
        
        # 如果图片为空，过滤掉需要图片的平台
        platforms_to_use = platforms.copy()
        if not uploaded_image_url:
            platforms_requiring_image = ['tiktok', 'instagram']
            platforms_to_use = [p for p in platforms if p not in platforms_requiring_image]
            if platforms_to_use != platforms:
                logger.warning(f"⚠️ 图片为空，跳过需要图片的平台: {[p for p in platforms if p in platforms_requiring_image]}")
        
        # 发布到各个平台
        results = publish_to_platforms(new_content, uploaded_image_url, platforms_to_use, immediate, schedule_time, product_name=entry.get('产品名称'))
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info("发布完成", extra={"success_count": success_count, "total_platforms": len(results)})
        
        # 获取调整后的图片URL（TikTok或Facebook）
        tiktok_resized_url = None
        for r in results:
            if r['status'] == 'success' and r.get('resized_url'):
                tiktok_resized_url = r['resized_url']
                logger.info(f"图片已调整尺寸: {tiktok_resized_url[:50]} (平台: {r.get('platform')})")
                break
        
        # 如果发布成功，保存到知识库
        if success_count > 0:
            new_entry = {
                "产品名称": entry['产品名称'],
                "文案内容": new_content,
                "prompt": image_prompt,
                "image_url": uploaded_image_url,
                "image_url_tiktok": tiktok_resized_url,
                "标签": entry.get('标签', []),
                "来源": Config.SOURCE_PUBLISHED
            }
            add_entry(new_entry)
            logger.info("内容已保存到知识库", extra={"product_name": product_name})
        
        logger.info("全自动发布完成", extra={"product_name": product_name, "success_count": success_count})
        
        return jsonify({
            "status": "completed",
            "product_name": product_name,
            "generated_content": new_content,
            "generated_image": new_image,
            "content_prompt": content_prompt,
            "image_prompt": image_prompt,
            "publish_results": results
        })
        
    except Exception as e:
        logger.error("全自动发布失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"全自动发布失败: {str(e)}"}), 500


@api_bp.route('/generate-content', methods=['POST'])
def generate_content_for_knowledge():
    """
    为知识库生成社交媒体文案
    
    根据产品名称和描述生成适合社交媒体发布的种草文案。
    
    请求参数（JSON）：
    - 产品名称 (str): 产品名称（必填）
    - 产品描述 (str, optional): 产品详细描述
    
    返回值（JSON）：
    {
        "文案内容": 生成的文案,
        "prompt": 图片生成提示词
    }
    """
    data = request.json
    product_name = data.get('产品名称', '')
    product_description = data.get('产品描述', '')
    
    # 参数校验
    if not product_name:
        return jsonify({"error": "请提供产品名称"}), 400
    
    logger.info("开始为知识库生成内容", extra={"product_name": product_name})
    
    try:
        # 构建产品信息
        product_info = f"产品名称: {product_name}"
        if product_description:
            product_info += f"\n产品描述: {product_description}"
        
        # 生成文案（直接传递产品信息，内部使用配置化提示词）
        content_result = generate_content(product_info)
        
        # 获取图片生成提示词（使用配置化的提示词生成函数）
        prompt_result = build_image_prompt(product_info)
        
        result = {
            "文案内容": content_result,
            "prompt": prompt_result
        }
        
        logger.info("知识库内容生成完成", extra={"product_name": product_name})
        return jsonify(result)
        
    except Exception as e:
        logger.error("知识库内容生成失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"内容生成失败: {str(e)}"}), 500


@api_bp.route('/save-to-knowledge', methods=['POST'])
def save_to_knowledge():
    """
    将生成的内容保存到知识库（无需发布）
    
    用于半自动生成模式，生成内容预览后可手动保存到知识库。
    
    请求参数（JSON）：
    - product_name (str): 产品名称
    - content (str): 生成的文案内容
    - image_url (str): 生成的图片URL
    - prompt (str, optional): 图片生成提示词
    - original_entry_id (str, optional): 原始条目ID（如果是从现有条目生成）
    
    返回值（JSON）：
    {
        "success": true,
        "message": "保存成功",
        "entry_id": 新条目ID
    }
    """
    data = request.json
    product_name = data.get('product_name', '')
    content = data.get('content', '')
    image_url = data.get('image_url', '')
    prompt = data.get('prompt', '')
    original_entry_id = data.get('original_entry_id')
    
    logger.info("开始保存内容到知识库", extra={"product_name": product_name})
    
    try:
        # 验证必填字段
        if not product_name:
            return jsonify({"error": "缺少产品名称"}), 400
        if not content:
            return jsonify({"error": "缺少文案内容"}), 400
        
        # 创建新条目
        new_entry = {
            "产品名称": product_name,
            "文案内容": content,
            "prompt": prompt,
            "image_url": image_url,
            "来源": Config.SOURCE_AI,
            "发布次数": 0
        }
        
        # 如果有原始条目ID，添加引用
        if original_entry_id:
            new_entry["original_entry_id"] = original_entry_id
        
        # 添加到知识库
        result = add_entry(new_entry)
        
        # add_entry 成功时返回 entry 对象，失败时抛出异常
        if result and result.get('id'):
            logger.info("内容保存到知识库成功", extra={"product_name": product_name, "entry_id": result.get('id')})
            return jsonify({
                "success": True,
                "message": "保存成功",
                "entry_id": result.get('id')
            })
        else:
            logger.error("保存到知识库失败", extra={"product_name": product_name})
            return jsonify({"error": "保存失败"}), 500
        
    except Exception as e:
        logger.error("保存到知识库失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"保存失败: {str(e)}"}), 500