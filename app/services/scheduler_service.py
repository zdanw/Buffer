import random
import json
import os
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .chroma_service import get_all_entries
from .buffer_service import publish_to_platforms
from .ai_service import generate_unique_content, generate_unique_image, build_image_prompt
from .github_service import upload_image_to_github, convert_github_url_to_cdn, is_configured as is_github_configured
from .logger import get_logger
logger = get_logger(__name__)
from .chroma_service import add_entry as add_knowledge_entry
from app.config import Config

scheduler = None
scheduled_jobs = {}
SCHEDULE_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'schedule_config.json')

def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        scheduler.start()
        load_scheduled_jobs()
        logger.info("定时任务调度器已启动")

def load_scheduled_jobs():
    if os.path.exists(SCHEDULE_CONFIG_FILE):
        try:
            with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                for config in configs:
                    schedule_publish(config)
                logger.info(f"已加载 {len(configs)} 个定时任务配置")
        except Exception as e:
            logger.error(f"加载定时任务配置失败: {e}")

def save_scheduled_jobs():
    configs = []
    for job_id, job_info in scheduled_jobs.items():
        configs.append({
            'job_id': job_id,
            'name': job_info.get('name', ''),
            'schedule_type': job_info.get('schedule_type', 'interval'),
            'interval_minutes': job_info.get('interval_minutes', 60),
            'cron_expression': job_info.get('cron_expression', ''),
            'platforms': job_info.get('platforms', ['tiktok', 'instagram']),
            'count_per_run': job_info.get('count_per_run', 1),
            'max_publish_count': job_info.get('max_publish_count'),
            'enabled': job_info.get('enabled', True)
        })
    try:
        os.makedirs(os.path.dirname(SCHEDULE_CONFIG_FILE), exist_ok=True)
        with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)
        logger.info("定时任务配置已保存")
    except Exception as e:
        logger.error(f"保存定时任务配置失败: {e}")

def schedule_publish(config):
    if config.get('job_id'):
        job_id = config['job_id']
    else:
        # 生成唯一的任务ID，避免重复
        timestamp = int(time.time())
        job_id = f"publish_job_{timestamp}"
    name = config.get('name', '定时发布任务')
    schedule_type = config.get('schedule_type', 'interval')
    interval_minutes = config.get('interval_minutes', 60)
    cron_expression = config.get('cron_expression', '')
    platforms = config.get('platforms', ['tiktok', 'instagram'])
    count_per_run = config.get('count_per_run', 1)
    max_publish_count = config.get('max_publish_count')
    enabled = config.get('enabled', True)

    if not enabled:
        scheduled_jobs[job_id] = {
            'name': name,
            'schedule_type': schedule_type,
            'interval_minutes': interval_minutes,
            'cron_expression': cron_expression,
            'platforms': platforms,
            'count_per_run': count_per_run,
            'max_publish_count': max_publish_count,
            'enabled': False,
            'job': None
        }
        return {'job_id': job_id, 'status': 'saved but disabled'}

    if schedule_type == 'cron':
        if cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            return {'error': 'cron类型任务需要提供cron_expression'}
    else:
        trigger = IntervalTrigger(minutes=interval_minutes)

    def job_func():
        logger.info(f"定时发布任务开始执行: {name}")
        result = auto_publish_random_products(platforms, count_per_run, max_publish_count)
        
        # 如果达到上限，自动停止任务
        if isinstance(result, dict) and result.get('reached_limit'):
            logger.info(f"任务 {name} 已达到发布上限，自动停止")
            scheduler.pause_job(job_id)

    job = scheduler.add_job(job_func, trigger=trigger, id=job_id, name=name)
    
    scheduled_jobs[job_id] = {
        'name': name,
        'schedule_type': schedule_type,
        'interval_minutes': interval_minutes,
        'cron_expression': cron_expression,
        'platforms': platforms,
        'count_per_run': count_per_run,
        'max_publish_count': max_publish_count,
        'enabled': True,
        'job': job
    }
    
    save_scheduled_jobs()
    logger.info(f"定时发布任务已创建: {name} ({job_id})")
    
    return {'job_id': job_id, 'name': name, 'status': 'scheduled'}

def auto_publish_random_products(platforms, count=1, max_publish_count=None):
    try:
        if max_publish_count is not None:
            total_published = get_total_published_count()
            if total_published >= max_publish_count:
                logger.info(f"已达到发布上限 {total_published}/{max_publish_count}，停止任务")
                return {'reached_limit': True, 'message': f'已达到发布上限 {max_publish_count}'}
        
        entries = get_all_entries()
        if not entries:
            logger.warning("知识库中没有可用的产品")
            return
        
        selected_entries = random.sample(entries, min(count, len(entries)))
        
        for entry in selected_entries:
            product_name = entry.get('产品名称', '未知产品')
            logger.info(f"开始自动发布产品: {product_name}")
            
            try:
                publish_result = publish_entry(entry, platforms)
                if publish_result['success']:
                    logger.info(f"✅ 产品 {product_name} 自动发布成功")
                else:
                    logger.error(f"❌ 产品 {product_name} 自动发布失败: {publish_result.get('error')}")
            except Exception as e:
                logger.error(f"❌ 产品 {product_name} 自动发布异常: {str(e)}")
        
        if max_publish_count is not None:
            total_published = get_total_published_count()
            if total_published >= max_publish_count:
                logger.info(f"发布后达到上限 {total_published}/{max_publish_count}")
                return {'reached_limit': True, 'message': f'发布后达到上限 {max_publish_count}'}
                
    except Exception as e:
        logger.error(f"自动发布任务执行失败: {str(e)}")


def get_total_published_count():
    try:
        all_entries = get_all_entries()
        count = 0
        for entry in all_entries:
            if entry.get('发布次数'):
                count += entry['发布次数']
        return count
    except Exception as e:
        logger.error(f"获取发布计数失败: {e}")
        return 0

def publish_entry(entry, platforms):
    result = {'success': False, 'error': None, 'details': None}
    
    try:
        product_name = entry.get('产品名称', '未知产品')
        
        existing_contents = []
        existing_images_info = []
        
        all_entries = get_all_entries()
        for e in all_entries:
            if e.get('文案内容'):
                existing_contents.append(e['文案内容'])
            if e.get('image_url'):
                existing_images_info.append({'url': e['image_url']})
        
        logger.info(f"获取知识库内容完成，待比较文案数量: {len(existing_contents)}, 待比较图片数量: {len(existing_images_info)}")
        
        # 生成独特文案（直接传递产品信息）
        product_description = f"产品名称: {product_name}"
        new_content = generate_unique_content(product_description, existing_contents)
        
        if not new_content:
            result['error'] = '文案生成失败'
            return result
        
        reference_image_url = entry.get('image_url')
        # 使用配置化的提示词生成函数
        product_description = entry.get('产品名称', '') + ' ' + entry.get('文案内容', '')[:100]
        image_prompt = build_image_prompt(product_description)
        new_image = generate_unique_image(image_prompt, existing_images_info, reference_image_url=reference_image_url)
        
        uploaded_image_url = new_image
        
        if new_image and is_github_configured(log_enabled=False):
            try:
                if "cdn.jsdelivr.net" not in new_image and "github.com" not in new_image:
                    github_url = upload_image_to_github(new_image, product_name=product_name)
                    if github_url:
                        cdn_url = convert_github_url_to_cdn(github_url) if convert_github_url_to_cdn else github_url
                        uploaded_image_url = cdn_url
            except Exception as e:
                logger.warning(f"上传图片到GitHub失败: {e}")
        
        platforms_to_use = platforms.copy()
        if not uploaded_image_url:
            platforms_requiring_image = ['tiktok', 'instagram']
            platforms_to_use = [p for p in platforms if p not in platforms_requiring_image]
        
        publish_results = publish_to_platforms(new_content, uploaded_image_url, platforms_to_use, immediate=True, product_name=product_name)
        success_count = sum(1 for r in publish_results if r['status'] == 'success')
        
        if success_count > 0:
            tiktok_resized_url = None
            for r in publish_results:
                if r['status'] == 'success' and r.get('resized_url'):
                    tiktok_resized_url = r['resized_url']
                    break
            
            new_knowledge_entry = {
                "产品名称": product_name,
                "文案内容": new_content,
                "prompt": image_prompt,
                "image_url": uploaded_image_url,
                "image_url_tiktok": tiktok_resized_url,
                "标签": entry.get('标签', []),
                "来源": Config.SOURCE_PUBLISHED,
                "发布次数": 1
            }
            add_knowledge_entry(new_knowledge_entry)
            
            result['success'] = True
            result['details'] = {
                'product_name': product_name,
                'platforms': platforms_to_use,
                'success_count': success_count,
                'total_count': len(publish_results)
            }
        
    except Exception as e:
        result['error'] = str(e)
    
    return result

def get_scheduled_jobs():
    jobs_info = []
    for job_id, job_info in scheduled_jobs.items():
        job = job_info.get('job')
        next_run_time = None
        if job and job_info.get('enabled'):
            next_run_time = str(job.next_run_time)
        
        jobs_info.append({
            'job_id': job_id,
            'name': job_info.get('name', ''),
            'schedule_type': job_info.get('schedule_type', 'interval'),
            'interval_minutes': job_info.get('interval_minutes', 60),
            'cron_expression': job_info.get('cron_expression', ''),
            'platforms': job_info.get('platforms', []),
            'count_per_run': job_info.get('count_per_run', 1),
            'max_publish_count': job_info.get('max_publish_count'),
            'enabled': job_info.get('enabled', False),
            'next_run_time': next_run_time
        })
    return jobs_info

def update_scheduled_job(job_id, config):
    if job_id not in scheduled_jobs:
        return {'error': '任务不存在'}
    
    old_job = scheduled_jobs[job_id].get('job')
    if old_job:
        scheduler.remove_job(job_id)
    
    config['job_id'] = job_id
    return schedule_publish(config)

def delete_scheduled_job(job_id):
    if job_id not in scheduled_jobs:
        return {'error': '任务不存在'}
    
    job = scheduled_jobs[job_id].get('job')
    if job:
        scheduler.remove_job(job_id)
    
    del scheduled_jobs[job_id]
    save_scheduled_jobs()
    logger.info(f"定时发布任务已删除: {job_id}")
    
    return {'job_id': job_id, 'status': 'deleted'}

def toggle_scheduled_job(job_id):
    if job_id not in scheduled_jobs:
        return {'error': '任务不存在'}
    
    job_info = scheduled_jobs[job_id]
    job_info['enabled'] = not job_info['enabled']
    
    if job_info['enabled']:
        config = {
            'job_id': job_id,
            'name': job_info.get('name'),
            'schedule_type': job_info.get('schedule_type'),
            'interval_minutes': job_info.get('interval_minutes'),
            'cron_expression': job_info.get('cron_expression'),
            'platforms': job_info.get('platforms'),
            'count_per_run': job_info.get('count_per_run'),
            'max_publish_count': job_info.get('max_publish_count'),
            'enabled': True
        }
        schedule_publish(config)
    else:
        job = job_info.get('job')
        if job:
            scheduler.remove_job(job_id)
            job_info['job'] = None
        save_scheduled_jobs()
    
    return {'job_id': job_id, 'enabled': job_info['enabled']}