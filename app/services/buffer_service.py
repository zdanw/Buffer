# -*- coding: utf-8 -*-
"""
Buffer平台API服务模块

该模块提供与Buffer GraphQL API的交互功能，支持：
1. 获取已连接的社交平台账号（Channels）
2. 创建和发布社交媒体帖子
3. 多平台批量发布
4. TikTok图片尺寸调整（TikTok限制图片最大2,073,600像素）

模块结构：
- 常量定义：TikTok像素限制、API URL、缓存TTL
- 缓存管理：账户信息和频道列表的缓存机制
- GraphQL请求：封装的GraphQL请求函数
- 数据获取：获取账户信息、获取频道列表
- 帖子创建：创建带媒体的帖子、创建纯文本帖子
- 批量发布：支持多平台同时发布
"""

import requests
import time
from PIL import Image
import io
import os
import uuid
from app.config import Config
from app.services.logger import get_logger
from app.services.github_service import upload_image_to_github, convert_github_url_to_cdn, is_configured as is_github_configured

logger = get_logger(__name__)

# TikTok图片最大像素限制（1080x1080 = 1,166,400）
TIKTOK_MAX_PIXELS = 1166400


def resize_image_for_tiktok(image_url, max_pixels=TIKTOK_MAX_PIXELS, product_name=None):
    """
    调整图片尺寸以满足TikTok上传要求
    
    TikTok对图片有像素限制，超过限制的图片需要缩小。
    该函数会先检查图片尺寸，如果超过限制则按比例缩小并上传到GitHub图床。
    
    Args:
        image_url (str): 原始图片URL
        max_pixels (int, optional): 最大像素数限制，默认2,073,600
        product_name (str, optional): 产品名称，用于GitHub图床文件命名
    
    Returns:
        str: 调整后的图片URL（可能是原图URL或新上传的URL）
    """
    try:
        logger.info(f"检查图片尺寸是否需要调整", extra={"image_url": image_url[:50]})
        
        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # 打开图片并获取尺寸
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        pixels = width * height
        
        logger.debug(f"原始图片尺寸: {width}x{height} = {pixels} 像素")
        
        # 如果尺寸满足要求，直接返回原URL
        if pixels <= max_pixels:
            logger.info(f"图片尺寸满足 TikTok 要求，无需调整")
            return image_url
        
        # 计算缩放比例
        scale = (max_pixels / pixels) ** 0.5
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        logger.info(f"图片尺寸超出限制，正在缩放: {width}x{height} -> {new_width}x{new_height}")
        
        # 使用LANCZOS算法缩小图片（高质量）
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 保存到临时文件
        filename = f"tiktok_{uuid.uuid4()}.jpg"
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        
        # 处理透明通道
        if img_resized.mode in ('RGBA', 'P'):
            img_resized = img_resized.convert('RGB')
        
        # 保存图片
        img_resized.save(file_path, 'JPEG', quality=95)
        
        # 调试日志
        logger.debug(f"调试: is_github_configured={is_github_configured(log_enabled=True)}")
        logger.debug(f"调试: upload_image_to_github={upload_image_to_github is not None}")
        logger.debug(f"调试: product_name={product_name}")
        
        # 上传到GitHub图床
        if is_github_configured(log_enabled=False) and upload_image_to_github:
            logger.info(f"上传调整后的图片到 GitHub 图床")
            github_url = upload_image_to_github(file_path, product_name=product_name)
            if github_url:
                cdn_url = convert_github_url_to_cdn(github_url) if convert_github_url_to_cdn else github_url
                logger.info(f"✅ 调整后的图片已上传到 GitHub: {cdn_url}", extra={"new_size": f"{new_width}x{new_height}"})
                
                # 清理临时文件
                try:
                    os.remove(file_path)
                    logger.debug(f"已清理临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
                
                return cdn_url
            else:
                logger.warning("❌ 上传到 GitHub 失败，使用本地地址")
        
        # 回退到本地地址
        from flask import request
        base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
        result_url = f"{base_url}/uploads/{filename}"
        
        logger.info(f"图片已调整并保存到 uploads: {result_url}", extra={"new_size": f"{new_width}x{new_height}"})
        return result_url
        
    except Exception as e:
        logger.error(f"调整图片尺寸失败: {str(e)}", extra={"image_url": image_url})
        return image_url


# Buffer API 基础URL配置
BUFFER_API_URL = "https://api.buffer.com"
BUFFER_REST_API_URL = "https://api.buffer.com/1"

# 缓存过期时间（10分钟）
CACHE_TTL = 600

# 缓存存储结构
_cache = {
    'account_info': None,
    'account_info_time': 0,
    'channels': {},
    'channels_time': {}
}


def get_cached_account_info():
    """
    获取缓存的账户信息
    
    如果缓存有效（未过期），直接返回缓存数据；否则重新获取并更新缓存。
    
    Returns:
        dict | None: 账户信息字典，包含id、email、name、organizations等字段
    """
    now = time.time()
    
    # 检查缓存是否有效
    if _cache['account_info'] and (now - _cache['account_info_time']) < CACHE_TTL:
        logger.info(f"✅ 使用缓存的账户信息")
        return _cache['account_info']
    
    # 缓存无效，重新获取
    logger.info(f"🔄 缓存无效，重新获取账户信息")
    account_info = _fetch_account_info()
    
    # 更新缓存
    if account_info:
        _cache['account_info'] = account_info
        _cache['account_info_time'] = now
        logger.info(f"📥 账户信息已缓存")
    
    return account_info


def get_cached_channels(organization_id):
    """
    获取缓存的频道列表
    
    如果缓存有效（未过期），直接返回缓存数据；否则重新获取并更新缓存。
    
    Args:
        organization_id (str): 组织ID
    
    Returns:
        list: 频道列表，每个频道包含id、name、service、avatar、status等字段
    """
    now = time.time()
    
    # 检查缓存是否有效
    if organization_id in _cache['channels']:
        if (now - _cache['channels_time'].get(organization_id, 0)) < CACHE_TTL:
            logger.info(f"✅ 使用缓存的频道列表 (组织: {organization_id})")
            return _cache['channels'][organization_id]
    
    # 缓存无效，重新获取
    logger.info(f"🔄 缓存无效，重新获取频道列表 (组织: {organization_id})")
    channels = _fetch_channels(organization_id)
    
    # 更新缓存
    if channels:
        _cache['channels'][organization_id] = channels
        _cache['channels_time'][organization_id] = now
        logger.info(f"📥 频道列表已缓存 (组织: {organization_id}, 频道数: {len(channels)})")
    
    return channels


def clear_cache():
    """
    清除所有缓存
    
    包括账户信息和所有组织的频道列表缓存。
    """
    _cache['account_info'] = None
    _cache['account_info_time'] = 0
    _cache['channels'] = {}
    _cache['channels_time'] = {}
    logger.info("Buffer API 缓存已清除")


def graphql_request(query, max_retries=3, initial_delay=1.0):
    """
    发送GraphQL请求到Buffer API
    
    支持自动重试机制，处理超时和连接错误。
    
    Args:
        query (str): GraphQL查询字符串
        max_retries (int, optional): 最大重试次数，默认3次
        initial_delay (float, optional): 初始重试延迟（秒），默认1秒
    
    Returns:
        dict | None: GraphQL响应数据，失败返回None
    """
    headers = {
        "Authorization": f"Bearer {Config.BUFFER_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    data = {"query": query}
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = requests.post(BUFFER_API_URL, headers=headers, json=data, timeout=30)
            result = response.json()
            
            # 处理GraphQL错误
            if "errors" in result:
                error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
                logger.error(f"GraphQL Error: {', '.join(error_messages)}")
                return None
                
            return result.get("data")
        except requests.exceptions.ReadTimeout:
            # 超时处理
            logger.warning(f"GraphQL请求超时，第 {attempt + 1}/{max_retries} 次尝试")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2  # 指数退避
            else:
                logger.error(f"GraphQL请求超时，已达最大重试次数 {max_retries}")
        except requests.exceptions.ConnectionError:
            # 连接错误处理
            logger.warning(f"GraphQL请求连接失败，第 {attempt + 1}/{max_retries} 次尝试")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2  # 指数退避
            else:
                logger.error(f"GraphQL请求连接失败，已达最大重试次数 {max_retries}")
        except Exception as e:
            logger.error(f"GraphQL Request Error: {e}")
            return None
    
    return None


def _fetch_account_info():
    """
    获取账户信息（内部函数）
    
    使用GraphQL查询获取当前账户的基本信息，包括ID、邮箱、名称和所属组织。
    
    Returns:
        dict | None: 账户信息，包含id、email、name、organizations字段
    """
    query = """
    query {
        account {
            id
            email
            name
            organizations {
                id
                name
            }
        }
    }
    """
    
    data = graphql_request(query)
    if not data:
        return None
    
    return data.get("account")


def _fetch_channels(organization_id):
    """
    获取指定组织的频道列表（内部函数）
    
    使用GraphQL查询获取指定组织下所有连接的社交平台频道。
    
    Args:
        organization_id (str): 组织ID
    
    Returns:
        list: 频道列表，每个频道包含id、name、service、avatar、status等字段
    """
    query = f"""
    query {{
        channels(input: {{ organizationId: "{organization_id}" }}) {{
            id
            name
            service
            avatar
            isQueuePaused
        }}
    }}
    """
    
    data = graphql_request(query)
    if not data:
        return []
    
    channels = []
    for channel in data.get("channels", []):
        channels.append({
            "id": channel.get("id"),
            "name": channel.get("name"),
            "service": channel.get("service"),
            "avatar": channel.get("avatar"),
            "isQueuePaused": channel.get("isQueuePaused"),
            "status": "connected" if not channel.get("isQueuePaused") else "paused"
        })
    
    return channels


def escape_graphql_string(text):
    """
    转义GraphQL字符串中的特殊字符
    
    确保字符串可以安全地嵌入到GraphQL查询中。
    
    Args:
        text (str): 原始字符串
    
    Returns:
        str: 转义后的字符串
    """
    if not text:
        return text
    
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    
    return text


def create_post_with_media(channel_id, text, media_url, platform_type=None, immediate=False, schedule_time=None):
    """
    创建带媒体的帖子
    
    通过Buffer API创建包含图片的社交媒体帖子，支持立即发布或定时发布。
    
    Args:
        channel_id (str): 目标频道ID
        text (str): 帖子文案内容
        media_url (str): 媒体（图片）URL
        platform_type (str, optional): 平台类型（如"instagram"），用于特殊配置
        immediate (bool, optional): 是否立即发布，默认False（定时发布）
        schedule_time (str, optional): 定时发布时间（ISO格式）
    
    Returns:
        dict | None: 发布结果，包含status、post等字段
    """
    text = escape_graphql_string(text)
    
    # 平台特殊配置
    metadata = ""
    if platform_type == "instagram":
        metadata = """
            metadata: {
                instagram: {
                    type: post,
                    shouldShareToFeed: true
                }
            }
        """
    elif platform_type == "facebook":
        metadata = """
            metadata: {
                facebook: {
                    type: post
                }
            }
        """
    
    # 确定发布模式
    if immediate:
        mode = "shareNow"
        due_at_str = ""
        scheduling_type = "automatic"
    else:
        mode = "customScheduled"
        scheduling_type = "automatic"
        
        # 处理定时时间
        if schedule_time:
            from datetime import datetime, timezone
            try:
                scheduled_dt = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
                due_at = scheduled_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception as e:
                logger.warning(f"无法解析定时时间，使用默认时间: {e}")
                from datetime import timedelta
                due_at = (datetime.now(timezone.utc) + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            from datetime import datetime, timezone, timedelta
            due_at = (datetime.now(timezone.utc) + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        due_at_str = f', dueAt: "{due_at}"'
    
    # 构建GraphQL查询
    query = f"""
    mutation {{
        createPost(input: {{
            channelId: "{channel_id}",
            text: "{text}",
            schedulingType: {scheduling_type},
            mode: {mode},
            assets: [{{ image: {{ url: "{media_url}" }} }}]{metadata}{due_at_str}
        }}) {{
            ... on PostActionSuccess {{
                post {{
                    id
                    text
                    dueAt
                }}
            }}
            ... on MutationError {{
                message
            }}
        }}
    }}
    """
    
    data = graphql_request(query)
    
    if not data:
        return None
    
    create_post_result = data.get("createPost")
    
    if not create_post_result:
        return {"status": "failed", "message": "发布失败"}
    
    # 解析结果
    if "post" in create_post_result:
        post = create_post_result["post"]
        logger.info(f"发布成功: {post}")
        return {
            "status": "success",
            "post": {
                "id": post.get("id"),
                "text": post.get("text"),
                "dueAt": post.get("dueAt", "立即")
            }
        }
    elif "message" in create_post_result:
        logger.error(f"发布失败: {create_post_result['message']}")
        return {"status": "failed", "message": create_post_result["message"]}
    
    return {"status": "failed", "message": "未知错误"}


def create_post(channel_id, text, media_url=None, platform_type=None, immediate=False, schedule_time=None):
    """
    创建帖子（统一入口）
    
    根据是否包含媒体URL，选择调用带媒体或纯文本的帖子创建函数。
    
    Args:
        channel_id (str): 目标频道ID
        text (str): 帖子文案内容
        media_url (str, optional): 媒体（图片）URL
        platform_type (str, optional): 平台类型（如"instagram"）
        immediate (bool, optional): 是否立即发布，默认False
        schedule_time (str, optional): 定时发布时间（ISO格式）
    
    Returns:
        dict | None: 发布结果
    """
    # 如果有媒体URL，调用带媒体的发布函数
    if media_url:
        return create_post_with_media(channel_id, text, media_url, platform_type, immediate, schedule_time)
    
    # 纯文本帖子
    text = escape_graphql_string(text)
    
    # 确定发布模式
    if immediate:
        mode = "shareNow"
        scheduling_type = "automatic"
    else:
        mode = "customScheduled"
        scheduling_type = "automatic"
    
    # 构建查询参数
    query_parts = [
        f'channelId: "{channel_id}"',
        f'text: "{text}"',
        f'schedulingType: {scheduling_type}',
        f'mode: {mode}'
    ]
    
    # 添加平台特定的metadata配置
    if platform_type == "facebook":
        query_parts.append("""metadata: { facebook: { type: post } }""")
    
    # 添加定时时间（非立即发布）
    if not immediate:
        if schedule_time:
            from datetime import datetime, timezone
            try:
                scheduled_dt = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
                due_at = scheduled_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception as e:
                logger.warning(f"无法解析定时时间，使用默认时间: {e}")
                from datetime import timedelta
                due_at = (datetime.now(timezone.utc) + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            from datetime import datetime, timezone, timedelta
            due_at = (datetime.now(timezone.utc) + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        query_parts.append(f'dueAt: "{due_at}"')
    
    # 构建GraphQL查询
    query = f"""
    mutation {{
        createPost(input: {{ {', '.join(query_parts)} }}) {{
            ... on PostActionSuccess {{
                post {{
                    id
                    text
                    dueAt
                }}
            }}
            ... on MutationError {{
                message
            }}
        }}
    }}
    """
    
    data = graphql_request(query)
    
    if not data:
        return None
    
    result = data.get("createPost", {})
    
    # 解析结果
    if "post" in result:
        return {
            "status": "success",
            "post": {
                "id": result["post"].get("id"),
                "text": result["post"].get("text"),
                "scheduledAt": result["post"].get("dueAt")
            }
        }
    elif "message" in result:
        return {
            "status": "failed",
            "message": result["message"]
        }
    
    return None


def publish_to_platforms(text, media_url=None, platforms=None, immediate=False, schedule_time=None, product_name=None, tiktok_image_url=None):
    """
    批量发布到多个社交平台
    
    支持同时发布到多个平台，自动匹配可用频道，并处理TikTok图片尺寸调整。
    
    Args:
        text (str): 帖子文案内容
        media_url (str, optional): 媒体（图片）URL
        platforms (list, optional): 目标平台列表，默认["tiktok", "instagram", "facebook"]
        immediate (bool, optional): 是否立即发布，默认False
        schedule_time (str, optional): 定时发布时间（ISO格式）
        product_name (str, optional): 产品名称，用于TikTok图片命名
        tiktok_image_url (str, optional): 预调整的TikTok图片URL
    
    Returns:
        list: 各平台发布结果列表
    """
    if platforms is None:
        platforms = ["tiktok", "instagram", "facebook"]
    
    logger.info("开始发布到社交平台", extra={
        "platforms": platforms, 
        "text_length": len(text),
        "immediate": immediate,
        "schedule_time": schedule_time,
        "product_name": product_name,
        "has_tiktok_url": tiktok_image_url is not None
    })
    
    # 获取账户信息
    account = get_cached_account_info()
    if not account:
        logger.error("无法获取账户信息")
        return [{"error": "Failed to get account info"}]
    
    # 获取组织列表
    orgs = account.get("organizations", [])
    if not orgs:
        logger.error("未找到组织")
        return [{"error": "No organizations found"}]
    
    # 使用第一个组织
    org_id = orgs[0]["id"]
    channels = get_cached_channels(org_id)
    logger.info(f"获取到 {len(channels)} 个频道", extra={"channels": [c['service'] for c in channels]})
    
    results = []
    
    # 平台到服务名称的映射（支持多种服务名称变体）
    platform_mapping = {
        "tiktok": ["tiktok", "tiktok-business", "tiktok-account", "tiktok-pro"],
        "instagram": ["instagram", "instagram-business", "instagram-personal", "instagram-professional", "instagram-creator"],
        "facebook": ["facebook", "facebook-page", "facebook-group", "facebook-profile", "facebook-business"],
        "twitter": ["twitter", "twitter-x", "x", "twitter-business", "x-business"],
        "linkedin": ["linkedin", "linkedin-company", "linkedin-personal", "linkedin-professional"],
        "pinterest": ["pinterest", "pinterest-business", "pinterest-pro"],
        "youtube": ["youtube", "youtube-channel", "youtube-business"],
        "threads": ["threads", "threads-business"],
        "mastodon": ["mastodon"]
    }
    
    # 遍历每个目标平台
    for platform in platforms:
        matched = False
        
        # 查找匹配的频道
        for channel in channels:
            service = channel.get("service", "").lower()
            
            if service in platform_mapping.get(platform, []):
                matched = True
                logger.debug(f"平台 {platform} 匹配到频道: {channel['name']} ({service})")
                
                # 检查频道状态
                if channel.get("status") != "connected":
                    logger.warning(f"频道 {channel['name']} 未连接")
                    results.append({
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "failed",
                        "error": "Channel not connected"
                    })
                    continue
                
                # 处理图片URL（TikTok使用预调整的URL或自动调整尺寸）
                media_url_to_use = media_url
                was_resized = False
                if platform == "tiktok" and media_url:
                    if tiktok_image_url:
                        # 使用预调整的URL
                        logger.info(f"使用预调整的TikTok图片URL")
                        media_url_to_use = tiktok_image_url
                        was_resized = True
                    else:
                        # 自动调整尺寸
                        media_url_to_use = resize_image_for_tiktok(media_url, product_name=product_name)
                        was_resized = (media_url_to_use != media_url)
                
                # 创建帖子
                logger.debug(f"发布到频道: {channel['name']}")
                result = create_post(channel["id"], text, media_url_to_use, platform, immediate, schedule_time)
                
                # 处理结果
                if result and result.get("status") == "success":
                    logger.info(f"发布成功: {platform} -> {channel['name']}", extra={"post_id": result["post"].get("id")})
                    result_item = {
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "success",
                        "post_id": result["post"].get("id"),
                        "scheduled_at": result["post"].get("scheduledAt")
                    }
                    if was_resized:
                        result_item["resized_url"] = media_url_to_use
                    results.append(result_item)
                else:
                    error_msg = result.get("message", "Failed to create post") if result else "Unknown error"
                    logger.error(f"发布失败: {platform} -> {channel['name']}", extra={"error": error_msg})
                    results.append({
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "failed",
                        "error": error_msg
                    })
        
        # 未找到匹配频道
        if not matched:
            logger.warning(f"未找到平台 {platform} 的匹配频道", extra={"available_services": [c['service'] for c in channels]})
            results.append({
                "platform": platform,
                "channel": None,
                "status": "failed",
                "error": f"No matching channel found for platform '{platform}'"
            })
    
    return results


def get_posts(organization_id, limit=10, status_filter=None):
    """
    获取组织的帖子列表
    
    使用GraphQL查询获取指定组织下的帖子，支持状态过滤。
    
    Args:
        organization_id (str): 组织ID
        limit (int, optional): 返回数量限制，默认10
        status_filter (list, optional): 状态过滤列表（如["scheduled", "published"]）
    
    Returns:
        list: 帖子列表，每个帖子包含id、text、dueAt、channelId等字段
    """
    # 构建过滤条件
    filter_part = ""
    if status_filter:
        status_items = ", ".join([f'"{s}"' for s in status_filter])
        filter_part = f'filter: {{ status: [{status_items}] }}'
    
    # 构建GraphQL查询
    query = f"""
    query {{
        posts(
            first: {limit},
            input: {{
                organizationId: "{organization_id}",
                {filter_part}
            }}
        ) {{
            edges {{
                node {{
                    id
                    text
                    dueAt
                    channelId
                }}
            }}
            pageInfo {{
                hasNextPage
                endCursor
            }}
        }}
    }}
    """
    
    data = graphql_request(query)
    
    if not data:
        return []
    
    # 解析结果
    posts = []
    for edge in data.get("posts", {}).get("edges", []):
        node = edge.get("node", {})
        posts.append({
            "id": node.get("id"),
            "text": node.get("text"),
            "dueAt": node.get("dueAt"),
            "channelId": node.get("channelId")
        })
    
    return posts