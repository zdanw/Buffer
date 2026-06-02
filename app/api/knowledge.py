# -*- coding: utf-8 -*-
"""
知识库管理API蓝本

该模块提供知识库的增删改查接口，主要功能包括：
1. 搜索：支持关键词搜索、字段搜索、标签搜索
2. 查询：获取所有条目、获取单个条目、获取搜索建议
3. 添加：支持表单上传（带图片）和JSON格式添加
4. 更新：更新已有条目
5. 删除：删除指定条目

API端点列表：
- GET /api/search - 关键词搜索知识库
- GET /api/search/suggestions - 获取搜索建议
- GET /api/search/field - 按字段搜索
- GET /api/search/tag - 按标签搜索
- GET /api/entries - 获取所有条目
- GET /api/entries/<entry_id> - 获取单个条目
- POST /api/entries - 添加新条目
- PUT /api/entries/<entry_id> - 更新条目
- DELETE /api/entries/<entry_id> - 删除条目
"""

from flask import request, jsonify, current_app
import os
import uuid

from app.services.chroma_service import (
    search_knowledge_base,
    get_random_entry_by_product,
    add_entry,
    get_all_entries,
    get_search_suggestions,
    search_by_field,
    update_entry,
    delete_entry,
    get_entry_by_id,
    get_entries_by_tag
)
from app.config import Config
from app.api import api_bp
from app.services.github_service import upload_image_to_github


def allowed_file(filename):
    """
    检查文件是否为允许的图片格式
    
    Args:
        filename (str): 文件名
    
    Returns:
        bool: 是否为允许的图片格式
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS


@api_bp.route('/search', methods=['GET'])
def search():
    """
    关键词搜索知识库
    
    通过关键词在知识库中搜索相关条目，支持相似度阈值过滤。
    
    请求参数（URL参数）：
    - keyword (str): 搜索关键词
    - limit (int, optional): 返回数量限制，默认10
    - threshold (float, optional): 相似度阈值，默认0.3
    
    返回值（JSON）：
    {
        "results": 搜索结果列表
    }
    """
    keyword = request.args.get('keyword', '')
    limit = int(request.args.get('limit', 10))
    threshold = float(request.args.get('threshold', 0.3))
    
    results = search_knowledge_base(keyword, n_results=limit, threshold=threshold)
    return jsonify({"results": results})


@api_bp.route('/search/suggestions', methods=['GET'])
def search_suggestions():
    """
    获取搜索建议
    
    根据关键词获取相关的搜索建议词。
    
    请求参数（URL参数）：
    - keyword (str): 搜索关键词
    
    返回值（JSON）：
    {
        "suggestions": 搜索建议列表
    }
    """
    keyword = request.args.get('keyword', '')
    suggestions = get_search_suggestions(keyword)
    return jsonify({"suggestions": suggestions})


@api_bp.route('/search/field', methods=['GET'])
def search_by_field_api():
    """
    按字段搜索
    
    根据指定字段和值搜索知识库条目。
    
    请求参数（URL参数）：
    - field (str): 字段名称（必填）
    - value (str): 字段值（必填）
    - limit (int, optional): 返回数量限制，默认10
    
    返回值（JSON）：
    {
        "results": 搜索结果列表
    }
    
    错误返回：
    - 400: 缺少必填参数
    """
    field = request.args.get('field', '')
    value = request.args.get('value', '')
    limit = int(request.args.get('limit', 10))
    
    # 参数校验
    if not field or not value:
        return jsonify({"error": "缺少必填参数: field 和 value"}), 400
    
    results = search_by_field(field, value, n_results=limit)
    return jsonify({"results": results})


@api_bp.route('/search/tag', methods=['GET'])
def search_by_tag():
    """
    按标签搜索
    
    根据标签获取相关的知识库条目。
    
    请求参数（URL参数）：
    - tag (str): 标签名称（必填）
    
    返回值（JSON）：
    {
        "results": 搜索结果列表
    }
    
    错误返回：
    - 400: 缺少必填参数
    """
    tag = request.args.get('tag', '')
    
    # 参数校验
    if not tag:
        return jsonify({"error": "缺少必填参数: tag"}), 400
    
    results = get_entries_by_tag(tag)
    return jsonify({"results": results})


@api_bp.route('/entries', methods=['GET'])
def get_entries():
    """
    获取所有条目
    
    返回知识库中的所有条目。
    
    返回值（JSON）：
    {
        "entries": 所有条目列表
    }
    """
    entries = get_all_entries()
    return jsonify({"entries": entries})


@api_bp.route('/entries/<entry_id>', methods=['GET'])
def get_entry(entry_id):
    """
    获取单个条目
    
    根据条目ID获取详细信息。
    
    参数：
    - entry_id (str): 条目ID（URL路径参数）
    
    返回值（JSON）：
    {
        "entry": 条目详细信息
    }
    
    错误返回：
    - 404: 条目不存在
    """
    entry = get_entry_by_id(entry_id)
    if not entry:
        return jsonify({"error": "条目不存在"}), 404
    return jsonify({"entry": entry})


@api_bp.route('/entries', methods=['POST'])
def add_new_entry():
    """
    添加新条目
    
    支持两种添加方式：
    1. 表单上传（multipart/form-data）：包含图片文件和表单字段
    2. JSON格式（application/json）：纯数据添加
    
    表单上传参数：
    - file: 图片文件
    - 产品名称: 产品名称（必填）
    - 文案内容: 文案内容（必填）
    - prompt: 图片生成提示词（必填）
    
    JSON参数：
    - 产品名称 (str): 产品名称（必填）
    - 文案内容 (str): 文案内容（必填）
    - prompt (str): 图片生成提示词（必填）
    - image_url (str): 图片URL（必填）
    - 来源 (str, optional): 来源标识
    
    返回值（JSON）：
    {
        "status": "success",
        "entry": 新添加的条目
    }
    
    错误返回：
    - 400: 缺少必填字段或不支持的文件格式
    """
    # 处理表单上传（带图片）
    if 'file' in request.files:
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            return jsonify({"error": "请选择文件"}), 400
        
        # 检查文件格式
        if file and allowed_file(file.filename):
            # 保存临时文件
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(temp_path)
            
            # 获取产品名称（用于图片命名）
            product_name = request.form.get('产品名称', '').strip()
            
            # 上传到GitHub图床
            image_url = None
            try:
                if upload_image_to_github:
                    github_cdn_url = upload_image_to_github(temp_path, product_name=product_name)
                    if github_cdn_url:
                        image_url = github_cdn_url
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"✅ 图片已上传到 GitHub 图床: {image_url}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ GitHub 图床上传失败: {e}")
            
            # 如果上传失败，使用本地路径
            if not image_url:
                image_url = f"/uploads/{filename}"
            
            # 构建条目数据
            entry = {
                "产品名称": request.form.get('产品名称', ''),
                "文案内容": request.form.get('文案内容', ''),
                "prompt": request.form.get('prompt', ''),
                "image_url": image_url,
                "来源": Config.SOURCE_MANUAL
            }
            
            # 验证必填字段
            required_fields = ['产品名称', '文案内容', 'prompt']
            for field in required_fields:
                if not entry[field]:
                    return jsonify({"error": f"缺少必填字段: {field}"}), 400
            
            # 添加条目
            new_entry = add_entry(entry)
            return jsonify({"status": "success", "entry": new_entry})
        else:
            return jsonify({"error": "不支持的文件格式"}), 400
    
    # 处理JSON格式请求
    else:
        data = request.json
        
        # 验证必填字段
        required_fields = ['产品名称', '文案内容', 'prompt', 'image_url']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"缺少必填字段: {field}"}), 400
        
        # 构建条目数据
        entry = {
            "产品名称": data['产品名称'],
            "文案内容": data['文案内容'],
            "prompt": data['prompt'],
            "image_url": data['image_url'],
            "来源": data.get('来源', Config.SOURCE_MANUAL)
        }
        
        # 添加条目
        new_entry = add_entry(entry)
        return jsonify({"status": "success", "entry": new_entry})


@api_bp.route('/entries/<entry_id>', methods=['PUT'])
def update_existing_entry(entry_id):
    """
    更新已有条目
    
    根据条目ID更新条目内容。
    
    参数：
    - entry_id (str): 条目ID（URL路径参数）
    
    请求参数（JSON）：
    支持更新的字段：产品名称、文案内容、prompt、image_url、标签、来源、发布次数等
    
    返回值（JSON）：
    {
        "status": "success",
        "entry": 更新后的条目
    }
    
    错误返回：
    - 404: 条目不存在或更新失败
    """
    data = request.json
    updated_entry = update_entry(entry_id, data)
    
    if not updated_entry:
        return jsonify({"error": "条目不存在或更新失败"}), 404
    
    return jsonify({"status": "success", "entry": updated_entry})


@api_bp.route('/entries/<entry_id>', methods=['DELETE'])
def delete_existing_entry(entry_id):
    """
    删除条目
    
    根据条目ID删除指定条目。
    
    参数：
    - entry_id (str): 条目ID（URL路径参数）
    
    返回值（JSON）：
    {
        "status": "success",
        "message": "条目已删除"
    }
    
    错误返回：
    - 404: 条目不存在或删除失败
    """
    success = delete_entry(entry_id)
    
    if not success:
        return jsonify({"error": "条目不存在或删除失败"}), 404
    
    return jsonify({"status": "success", "message": "条目已删除"})