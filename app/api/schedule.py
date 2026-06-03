from flask import Blueprint, request, jsonify
from app.services.scheduler_service import (
    schedule_publish,
    get_scheduled_jobs,
    update_scheduled_job,
    delete_scheduled_job,
    toggle_scheduled_job,
    auto_publish_random_products
)
from app.services.logger import get_logger
logger = get_logger(__name__)

schedule_bp = Blueprint('schedule', __name__)

@schedule_bp.route('/schedule/jobs', methods=['GET'])
def list_scheduled_jobs():
    """
    获取所有定时任务列表
    
    返回:
    - jobs: 定时任务列表
    """
    jobs = get_scheduled_jobs()
    return jsonify({'jobs': jobs})

@schedule_bp.route('/schedule/jobs', methods=['POST'])
def create_scheduled_job():
    """
    创建定时发布任务
    
    请求参数（JSON）：
    - name (str): 任务名称（可选，默认为'定时发布任务'）
    - schedule_type (str): 调度类型，'interval'或'cron'（默认为'interval'）
    - interval_minutes (int): 间隔分钟数（interval类型必填，默认60）
    - cron_expression (str): Cron表达式（cron类型必填）
    - platforms (list): 发布平台列表，如['tiktok', 'instagram']（默认全部平台）
    - count_per_run (int): 每次执行发布的产品数量（默认1）
    - max_publish_count (int): 发布上限，达到此数量后自动停止任务（可选，默认无上限）
    - enabled (bool): 是否启用（默认True）
    
    返回:
    - job_id: 任务ID
    - name: 任务名称
    - status: 状态
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    schedule_type = data.get('schedule_type', 'interval')
    
    if schedule_type == 'interval':
        interval_minutes = data.get('interval_minutes', 60)
        if not isinstance(interval_minutes, int) or interval_minutes < 1:
            return jsonify({'error': 'interval_minutes必须是大于0的整数'}), 400
    elif schedule_type == 'cron':
        cron_expression = data.get('cron_expression')
        if not cron_expression:
            return jsonify({'error': 'cron类型任务必须提供cron_expression'}), 400
    else:
        return jsonify({'error': 'schedule_type必须是interval或cron'}), 400
    
    config = {
        'name': data.get('name', '定时发布任务'),
        'schedule_type': schedule_type,
        'interval_minutes': data.get('interval_minutes', 60),
        'cron_expression': data.get('cron_expression', ''),
        'platforms': data.get('platforms', ['tiktok', 'instagram', 'facebook']),
        'count_per_run': data.get('count_per_run', 1),
        'max_publish_count': data.get('max_publish_count'),
        'enabled': data.get('enabled', True)
    }
    
    result = schedule_publish(config)
    
    if 'error' in result:
        return jsonify(result), 400
    
    logger.info(f"定时任务已创建: {config['name']}")
    return jsonify(result), 201

@schedule_bp.route('/schedule/jobs/<job_id>', methods=['GET'])
def get_scheduled_job(job_id):
    """
    获取单个定时任务详情
    
    参数:
    - job_id: 任务ID
    
    返回:
    - job: 任务详情
    """
    jobs = get_scheduled_jobs()
    job = next((j for j in jobs if j['job_id'] == job_id), None)
    
    if not job:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify({'job': job})

@schedule_bp.route('/schedule/jobs/<job_id>', methods=['PUT'])
def update_job(job_id):
    """
    更新定时任务
    
    请求参数（JSON）：
    - name (str): 任务名称
    - schedule_type (str): 调度类型
    - interval_minutes (int): 间隔分钟数
    - cron_expression (str): Cron表达式
    - platforms (list): 发布平台列表
    - count_per_run (int): 每次执行发布的产品数量
    - max_publish_count (int): 发布上限（可选）
    - enabled (bool): 是否启用
    
    参数:
    - job_id: 任务ID
    
    返回:
    - job_id: 任务ID
    - name: 任务名称
    - status: 状态
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    config = {
        'name': data.get('name'),
        'schedule_type': data.get('schedule_type'),
        'interval_minutes': data.get('interval_minutes'),
        'cron_expression': data.get('cron_expression'),
        'platforms': data.get('platforms'),
        'count_per_run': data.get('count_per_run'),
        'max_publish_count': data.get('max_publish_count'),
        'enabled': data.get('enabled')
    }
    
    config = {k: v for k, v in config.items() if v is not None}
    
    result = update_scheduled_job(job_id, config)
    
    if 'error' in result:
        return jsonify(result), 400
    
    logger.info(f"定时任务已更新: {job_id}")
    return jsonify(result)

@schedule_bp.route('/schedule/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """
    删除定时任务
    
    参数:
    - job_id: 任务ID
    
    返回:
    - job_id: 任务ID
    - status: 状态
    """
    result = delete_scheduled_job(job_id)
    
    if 'error' in result:
        return jsonify(result), 404
    
    logger.info(f"定时任务已删除: {job_id}")
    return jsonify(result)

@schedule_bp.route('/schedule/jobs/<job_id>/toggle', methods=['POST'])
def toggle_job(job_id):
    """
    启用/禁用定时任务
    
    参数:
    - job_id: 任务ID
    
    返回:
    - job_id: 任务ID
    - enabled: 当前状态
    """
    result = toggle_scheduled_job(job_id)
    
    if 'error' in result:
        return jsonify(result), 404
    
    status = '启用' if result['enabled'] else '禁用'
    logger.info(f"定时任务已{status}: {job_id}")
    return jsonify(result)

@schedule_bp.route('/schedule/run-now', methods=['POST'])
def run_schedule_now():
    """
    立即执行一次定时发布任务（测试用）
    
    请求参数（JSON）：
    - platforms (list): 发布平台列表（可选）
    - count (int): 发布产品数量（可选，默认1）
    
    返回:
    - status: 状态
    - message: 执行结果
    """
    data = request.get_json() or {}
    platforms = data.get('platforms', ['tiktok', 'instagram'])
    count = data.get('count', 1)
    
    logger.info(f"手动触发定时发布，平台: {platforms}, 数量: {count}")
    auto_publish_random_products(platforms, count)
    
    return jsonify({
        'status': 'started',
        'message': f'已开始执行自动发布，将从知识库随机选择{count}个产品发布到{platforms}'
    })