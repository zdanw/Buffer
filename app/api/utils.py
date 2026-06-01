# -*- coding: utf-8 -*-
"""
辅助工具API蓝本

该模块提供系统配置信息、GitHub图床工具等辅助接口。
"""

from flask import request, jsonify

from app.services.github_service import get_upload_history, get_latest_upload, convert_github_url_to_cdn
from app.services.chroma_service import get_all_entries, update_entry
from app.api.products import load_products
from app.config import Config
from app.api import api_bp


@api_bp.route('/config/info', methods=['GET'])
def get_config_info():
    products = load_products()
    product_names = [p['name'] for p in products]
    return jsonify({
        "valid_products": product_names,
        "supported_platforms": Config.SUPPORTED_PLATFORMS,
        "similarity_threshold": Config.SIMILARITY_THRESHOLD,
        "max_retry_attempts": Config.MAX_RETRY_ATTEMPTS
    })


@api_bp.route('/github/upload-history', methods=['GET'])
def get_upload_history_api():
    try:
        limit = int(request.args.get('limit', 20))
        history = get_upload_history(limit=limit)
        
        return jsonify({
            "status": "success",
            "count": len(history),
            "history": history
        })
        
    except Exception as e:
        return jsonify({"error": f"获取失败: {str(e)}"}), 500


@api_bp.route('/github/latest-upload', methods=['GET'])
def get_latest_upload_api():
    try:
        latest = get_latest_upload()
        
        if latest:
            return jsonify({
                "status": "success",
                "upload": latest
            })
        else:
            return jsonify({
                "status": "success",
                "upload": None,
                "message": "暂无上传记录"
            })
        
    except Exception as e:
        return jsonify({"error": f"获取失败: {str(e)}"}), 500


@api_bp.route('/utils/convert-github-url', methods=['POST'])
def convert_github_url():
    try:
        data = request.json
        github_url = data.get('url', '')
        
        if not github_url:
            return jsonify({"error": "请提供 GitHub URL"}), 400
        
        cdn_url = convert_github_url_to_cdn(github_url)
        
        return jsonify({
            "original_url": github_url,
            "cdn_url": cdn_url,
            "converted": github_url != cdn_url
        })
        
    except Exception as e:
        return jsonify({"error": f"转换失败: {str(e)}"}), 500


@api_bp.route('/utils/batch-convert-urls', methods=['POST'])
def batch_convert_urls():
    try:
        all_entries = get_all_entries()
        converted_count = 0
        
        for entry in all_entries:
            image_url = entry.get('image_url', '')
            
            if 'github.com' in image_url and '/blob/' in image_url:
                new_url = convert_github_url_to_cdn(image_url)
                
                if new_url != image_url:
                    update_entry(entry['id'], {'image_url': new_url})
                    converted_count += 1
        
        return jsonify({
            "status": "success",
            "total_entries": len(all_entries),
            "converted_count": converted_count
        })
        
    except Exception as e:
        return jsonify({"error": f"批量转换失败: {str(e)}"}), 500