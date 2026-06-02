# -*- coding: utf-8 -*-
"""
服务层模块

包含所有业务逻辑服务，无 Flask 依赖。
"""

from .logger import get_logger
from .chroma_service import (
    search_knowledge_base,
    get_random_entry_by_product,
    add_entry,
    get_all_entries,
    get_search_suggestions,
    search_by_field,
    update_entry,
    delete_entry,
    delete_entries_by_product,
    get_entry_by_id,
    get_entries_by_tag,
    update_publish_count
)
from .buffer_service import publish_to_platforms
from .ai_service import (
    generate_content,
    generate_image,
    generate_unique_content,
    generate_unique_image
)
from .github_service import (
    upload_image_to_github,
    convert_github_url_to_cdn,
    get_upload_history,
    get_latest_upload
)

__all__ = [
    'get_logger',
    'search_knowledge_base',
    'get_random_entry_by_product',
    'add_entry',
    'get_all_entries',
    'get_search_suggestions',
    'search_by_field',
    'update_entry',
    'delete_entry',
    'delete_entries_by_product',
    'get_entry_by_id',
    'get_entries_by_tag',
    'update_publish_count',
    'publish_to_platforms',
    'generate_content',
    'generate_image',
    'generate_unique_content',
    'generate_unique_image',
    'upload_image_to_github',
    'convert_github_url_to_cdn',
    'get_upload_history',
    'get_latest_upload'
]