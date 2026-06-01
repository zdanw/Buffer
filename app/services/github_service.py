# -*- coding: utf-8 -*-
"""
GitHub 图床上传服务模块

该模块提供将图片上传到 GitHub 仓库并通过 jsDelivr CDN 访问的功能。
"""

import requests
import base64
import os
from datetime import datetime
from urllib.parse import unquote

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

upload_history = []

_configured_cache = None


def is_configured(log_enabled=True):
    global _configured_cache
    
    if _configured_cache is not None:
        return _configured_cache
    
    if log_enabled:
        logger.info(f"[配置检查] GITHUB_IMAGE_BED_ENABLED: {Config.GITHUB_IMAGE_BED_ENABLED}")
        logger.info(f"[配置检查] GITHUB_TOKEN: {'已配置' if Config.GITHUB_TOKEN else '未配置'}")
        logger.info(f"[配置检查] GITHUB_USER: {Config.GITHUB_USER or '未配置'}")
        logger.info(f"[配置检查] GITHUB_REPO: {Config.GITHUB_REPO or '未配置'}")
        logger.info(f"[配置检查] GITHUB_BRANCH: {Config.GITHUB_BRANCH or '未配置'}")
        logger.info(f"[配置检查] GITHUB_IMAGE_FOLDER: {Config.GITHUB_IMAGE_FOLDER or '未配置'}")
    
    if not Config.GITHUB_IMAGE_BED_ENABLED:
        if log_enabled:
            logger.warning("[配置检查] ❌ GITHUB_IMAGE_BED_ENABLED 为 False，未启用 GitHub 图床")
        _configured_cache = False
        return False
    if not all([Config.GITHUB_TOKEN, Config.GITHUB_USER, Config.GITHUB_REPO]):
        if log_enabled:
            logger.warning("[配置检查] ❌ GitHub 图床配置不完整")
        _configured_cache = False
        return False
    
    if log_enabled:
        logger.info("[配置检查] ✅ GitHub 图床配置完整")
    _configured_cache = True
    return True


def get_github_headers():
    return {
        "Authorization": f"token {Config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def upload_local_image_to_github(local_image_path, remote_folder=None, skip_config_check=False):
    if not skip_config_check and not is_configured():
        logger.info("GitHub 图床未启用或配置不完整，跳过上传")
        return None

    try:
        global upload_history
        remote_folder = remote_folder or Config.GITHUB_IMAGE_FOLDER

        with open(local_image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(local_image_path)[1]
        remote_file_name = f"{timestamp}_{os.urandom(4).hex()}{file_ext}"
        remote_file_path = f"{remote_folder}/{remote_file_name}"

        url = f"https://api.github.com/repos/{Config.GITHUB_USER}/{Config.GITHUB_REPO}/contents/{remote_file_path}"
        headers = get_github_headers()
        data = {
            "message": f"Upload image via Buffer app: {remote_file_name}",
            "content": image_data,
            "branch": Config.GITHUB_BRANCH
        }

        logger.info(f"上传图片到 GitHub: {remote_file_path}")
        
        max_retries = 3
        timeout = 120
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
                
                if response.status_code in [200, 201]:
                    cdn_link = f"https://cdn.jsdelivr.net/gh/{Config.GITHUB_USER}/{Config.GITHUB_REPO}@{Config.GITHUB_BRANCH}/{remote_file_path}"
                    github_link = f"https://github.com/{Config.GITHUB_USER}/{Config.GITHUB_REPO}/blob/{Config.GITHUB_BRANCH}/{remote_file_path}"
                    
                    upload_history.insert(0, {
                        'timestamp': datetime.now().isoformat(),
                        'cdn_url': cdn_link,
                        'github_url': github_link,
                        'filename': remote_file_name,
                        'source': 'local'
                    })
                    
                    if len(upload_history) > 100:
                        upload_history = upload_history[:100]
                    
                    logger.info(f"✅ 图片上传成功")
                    logger.info(f"📎 CDN 链接: {cdn_link}")
                    return cdn_link
                else:
                    logger.error(f"❌ GitHub 上传失败: {response.status_code} - {response.text}")
                    return None
                    
            except requests.exceptions.Timeout:
                last_error = "请求超时"
                logger.warning(f"⚠️ 上传超时（第 {attempt + 1}/{max_retries} 次尝试）")
                if attempt < max_retries - 1:
                    continue
                else:
                    logger.error(f"❌ 上传本地图片失败: 请求超时（已重试 {max_retries} 次）")
                    return None
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ 上传失败: {last_error}")
                return None
        
        if last_error:
            logger.error(f"❌ 上传本地图片失败: {last_error}")
            return None
        return None

    except Exception as e:
        logger.error(f"❌ 上传本地图片失败: {str(e)}")
        return None


def upload_url_image_to_github(image_url, remote_folder=None, skip_config_check=False):
    if not skip_config_check and not is_configured():
        logger.info("GitHub 图床未启用或配置不完整，跳过上传")
        return None

    temp_path = None
    try:
        global upload_history
        logger.info(f"下载图片: {image_url}")
        
        response = requests.get(
            image_url, 
            timeout=30, 
            verify=False,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response.raise_for_status()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_{timestamp}.jpg"
        temp_path = os.path.join(os.path.dirname(__file__), temp_filename)

        with open(temp_path, "wb") as f:
            f.write(response.content)

        logger.info(f"图片已保存到临时文件: {temp_path}")

        result = upload_local_image_to_github(temp_path, remote_folder)

        if result:
            github_link = f"https://github.com/{Config.GITHUB_USER}/{Config.GITHUB_REPO}/blob/{Config.GITHUB_BRANCH}/{remote_folder}/{os.path.basename(temp_path)}"
            upload_history.insert(0, {
                'timestamp': datetime.now().isoformat(),
                'cdn_url': result,
                'github_url': github_link,
                'filename': os.path.basename(temp_path),
                'source': 'url',
                'original_url': image_url
            })
            
            if len(upload_history) > 100:
                upload_history = upload_history[:100]

        return result

    except Exception as e:
        logger.error(f"❌ 上传 URL 图片失败: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"已清理临时文件: {temp_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")


def upload_image_to_github(image_source, remote_folder=None):
    if not is_configured():
        return None

    if image_source.startswith("http://") or image_source.startswith("https://"):
        return upload_url_image_to_github(image_source, remote_folder, skip_config_check=True)
    else:
        if os.path.exists(image_source):
            return upload_local_image_to_github(image_source, remote_folder, skip_config_check=True)
        else:
            logger.error(f"图片文件不存在: {image_source}")
            return None


def convert_github_url_to_cdn(github_url):
    if not github_url:
        return github_url

    if "cdn.jsdelivr.net" in github_url:
        return github_url

    if "github.com" in github_url and "/blob/" in github_url:
        try:
            parts = github_url.split("/")
            user_index = parts.index("github.com") + 1
            repo_index = user_index + 1
            branch_index = repo_index + 1
            
            user = parts[user_index]
            repo = parts[repo_index]
            branch = parts[branch_index]
            
            path_parts = parts[branch_index + 1:]
            path = "/".join([unquote(p) for p in path_parts])
            
            cdn_url = f"https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}"
            logger.info(f"GitHub 链接已转换为 CDN: {cdn_url}")
            return cdn_url
            
        except (ValueError, IndexError) as e:
            logger.error(f"URL 解析失败: {github_url}, 错误: {str(e)}")
            return github_url
    
    return github_url


def get_upload_history(limit=20):
    return upload_history[:limit]


def get_latest_upload():
    if upload_history:
        return upload_history[0]
    return None
