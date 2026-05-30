# -*- coding: utf-8 -*-
"""
Buffer社交内容发布系统 - Flask主应用（优化版）

该模块提供了完整的RESTful API接口，用于：
1. 图文知识库管理（增删改查）
2. AI内容生成（文案+图片）
3. 多平台发布（TikTok、Instagram、Facebook）
4. 本地图片上传服务

优化特性：
- 使用统一的 config.py 配置
- 新增条目编辑、删除接口
- 新增标签搜索接口
- 参数验证和异常处理优化

依赖模块：
- flask: Web框架
- flask_cors: 跨域支持
- chroma_knowledge_base: 向量知识库操作
- buffer_api: Buffer平台API集成
- ai_api: Doubao AI API集成（原higgsfield_api）
- uuid: 生成唯一文件名
"""

# 导入必要的模块
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from app.chroma_knowledge_base import (
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
from app.buffer_api import publish_to_platforms
from app.doubao_api import generate_content, generate_image, generate_unique_content, generate_unique_image
from app.logger import get_logger
import os
import uuid
import sys
import json

# 添加项目根目录，导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# 初始化日志
logger = get_logger(__name__)

# 初始化Flask应用
app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)

# 使用 config.py 中的配置
UPLOAD_FOLDER = config.UPLOAD_DIR
ALLOWED_EXTENSIONS = config.ALLOWED_IMAGE_EXTENSIONS
MAX_UPLOAD_SIZE = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024

# 确保上传目录存在
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 设置最大上传大小
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE


def allowed_file(filename):
    """
    检查文件名是否为允许的图片格式
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------
# 前端页面路由
# ---------------------------

@app.route('/')
def index():
    """
    首页路由 - 返回前端页面
    """
    return render_template('index.html')


# ---------------------------
# 知识库管理API
# ---------------------------

@app.route('/api/search', methods=['GET'])
def search():
    """
    语义搜索知识库
    """
    keyword = request.args.get('keyword', '')
    limit = int(request.args.get('limit', 10))
    threshold = float(request.args.get('threshold', 0.3))
    
    results = search_knowledge_base(keyword, n_results=limit, threshold=threshold)
    return jsonify({"results": results})


@app.route('/api/search/suggestions', methods=['GET'])
def search_suggestions():
    """
    获取搜索建议
    """
    keyword = request.args.get('keyword', '')
    suggestions = get_search_suggestions(keyword)
    return jsonify({"suggestions": suggestions})


@app.route('/api/search/field', methods=['GET'])
def search_by_field_api():
    """
    按指定字段精确搜索
    """
    field = request.args.get('field', '')
    value = request.args.get('value', '')
    limit = int(request.args.get('limit', 10))
    
    if not field or not value:
        return jsonify({"error": "缺少必填参数: field 和 value"}), 400
    
    results = search_by_field(field, value, n_results=limit)
    return jsonify({"results": results})


@app.route('/api/search/tag', methods=['GET'])
def search_by_tag():
    """
    按标签搜索条目
    """
    tag = request.args.get('tag', '')
    
    if not tag:
        return jsonify({"error": "缺少必填参数: tag"}), 400
    
    results = get_entries_by_tag(tag)
    return jsonify({"results": results})


@app.route('/api/entries', methods=['GET'])
def get_entries():
    """
    获取所有知识库条目
    """
    entries = get_all_entries()
    return jsonify({"entries": entries})


@app.route('/api/entries/<entry_id>', methods=['GET'])
def get_entry(entry_id):
    """
    根据ID获取单个条目
    """
    entry = get_entry_by_id(entry_id)
    if not entry:
        return jsonify({"error": "条目不存在"}), 404
    return jsonify({"entry": entry})


@app.route('/api/entries', methods=['POST'])
def add_new_entry():
    """
    新增知识库条目（支持两种方式）
    """
    # 处理文件上传方式
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "请选择文件"}), 400
        
        # 检查文件格式
        if file and allowed_file(file.filename):
            # 生成唯一文件名
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = f"/uploads/{filename}"
            
            # 构建条目数据
            entry = {
                "产品名称": request.form.get('产品名称', ''),
                "文案内容": request.form.get('文案内容', ''),
                "prompt": request.form.get('prompt', ''),
                "image_url": image_url,
                "来源": config.SOURCE_MANUAL
            }
            
            # 验证必填字段
            required_fields = ['产品名称', '文案内容', 'prompt']
            for field in required_fields:
                if not entry[field]:
                    return jsonify({"error": f"缺少必填字段: {field}"}), 400
            
            # 添加到知识库
            new_entry = add_entry(entry)
            return jsonify({"status": "success", "entry": new_entry})
        else:
            return jsonify({"error": "不支持的文件格式"}), 400
    
    # 处理JSON方式（提供图片URL）
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
            "来源": data.get('来源', config.SOURCE_MANUAL)
        }
        
        new_entry = add_entry(entry)
        return jsonify({"status": "success", "entry": new_entry})


@app.route('/api/entries/<entry_id>', methods=['PUT'])
def update_existing_entry(entry_id):
    """
    更新知识库条目
    """
    data = request.json
    updated_entry = update_entry(entry_id, data)
    
    if not updated_entry:
        return jsonify({"error": "条目不存在或更新失败"}), 404
    
    return jsonify({"status": "success", "entry": updated_entry})


@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_existing_entry(entry_id):
    """
    删除知识库条目
    """
    success = delete_entry(entry_id)
    
    if not success:
        return jsonify({"error": "条目不存在或删除失败"}), 404
    
    return jsonify({"status": "success", "message": "条目已删除"})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    提供上传图片的访问服务
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---------------------------
# 内容生成API
# ---------------------------

@app.route('/api/generate', methods=['POST'])
def generate():
    """
    生成社交媒体内容（文案+图片）
    """
    data = request.json
    product_name = data.get('product_name', '')
    mode = data.get('mode', 'semi_auto')
    entry_id = data.get('entry_id')  # 新增：允许前端传递选中条目的ID
    
    logger.info("开始生成内容", extra={"product_name": product_name, "mode": mode, "entry_id": entry_id})
    
    try:
        # 优先使用前端传入的条目ID，如果没有则随机选择
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
        
        # 获取产品图片作为参考图片
        reference_image_url = entry.get('image_url')
        
        # 构建带约束的 prompt
        content_prompt = f"{config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{entry['产品名称']}'生成社交媒体文案"
        new_content = generate_unique_content(content_prompt, existing_contents)
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        # 使用固定的简洁图片 Prompt（不经过知识库，直接使用用户要求的提示词）
        simple_image_prompt = "给我生成TikTok、淘宝、小红书类似的电商宣传图片，图片上的文字采用英文，不能出现任何中文字符"
        image_prompt = f"{simple_image_prompt}\n\n{config.IMAGE_GENERATION_CONSTRAINTS}"
        # 将产品图片作为参考图片传递给图片生成函数
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


@app.route('/api/regenerate', methods=['POST'])
def regenerate():
    """
    重新生成内容（文案或图片）
    """
    data = request.json
    original_entry = data.get('original_entry')
    regenerate_type = data.get('type', 'both')
    
    if not original_entry:
        return jsonify({"error": "缺少必要参数: original_entry"}), 400
    
    existing_contents = [e['文案内容'] for e in get_all_entries()]
    existing_images_info = [{'image_url': e.get('image_url'), 'prompt': e.get('prompt')} for e in get_all_entries()]
    
    # 获取产品图片作为参考图片
    reference_image_url = original_entry.get('image_url')
    
    result = {}
    
    if regenerate_type == 'content' or regenerate_type == 'both':
        if '产品名称' not in original_entry:
            return jsonify({"error": "original_entry 缺少必要字段: 产品名称"}), 400
        content_prompt = f"{config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{original_entry['产品名称']}'生成社交媒体文案"
        result['generated_content'] = generate_unique_content(content_prompt, existing_contents)
    
    if regenerate_type == 'image' or regenerate_type == 'both':
        # 使用固定的简洁图片 Prompt
        simple_image_prompt = "给我生成TikTok、淘宝、小红书类似的电商宣传图片，图片上的文字采用英文"
        image_prompt = f"{simple_image_prompt}\n\n{config.IMAGE_GENERATION_CONSTRAINTS}"
        # 将产品图片作为参考图片传递给图片生成函数
        result['generated_image'] = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
    
    return jsonify(result)


# ---------------------------
# 发布API
# ---------------------------

@app.route('/api/publish', methods=['POST'])
def publish():
    """
    发布内容到社交平台（半自动模式）
    """
    data = request.json
    text = data.get('text', '')
    image_url = data.get('image_url', '')
    platforms = data.get('platforms', ['tiktok', 'instagram', 'facebook'])
    product_name = data.get('产品名称', '')
    immediate = data.get('immediate', False)
    source = data.get('source', 'new')
    entry_id = data.get('entry_id')
    schedule_time = data.get('schedule_time')  # 定时发布时间
    
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
                from app.chroma_knowledge_base import update_publish_count
                updated_entry = update_publish_count(entry_id)
                if updated_entry:
                    logger.info("知识库内容发布次数已更新", extra={"entry_id": entry_id, "publish_count": updated_entry.get('发布次数')})
                else:
                    logger.warning("更新发布次数失败，条目可能不存在", extra={"entry_id": entry_id})
            else:
                from app.chroma_knowledge_base import add_entry
                new_entry = {
                    "产品名称": data.get('产品名称', ''),
                    "文案内容": text,
                    "prompt": data.get('prompt', ''),
                    "image_url": image_url,
                    "来源": config.SOURCE_PUBLISHED,
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


@app.route('/api/auto_publish', methods=['POST'])
def auto_publish():
    """
    全自动发布模式（一键完成）
    """
    data = request.json
    product_name = data.get('product_name', '')
    platforms = data.get('platforms', ['tiktok', 'instagram', 'facebook'])
    immediate = data.get('immediate', True)  # 全自动模式默认立即发布
    schedule_time = data.get('schedule_time')  # 定时发布时间
    
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
        
        # 获取产品图片作为参考图片
        reference_image_url = entry.get('image_url')
        
        content_prompt = f"{config.CONTENT_GENERATION_SYSTEM_PROMPT}\n\n为产品'{entry['产品名称']}'生成社交媒体文案"
        new_content = generate_unique_content(content_prompt, existing_contents)
        logger.info("文案生成完成", extra={"content_length": len(new_content) if new_content else 0})
        
        # 使用固定的简洁图片 Prompt
        simple_image_prompt = "给我生成TikTok、淘宝、小红书类似的电商宣传图片，图片上的文字采用英文"
        image_prompt = f"{simple_image_prompt}\n\n{config.IMAGE_GENERATION_CONSTRAINTS}"
        # 将产品图片作为参考图片传递给图片生成函数
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
                "来源": config.SOURCE_PUBLISHED
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


@app.route('/api/generate-content', methods=['POST'])
def generate_content_for_knowledge():
    """
    为知识库生成文案内容（文案、Prompt）
    """
    data = request.json
    product_name = data.get('产品名称', '')
    product_description = data.get('产品描述', '')
    
    if not product_name:
        return jsonify({"error": "请提供产品名称"}), 400
    
    logger.info("开始为知识库生成内容", extra={"product_name": product_name})
    
    try:
        from app.doubao_api import generate_content
        
        # 构建产品信息
        product_info = f"产品名称: {product_name}"
        if product_description:
            product_info += f"\n产品描述: {product_description}"
        
        # 生成文案内容
        content_prompt = f"""基于以下产品信息，生成社交媒体种草文案：

{product_info}

要求：
1. 语言生动活泼，适合抖音、小红书、Instagram等社交平台
2. 突出产品特点和使用场景
3. 字数控制在100-300字之间
4. 包含相关标签（#hashtag）
5. 保持积极、友好的语气
6. 如果有产品描述，请充分利用描述信息"""
        content_result = generate_content(content_prompt)
        
        # 使用固定的简洁图片 Prompt（不经过DeepSeek生成，直接使用用户要求的提示词）
        prompt_result = f"给我生成TikTok、淘宝、小红书类似的电商宣传图片，图片上的文字采用英文"
        
        result = {
            "文案内容": content_result,
            "prompt": prompt_result
        }
        
        logger.info("知识库内容生成完成", extra={"product_name": product_name})
        return jsonify(result)
        
    except Exception as e:
        logger.error("知识库内容生成失败", extra={"product_name": product_name, "error": str(e)})
        return jsonify({"error": f"内容生成失败: {str(e)}"}), 500


# ---------------------------
# 产品管理API
# ---------------------------

PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'products.json')

def load_products():
    """加载产品列表"""
    if not os.path.exists(PRODUCTS_FILE):
        # 创建初始空产品列表
        os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)
        initial_products = []
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_products, f, ensure_ascii=False, indent=2)
        return initial_products
    
    with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    # 迁移旧格式（列表→对象）
    if isinstance(products, list) and len(products) > 0 and isinstance(products[0], str):
        new_products = []
        for i, name in enumerate(products):
            new_products.append({
                "id": i + 1,
                "name": name,
                "description": ""
            })
        save_products(new_products)
        return new_products
    
    return products

def save_products(products):
    """保存产品列表"""
    os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

def get_next_id(products):
    """获取下一个产品ID"""
    if not products:
        return 1
    return max(p['id'] for p in products) + 1

@app.route('/api/products', methods=['GET'])
def get_products():
    """获取所有产品"""
    products = load_products()
    return jsonify({"products": products})

@app.route('/api/products', methods=['POST'])
def add_product():
    """添加新产品"""
    data = request.json
    product_name = data.get('product_name', '').strip()
    description = data.get('description', '').strip()
    
    if not product_name:
        return jsonify({"error": "请输入产品名称"}), 400
    
    products = load_products()
    
    if any(p['name'] == product_name for p in products):
        return jsonify({"error": "产品已存在"}), 400
    
    new_product = {
        "id": get_next_id(products),
        "name": product_name,
        "description": description
    }
    
    products.append(new_product)
    save_products(products)
    
    logger.info("产品已添加", extra={"product_name": product_name})
    return jsonify({"status": "success", "product": new_product, "products": products})

@app.route('/api/products/<int:index>', methods=['PUT'])
def update_product(index):
    """修改产品信息"""
    data = request.json
    new_name = data.get('product_name', '').strip()
    new_description = data.get('description', '').strip()
    
    if not new_name:
        return jsonify({"error": "请输入产品名称"}), 400
    
    products = load_products()
    
    if index < 0 or index >= len(products):
        return jsonify({"error": "产品不存在"}), 404
    
    old_name = products[index]['name']
    
    # 检查名称是否与其他产品重复
    if any(p['name'] == new_name and p != products[index] for p in products):
        return jsonify({"error": "产品已存在"}), 400
    
    products[index]['name'] = new_name
    products[index]['description'] = new_description
    save_products(products)
    
    logger.info("产品已修改", extra={"old_name": old_name, "new_name": new_name})
    return jsonify({"status": "success", "old_name": old_name, "new_name": new_name, "products": products})

@app.route('/api/products/<int:index>', methods=['DELETE'])
def delete_product(index):
    """删除产品"""
    products = load_products()
    
    if index < 0 or index >= len(products):
        return jsonify({"error": "产品不存在"}), 404
    
    deleted = products.pop(index)
    save_products(products)
    
    logger.info("产品已删除", extra={"product_name": deleted['name']})
    return jsonify({"status": "success", "deleted": deleted, "products": products})

# ---------------------------
# 系统信息API
# ---------------------------

@app.route('/api/config/info', methods=['GET'])
def get_config_info():
    """
    获取系统配置信息（不含敏感信息）
    """
    products = load_products()
    # 只返回产品名称列表（用于下拉框）
    product_names = [p['name'] for p in products]
    return jsonify({
        "valid_products": product_names,
        "supported_platforms": config.SUPPORTED_PLATFORMS,
        "similarity_threshold": config.SIMILARITY_THRESHOLD,
        "max_retry_attempts": config.MAX_RETRY_ATTEMPTS
    })


# ---------------------------
# 启动应用
# ---------------------------

if __name__ == '__main__':
    # 使用 use_reloader=False 防止缓存失效
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)

