# -*- coding: utf-8 -*-
"""
知识库管理API蓝本

该模块提供知识库的增删改查接口。
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
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS


@api_bp.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    limit = int(request.args.get('limit', 10))
    threshold = float(request.args.get('threshold', 0.5))
    
    results = search_knowledge_base(keyword, n_results=limit, threshold=threshold)
    return jsonify({"results": results})


@api_bp.route('/search/suggestions', methods=['GET'])
def search_suggestions():
    keyword = request.args.get('keyword', '')
    suggestions = get_search_suggestions(keyword)
    return jsonify({"suggestions": suggestions})


@api_bp.route('/search/field', methods=['GET'])
def search_by_field_api():
    field = request.args.get('field', '')
    value = request.args.get('value', '')
    limit = int(request.args.get('limit', 10))
    
    if not field or not value:
        return jsonify({"error": "缺少必填参数: field 和 value"}), 400
    
    results = search_by_field(field, value, n_results=limit)
    return jsonify({"results": results})


@api_bp.route('/search/tag', methods=['GET'])
def search_by_tag():
    tag = request.args.get('tag', '')
    
    if not tag:
        return jsonify({"error": "缺少必填参数: tag"}), 400
    
    results = get_entries_by_tag(tag)
    return jsonify({"results": results})


@api_bp.route('/entries', methods=['GET'])
def get_entries():
    entries = get_all_entries()
    return jsonify({"entries": entries})


@api_bp.route('/entries/<entry_id>', methods=['GET'])
def get_entry(entry_id):
    entry = get_entry_by_id(entry_id)
    if not entry:
        return jsonify({"error": "条目不存在"}), 404
    return jsonify({"entry": entry})


@api_bp.route('/entries', methods=['POST'])
def add_new_entry():
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "请选择文件"}), 400
        
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(temp_path)
            
            image_url = None
            try:
                if upload_image_to_github:
                    github_cdn_url = upload_image_to_github(temp_path)
                    if github_cdn_url:
                        image_url = github_cdn_url
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"✅ 图片已上传到 GitHub 图床: {image_url}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ GitHub 图床上传失败: {e}")
            
            if not image_url:
                image_url = f"/uploads/{filename}"
            
            entry = {
                "产品名称": request.form.get('产品名称', ''),
                "文案内容": request.form.get('文案内容', ''),
                "prompt": request.form.get('prompt', ''),
                "image_url": image_url,
                "来源": Config.SOURCE_MANUAL
            }
            
            required_fields = ['产品名称', '文案内容', 'prompt']
            for field in required_fields:
                if not entry[field]:
                    return jsonify({"error": f"缺少必填字段: {field}"}), 400
            
            new_entry = add_entry(entry)
            return jsonify({"status": "success", "entry": new_entry})
        else:
            return jsonify({"error": "不支持的文件格式"}), 400
    
    else:
        data = request.json
        required_fields = ['产品名称', '文案内容', 'prompt', 'image_url']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"缺少必填字段: {field}"}), 400
        
        entry = {
            "产品名称": data['产品名称'],
            "文案内容": data['文案内容'],
            "prompt": data['prompt'],
            "image_url": data['image_url'],
            "来源": data.get('来源', Config.SOURCE_MANUAL)
        }
        
        new_entry = add_entry(entry)
        return jsonify({"status": "success", "entry": new_entry})


@api_bp.route('/entries/<entry_id>', methods=['PUT'])
def update_existing_entry(entry_id):
    data = request.json
    updated_entry = update_entry(entry_id, data)
    
    if not updated_entry:
        return jsonify({"error": "条目不存在或更新失败"}), 404
    
    return jsonify({"status": "success", "entry": updated_entry})


@api_bp.route('/entries/<entry_id>', methods=['DELETE'])
def delete_existing_entry(entry_id):
    success = delete_entry(entry_id)
    
    if not success:
        return jsonify({"error": "条目不存在或删除失败"}), 404
    
    return jsonify({"status": "success", "message": "条目已删除"})