# -*- coding: utf-8 -*-
"""
内容发布API蓝本

该模块提供内容生成和发布接口。
"""

from flask import request, jsonify

from app.services.buffer_service import publish_to_platforms
from app.services.ai_service import generate_unique_content, generate_unique_image, generate_content
from app.services.chroma_service import get_random_entry_by_product, get_all_entries, add_entry, get_entry_by_id, update_publish_count
from app.services.logger import get_logger
from app.config import Config
from app.api import api_bp

logger = get_logger(__name__)


@api_bp.route('/generate', methods=['POST'])
def generate():
    data = request.json
    product_name = data.get('product_name', '')
    mode = data.get('mode', 'semi_auto')
    entry_id = data.get('entry_id')
    
    logger.info("开始生成内容", extra={"product_name": product_name, "mode": mode, "entry_id": entry_id})
    
    try:
        entry = None
        if entry_id:
            entry = get_entry_by_id(entry_id)
            logger.info(f"使用前端指定的条目: {entry_id}")
        
        if not entry:
            entry = get_random_entry_by_product(product_name)
        
        if not entry:
            logger.warning("未找到相关产品", extra={"product_name": product_name})
            return jsonify({"error": "未找到相关产品"}), 404
        
        logger.info("找到相关条目", extra={"entry_id": entry.get('id'), "product_name": entry.get('产品名称')})
        
        all_entries = get_all_entries()
        existing_contents = [e['文案内容'] for e in all_entries]
        existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in all_entries]
        
        reference_image_url = entry.get('image_url')
        
        content_prompt = f"{Config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{entry['产品名称']}'生成社交媒体文案"
        new_content = generate_unique_content(content_prompt, existing_contents)
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        image_prompt = f"{Config.IMAGE_GENERATION_PROMPT}\n\n{Config.IMAGE_GENERATION_CONSTRAINTS}"
        new_image = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        logger.info("图片生成完成", extra={"image_url": new_image})
        
        result = {
            "original_entry": entry,
            "generated_content": new_content,
            "generated_image": new_image,
            "mode": mode
        }
        
        logger.info("内容生成成功", extra={"product_name": product_name, "mode": mode})
        return jsonify(result)
        
    except Exception as e:
        logger.error("内容生成失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"内容生成失败: {str(e)}"}), 500


@api_bp.route('/regenerate', methods=['POST'])
def regenerate():
    data = request.json
    original_entry = data.get('original_entry')
    regenerate_type = data.get('type', 'both')
    
    if not original_entry:
        return jsonify({"error": "缺少必要参数: original_entry"}), 400
    
    existing_contents = [e['文案内容'] for e in get_all_entries()]
    existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in get_all_entries()]
    
    reference_image_url = original_entry.get('image_url')
    
    result = {}
    
    if regenerate_type == 'content' or regenerate_type == 'both':
        if '产品名称' not in original_entry:
            return jsonify({"error": "original_entry 缺少必要字段: 产品名称"}), 400
        content_prompt = f"{Config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{original_entry['产品名称']}'生成社交媒体文案"
        result['generated_content'] = generate_unique_content(content_prompt, existing_contents)
    
    if regenerate_type == 'image' or regenerate_type == 'both':
        image_prompt = f"{Config.IMAGE_GENERATION_PROMPT}\n\n{Config.IMAGE_GENERATION_CONSTRAINTS}"
        result['generated_image'] = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
    
    return jsonify(result)


@api_bp.route('/publish', methods=['POST'])
def publish():
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
        results = publish_to_platforms(text, image_url, platforms, immediate, schedule_time)
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info("发布完成", extra={"success_count": success_count, "total_platforms": len(platforms)})
        
        if success_count > 0:
            if source == 'knowledge' and entry_id:
                updated_entry = update_publish_count(entry_id)
                if updated_entry:
                    logger.info("知识库内容发布次数已更新", extra={"entry_id": entry_id, "publish_count": updated_entry.get('发布次数')})
                else:
                    logger.warning("更新发布次数失败，条目可能不存在", extra={"entry_id": entry_id})
            else:
                new_entry = {
                    "产品名称": data.get('产品名称', ''),
                    "文案内容": text,
                    "prompt": data.get('prompt', ''),
                    "image_url": image_url,
                    "来源": Config.SOURCE_PUBLISHED,
                    "发布次数": 1
                }
                add_entry(new_entry)
                logger.info("内容已保存到知识库", extra={"product_name": product_name})
        
        return jsonify({
            "status": "completed",
            "results": results,
            "success_count": success_count
        })
        
    except Exception as e:
        logger.error("发布失败", extra={"product_name": product_name, "platforms": platforms, "error": str(e)})
        return jsonify({"error": f"发布失败: {str(e)}"}), 500


@api_bp.route('/auto_publish', methods=['POST'])
def auto_publish():
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
        entry = get_random_entry_by_product(product_name)
        if not entry:
            logger.warning("未找到相关产品", extra={"product_name": product_name})
            return jsonify({"error": "未找到相关产品"}), 404
        
        logger.info("找到相关条目", extra={"entry_id": entry.get('id'), "product_name": entry.get('产品名称')})
        
        all_entries = get_all_entries()
        existing_contents = [e['文案内容'] for e in all_entries]
        existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in all_entries]
        
        reference_image_url = entry.get('image_url')
        
        content_prompt = f"{Config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{entry['产品名称']}'生成社交媒体文案"
        new_content = generate_unique_content(content_prompt, existing_contents)
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        image_prompt = f"{Config.IMAGE_GENERATION_PROMPT}\n\n{Config.IMAGE_GENERATION_CONSTRAINTS}"
        new_image = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        logger.info("图片生成完成", extra={"image_url": new_image})
        
        results = publish_to_platforms(new_content, new_image, platforms, immediate, schedule_time)
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info("发布完成", extra={"success_count": success_count, "total_platforms": len(results)})
        
        if success_count > 0:
            new_entry = {
                "产品名称": entry['产品名称'],
                "文案内容": new_content,
                "prompt": image_prompt,
                "image_url": new_image,
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
            "publish_results": results
        })
        
    except Exception as e:
        logger.error("全自动发布失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"全自动发布失败: {str(e)}"}), 500


@api_bp.route('/generate-content', methods=['POST'])
def generate_content_for_knowledge():
    data = request.json
    product_name = data.get('产品名称', '')
    product_description = data.get('产品描述', '')
    
    if not product_name:
        return jsonify({"error": "请提供产品名称"}), 400
    
    logger.info("开始为知识库生成内容", extra={"product_name": product_name})
    
    try:
        product_info = f"产品名称: {product_name}"
        if product_description:
            product_info += f"\n产品描述: {product_description}"
        
        content_prompt = f"""基于以下产品信息，生成社交媒体种草文案：

{product_info}

要求：
1. 语言生动活泼，适合tiktok、小红书、Instagram等社交平台
2. 突出产品特点和使用场景
3. 字数控制在100-300字之间
4. 包含相关标签（#hashtag）
5. 保持积极、友好的语气
6. 如果有产品描述，请充分利用描述信息"""
        content_result = generate_content(content_prompt)
        
        prompt_result = Config.IMAGE_GENERATION_PROMPT
        
        result = {
            "文案内容": content_result,
            "prompt": prompt_result
        }
        
        logger.info("知识库内容生成完成", extra={"product_name": product_name})
        return jsonify(result)
        
    except Exception as e:
        logger.error("知识库内容生成失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"内容生成失败: {str(e)}"}), 500