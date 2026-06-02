# -*- coding: utf-8 -*-
"""
GitHub 图床上传服务模块

该模块提供将图片上传到 GitHub 仓库并通过 jsDelivr CDN 访问的功能。

模块功能：
1. 配置检查：验证 GitHub 图床相关配置是否完整
2. 本地图片上传：将本地图片文件上传到 GitHub
3. URL图片上传：从远程URL下载图片并上传到 GitHub
4. 统一上传接口：自动识别来源类型并选择对应的上传方式
5. URL转换：将 GitHub blob 链接转换为 jsDelivr CDN 链接
6. 上传历史记录：记录最近的上传记录

文件命名规则：
- 有产品名时：{产品名}_{时间戳}{扩展名}
- 无产品名时：{时间戳}_{4位随机数}{扩展名}
"""

import requests
import base64
import os
from datetime import datetime
from urllib.parse import unquote

import urllib3
# 禁用SSL警告（用于某些不安全的连接场景）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

# 上传历史记录（最多保存100条）
upload_history = []

# 配置检查缓存（避免重复检查）
_configured_cache = None


def is_configured(log_enabled=True):
    """
    检查 GitHub 图床配置是否完整
    
    验证以下配置项：
    - GITHUB_IMAGE_BED_ENABLED: 是否启用图床
    - GITHUB_TOKEN: GitHub 访问令牌
    - GITHUB_USER: GitHub 用户名
    - GITHUB_REPO: GitHub 仓库名
    
    Args:
        log_enabled (bool, optional): 是否输出日志，默认True
    
    Returns:
        bool: 配置是否完整
    """
    global _configured_cache
    
    # 使用缓存结果
    if _configured_cache is not None:
        return _configured_cache
    
    # 输出配置信息
    if log_enabled:
        logger.info(f"[配置检查] GITHUB_IMAGE_BED_ENABLED: {Config.GITHUB_IMAGE_BED_ENABLED}")
        logger.info(f"[配置检查] GITHUB_TOKEN: {'已配置' if Config.GITHUB_TOKEN else '未配置'}")
        logger.info(f"[配置检查] GITHUB_USER: {Config.GITHUB_USER or '未配置'}")
        logger.info(f"[配置检查] GITHUB_REPO: {Config.GITHUB_REPO or '未配置'}")
        logger.info(f"[配置检查] GITHUB_BRANCH: {Config.GITHUB_BRANCH or '未配置'}")
        logger.info(f"[配置检查] GITHUB_IMAGE_FOLDER: {Config.GITHUB_IMAGE_FOLDER or '未配置'}")
    
    # 检查配置项
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
    """
    获取 GitHub API 请求头
    
    Returns:
        dict: 包含 Authorization 和 Accept 的请求头字典
    """
    return {
        "Authorization": f"token {Config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def upload_local_image_to_github(local_image_path, remote_folder=None, skip_config_check=False, product_name=None):
    """
    上传本地图片文件到 GitHub
    
    将本地图片文件通过 GitHub API 上传到指定仓库，并返回 jsDelivr CDN 链接。
    
    Args:
        local_image_path (str): 本地图片文件路径
        remote_folder (str, optional): 远程文件夹路径，默认使用配置中的 GITHUB_IMAGE_FOLDER
        skip_config_check (bool, optional): 是否跳过配置检查，默认False
        product_name (str, optional): 产品名称，用于生成文件名
    
    Returns:
        str | None: CDN 链接，上传失败返回 None
    """
    # 配置检查
    if not skip_config_check and not is_configured():
        logger.info("GitHub 图床未启用或配置不完整，跳过上传")
        return None

    try:
        global upload_history
        remote_folder = remote_folder or Config.GITHUB_IMAGE_FOLDER

        # 读取图片文件并进行Base64编码
        with open(local_image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(local_image_path)[1]
        
        if product_name:
            # 有产品名时：{产品名}_{时间戳}{扩展名}
            # 清理文件名中的非法字符
            safe_name = product_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            remote_file_name = f"{safe_name}_{timestamp}{file_ext}"
        else:
            # 无产品名时：{时间戳}_{4位随机数}{扩展名}
            remote_file_name = f"{timestamp}_{os.urandom(4).hex()}{file_ext}"
        
        remote_file_path = f"{remote_folder}/{remote_file_name}"

        # 构建 GitHub API 请求
        url = f"https://api.github.com/repos/{Config.GITHUB_USER}/{Config.GITHUB_REPO}/contents/{remote_file_path}"
        headers = get_github_headers()
        data = {
            "message": f"Upload image via Buffer app: {remote_file_name}",
            "content": image_data,
            "branch": Config.GITHUB_BRANCH
        }

        logger.info(f"上传图片到 GitHub: {remote_file_path}")
        
        # 重试配置
        max_retries = 3
        timeout = 120
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
                
                # 上传成功（200 或 201）
                if response.status_code in [200, 201]:
                    # 生成 CDN 链接和 GitHub 链接
                    cdn_link = f"https://cdn.jsdelivr.net/gh/{Config.GITHUB_USER}/{Config.GITHUB_REPO}@{Config.GITHUB_BRANCH}/{remote_file_path}"
                    github_link = f"https://github.com/{Config.GITHUB_USER}/{Config.GITHUB_REPO}/blob/{Config.GITHUB_BRANCH}/{remote_file_path}"
                    
                    # 记录上传历史
                    upload_history.insert(0, {
                        'timestamp': datetime.now().isoformat(),
                        'cdn_url': cdn_link,
                        'github_url': github_link,
                        'filename': remote_file_name,
                        'source': 'local'
                    })
                    
                    # 限制历史记录数量
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


def upload_url_image_to_github(image_url, remote_folder=None, skip_config_check=False, product_name=None):
    """
    从远程URL下载图片并上传到 GitHub
    
    先从指定URL下载图片到临时文件，然后调用本地图片上传函数。
    
    Args:
        image_url (str): 远程图片URL
        remote_folder (str, optional): 远程文件夹路径
        skip_config_check (bool, optional): 是否跳过配置检查，默认False
        product_name (str, optional): 产品名称，用于生成文件名
    
    Returns:
        str | None: CDN 链接，上传失败返回 None
    """
    # 配置检查
    if not skip_config_check and not is_configured():
        logger.info("GitHub 图床未启用或配置不完整，跳过上传")
        return None

    temp_path = None
    try:
        global upload_history
        logger.info(f"下载图片: {image_url}")
        
        # 下载图片（禁用SSL验证以兼容某些服务器）
        response = requests.get(
            image_url, 
            timeout=30, 
            verify=False,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response.raise_for_status()

        # 保存到临时文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_{timestamp}.jpg"
        temp_path = os.path.join(os.path.dirname(__file__), temp_filename)

        with open(temp_path, "wb") as f:
            f.write(response.content)

        logger.info(f"图片已保存到临时文件: {temp_path}")

        # 调用本地上传函数
        result = upload_local_image_to_github(temp_path, remote_folder, product_name=product_name)

        # 记录上传历史
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
            
            # 限制历史记录数量
            if len(upload_history) > 100:
                upload_history = upload_history[:100]

        return result

    except Exception as e:
        logger.error(f"❌ 上传 URL 图片失败: {e}")
        return None
    finally:
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"已清理临时文件: {temp_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")


def upload_image_to_github(image_source, remote_folder=None, product_name=None):
    """
    统一的图片上传接口
    
    根据图片来源类型自动选择上传方式：
    - HTTP/HTTPS URL: 调用 upload_url_image_to_github
    - 本地文件路径: 调用 upload_local_image_to_github
    
    Args:
        image_source (str): 图片来源（URL或本地路径）
        remote_folder (str, optional): 远程文件夹路径
        product_name (str, optional): 产品名称，用于生成文件名
    
    Returns:
        str | None: CDN 链接，上传失败返回 None
    """
    # 配置检查
    if not is_configured():
        return None

    # 判断来源类型
    if image_source.startswith("http://") or image_source.startswith("https://"):
        return upload_url_image_to_github(image_source, remote_folder, skip_config_check=True, product_name=product_name)
    else:
        if os.path.exists(image_source):
            return upload_local_image_to_github(image_source, remote_folder, skip_config_check=True, product_name=product_name)
        else:
            logger.error(f"图片文件不存在: {image_source}")
            return None


def convert_github_url_to_cdn(github_url):
    """
    将 GitHub blob 链接转换为 jsDelivr CDN 链接
    
    GitHub blob链接格式: https://github.com/{user}/{repo}/blob/{branch}/{path}
    jsDelivr CDN链接格式: https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}
    
    Args:
        github_url (str): GitHub blob 链接
    
    Returns:
        str: CDN 链接（如果转换失败，返回原URL）
    """
    if not github_url:
        return github_url

    # 已经是CDN链接，直接返回
    if "cdn.jsdelivr.net" in github_url:
        return github_url

    # 转换 GitHub blob 链接
    if "github.com" in github_url and "/blob/" in github_url:
        try:
            parts = github_url.split("/")
            user_index = parts.index("github.com") + 1
            repo_index = user_index + 1
            branch_index = repo_index + 1
            
            user = parts[user_index]
            repo = parts[repo_index]
            branch = parts[branch_index]
            
            # 解析路径部分（处理URL编码）
            path_parts = parts[branch_index + 1:]
            path = "/".join([unquote(p) for p in path_parts])
            
            # 构建CDN链接
            cdn_url = f"https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}"
            logger.info(f"GitHub 链接已转换为 CDN: {cdn_url}")
            return cdn_url
            
        except (ValueError, IndexError) as e:
            logger.error(f"URL 解析失败: {github_url}, 错误: {str(e)}")
            return github_url
    
    # 无法转换，返回原URL
    return github_url


def get_upload_history(limit=20):
    """
    获取上传历史记录
    
    Args:
        limit (int, optional): 返回数量限制，默认20条
    
    Returns:
        list: 上传历史记录列表
    """
    return upload_history[:limit]


def get_latest_upload():
    """
    获取最近一次上传记录
    
    Returns:
        dict | None: 最近一次上传记录，无记录时返回None
    """
    if upload_history:
        return upload_history[0]
    return None