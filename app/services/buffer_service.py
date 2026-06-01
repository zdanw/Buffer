# -*- coding: utf-8 -*-
"""
Buffer平台API服务模块

该模块提供与Buffer GraphQL API的交互功能，支持：
1. 获取已连接的社交平台账号（Channels）
2. 创建和发布社交媒体帖子
3. 多平台批量发布
"""

import requests
import time
from PIL import Image
import io
import os
from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

TIKTOK_MAX_PIXELS = 2073600


def resize_image_for_tiktok(image_url, max_pixels=TIKTOK_MAX_PIXELS):
    try:
        logger.info(f"检查图片尺寸是否需要调整", extra={"image_url": image_url[:50]})
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        pixels = width * height
        
        logger.debug(f"原始图片尺寸: {width}x{height} = {pixels} 像素")
        
        if pixels <= max_pixels:
            logger.info(f"图片尺寸满足 TikTok 要求，无需调整")
            return image_url
        
        scale = (max_pixels / pixels) ** 0.5
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        logger.info(f"图片尺寸超出限制，正在缩放: {width}x{height} -> {new_width}x{new_height}")
        
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        import uuid
        filename = f"tiktok_{uuid.uuid4()}.jpg"
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        
        if img_resized.mode in ('RGBA', 'P'):
            img_resized = img_resized.convert('RGB')
        
        img_resized.save(file_path, 'JPEG', quality=95)
        
        local_url = f"/uploads/{filename}"
        
        logger.info(f"图片已调整并保存到 uploads: {local_url}", extra={"new_size": f"{new_width}x{new_height}"})
        return local_url
        
    except Exception as e:
        logger.error(f"调整图片尺寸失败: {str(e)}", extra={"image_url": image_url})
        return image_url


BUFFER_API_URL = "https://api.buffer.com"
BUFFER_REST_API_URL = "https://api.buffer.com/1"

CACHE_TTL = 600

_cache = {
    'account_info': None,
    'account_info_time': 0,
    'channels': {},
    'channels_time': {}
}


def get_cached_account_info():
    now = time.time()
    
    if _cache['account_info'] and (now - _cache['account_info_time']) < CACHE_TTL:
        logger.info(f"✅ 使用缓存的账户信息")
        return _cache['account_info']
    
    logger.info(f"🔄 缓存无效，重新获取账户信息")
    account_info = _fetch_account_info()
    
    if account_info:
        _cache['account_info'] = account_info
        _cache['account_info_time'] = now
        logger.info(f"📥 账户信息已缓存")
    
    return account_info


def get_cached_channels(organization_id):
    now = time.time()
    
    if organization_id in _cache['channels']:
        if (now - _cache['channels_time'].get(organization_id, 0)) < CACHE_TTL:
            logger.info(f"✅ 使用缓存的频道列表 (组织: {organization_id})")
            return _cache['channels'][organization_id]
    
    logger.info(f"🔄 缓存无效，重新获取频道列表 (组织: {organization_id})")
    channels = _fetch_channels(organization_id)
    
    if channels:
        _cache['channels'][organization_id] = channels
        _cache['channels_time'][organization_id] = now
        logger.info(f"📥 频道列表已缓存 (组织: {organization_id}, 频道数: {len(channels)})")
    
    return channels


def clear_cache():
    _cache['account_info'] = None
    _cache['account_info_time'] = 0
    _cache['channels'] = {}
    _cache['channels_time'] = {}
    logger.info("Buffer API 缓存已清除")


def graphql_request(query, max_retries=3, initial_delay=1.0):
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
            
            if "errors" in result:
                error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
                logger.error(f"GraphQL Error: {', '.join(error_messages)}")
                return None
                
            return result.get("data")
        except requests.exceptions.ReadTimeout:
            logger.warning(f"GraphQL请求超时，第 {attempt + 1}/{max_retries} 次尝试")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"GraphQL请求超时，已达最大重试次数 {max_retries}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"GraphQL请求连接失败，第 {attempt + 1}/{max_retries} 次尝试")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"GraphQL请求连接失败，已达最大重试次数 {max_retries}")
        except Exception as e:
            logger.error(f"GraphQL Request Error: {e}")
            return None
    
    return None


def _fetch_account_info():
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
    if not text:
        return text
    
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    
    return text


def create_post_with_media(channel_id, text, media_url, platform_type=None, immediate=False, schedule_time=None):
    text = escape_graphql_string(text)
    
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
    
    if immediate:
        mode = "shareNow"
        due_at_str = ""
        scheduling_type = "automatic"
    else:
        mode = "customScheduled"
        scheduling_type = "automatic"
        
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
    if media_url:
        return create_post_with_media(channel_id, text, media_url, platform_type, immediate, schedule_time)
    
    text = escape_graphql_string(text)
    
    if immediate:
        mode = "shareNow"
        scheduling_type = "automatic"
    else:
        mode = "customScheduled"
        scheduling_type = "automatic"
    
    query_parts = [
        f'channelId: "{channel_id}"',
        f'text: "{text}"',
        f'schedulingType: {scheduling_type}',
        f'mode: {mode}'
    ]
    
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


def publish_to_platforms(text, media_url=None, platforms=None, immediate=False, schedule_time=None):
    if platforms is None:
        platforms = ["tiktok", "instagram", "facebook"]
    
    logger.info("开始发布到社交平台", extra={
        "platforms": platforms, 
        "text_length": len(text),
        "immediate": immediate,
        "schedule_time": schedule_time
    })
    
    account = get_cached_account_info()
    if not account:
        logger.error("无法获取账户信息")
        return [{"error": "Failed to get account info"}]
    
    orgs = account.get("organizations", [])
    if not orgs:
        logger.error("未找到组织")
        return [{"error": "No organizations found"}]
    
    org_id = orgs[0]["id"]
    channels = get_cached_channels(org_id)
    logger.info(f"获取到 {len(channels)} 个频道", extra={"channels": [c['service'] for c in channels]})
    results = []
    
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
    
    for platform in platforms:
        matched = False
        
        for channel in channels:
            service = channel.get("service", "").lower()
            
            if service in platform_mapping.get(platform, []):
                matched = True
                logger.debug(f"平台 {platform} 匹配到频道: {channel['name']} ({service})")
                
                if channel.get("status") != "connected":
                    logger.warning(f"频道 {channel['name']} 未连接")
                    results.append({
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "failed",
                        "error": "Channel not connected"
                    })
                    continue
                
                media_url_to_use = media_url
                if platform == "tiktok" and media_url:
                    media_url_to_use = resize_image_for_tiktok(media_url)
                
                logger.debug(f"发布到频道: {channel['name']}")
                result = create_post(channel["id"], text, media_url_to_use, platform, immediate, schedule_time)
                
                if result and result.get("status") == "success":
                    logger.info(f"发布成功: {platform} -> {channel['name']}", extra={"post_id": result["post"].get("id")})
                    results.append({
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "success",
                        "post_id": result["post"].get("id"),
                        "scheduled_at": result["post"].get("scheduledAt")
                    })
                else:
                    error_msg = result.get("message", "Failed to create post") if result else "Unknown error"
                    logger.error(f"发布失败: {platform} -> {channel['name']}", extra={"error": error_msg})
                    results.append({
                        "platform": platform,
                        "channel": channel["name"],
                        "status": "failed",
                        "error": error_msg
                    })
        
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
    filter_part = ""
    if status_filter:
        status_items = ", ".join([f'"{s}"' for s in status_filter])
        filter_part = f'filter: {{ status: [{status_items}] }}'
    
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