# -*- coding: utf-8 -*-
"""
Chroma向量知识库模块 - 优化版

该模块提供基于Chroma向量数据库的图文知识库操作，包括：
1. 知识库初始化（含示例数据）
2. 语义搜索（基于Qwen3-Embedding-0.6B模型）- 优化版
3. 条目管理（添加、查询、编辑、删除）
4. 相似度计算
5. 新增字段：标签、创建时间、来源

优化特性：
- 多字段加权搜索（产品名称权重更高）
- 关键词同义词扩展
- 结果智能排序
- 搜索缓存机制
- 搜索建议功能
- 完整的CRUD操作

依赖：
- chromadb: 向量数据库
- sentence_transformers: 嵌入模型
- Qwen3-Embedding-0.6B: 本地嵌入模型
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os
import random
import time
from collections import OrderedDict
import sys

# 添加项目根目录到路径，以便导入config模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from app.logger import get_logger

# 初始化日志
logger = get_logger(__name__)

# 路径配置（使用config.py中的配置）
CHROMA_DIR = config.CHROMA_DB_DIR
LOCAL_EMBEDDING_MODEL_PATH = config.LOCAL_EMBEDDING_MODEL_PATH

# 初始化SentenceTransformer嵌入函数
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=LOCAL_EMBEDDING_MODEL_PATH,
    trust_remote_code=True
)

# 初始化Chroma客户端（持久化存储）
client = chromadb.PersistentClient(
    path=CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False)
)

# 创建或获取知识库集合
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=sentence_transformer_ef
)

# 初始示例数据（新增标签、时间戳、来源字段）
# 注意：ChromaDB 不允许空列表作为 metadata
INITIAL_DATA = [
    {
        "id": "1",
        "产品名称": "初始化",
        "文案内容": "xxxxxxxxxxxxxx。",
        "prompt": "xxxxxxxxxxxxxxxxxx",
        "image_url": "https://example.com/bebcare-nightlight.jpg",
        "创建时间": str(int(time.time())),
        "来源": config.SOURCE_MANUAL
    },
]

# 同义词词典（用于关键词扩展）
SYNONYM_DICT = {
    "夜灯": ["小夜灯", "婴儿夜灯", "宝宝夜灯", "睡眠灯", "床头灯", "氛围灯"],
    "灯": ["灯具", "照明", "光源", "灯光"],
    "婴儿": ["宝宝", "新生儿", "小孩", "孩童"],
    "儿童": ["小孩", "孩子", "宝贝", "幼儿"],
    "卧室": ["房间", "寝室", "睡房", "卧房"],
    "安全": ["安心", "放心", "可靠", "稳固"],
    "温暖": ["温馨", "柔和", "舒适", "和煦"],
    "智能": ["智能控制", "自动", "便捷", "高科技"],
    "便携": ["轻巧", "方便携带", "旅行", "随身"],
    "充电": ["蓄电", "电池", "续航", "无线"]
}

# 搜索缓存（LRU策略，使用config配置）
SEARCH_CACHE = OrderedDict()
MAX_CACHE_SIZE = config.SEARCH_CACHE_MAX_SIZE

# 条目缓存（缓存已加载的条目，避免重复查询）
ENTRY_CACHE = {}
ENTRY_CACHE_TTL = 300  # 条目缓存过期时间（秒）

# 字段权重配置
FIELD_WEIGHTS = {
    '产品名称': 2.0,
    '文案内容': 1.0,
    'prompt': 0.5
}

# 初始化检查缓存（避免频繁检查）
_last_init_check = 0
_INIT_CHECK_INTERVAL = 60  # 初始化检查间隔（秒）
_is_initialized = None


def init_knowledge_base(force=False):
    """
    初始化知识库（优化版）
    
    如果知识库为空，添加初始示例数据。
    该函数在其他操作前自动调用，确保知识库已初始化。
    
    Args:
        force (bool): 是否强制重新检查（默认False，使用缓存）
    """
    global _last_init_check, _is_initialized
    
    # 检查是否需要执行初始化检查
    now = time.time()
    if not force and _is_initialized is not None and (now - _last_init_check) < _INIT_CHECK_INTERVAL:
        # 使用缓存的初始化状态
        return
    
    _last_init_check = now
    
    # 只有在知识库为空时才添加初始数据
    if collection.count() == 0:
        ids = [f"entry_{item['id']}" for item in INITIAL_DATA]
        documents = [build_document(item) for item in INITIAL_DATA]
        metadatas = [item for item in INITIAL_DATA]
        
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
    
    _is_initialized = True


def build_document(entry):
    """
    构建用于向量检索的文档内容
    
    Args:
        entry (dict): 条目数据
        
    Returns:
        str: 构建好的文档字符串
    """
    parts = []
    parts.append(f"产品名称: {entry['产品名称']}" * 2)
    parts.append(f"文案内容: {entry['文案内容']}")
    
    if 'prompt' in entry:
        parts.append(f"提示词: {entry['prompt']}")
    
    # 处理标签，确保是列表且非空
    if '标签' in entry and isinstance(entry['标签'], list) and len(entry['标签']) > 0:
        parts.append(f"标签: {', '.join(entry['标签'])}")
    
    return " ".join(parts)


def expand_keywords(keyword):
    """
    扩展关键词，添加同义词
    
    Args:
        keyword (str): 原始关键词
        
    Returns:
        list: 扩展后的关键词列表
    """
    expanded = [keyword]
    words = keyword.replace(' ', '').replace('，', ',').split(',')
    
    for word in words:
        if word in SYNONYM_DICT:
            expanded.extend(SYNONYM_DICT[word])
    
    return list(OrderedDict.fromkeys(expanded))


def search_knowledge_base(keyword, n_results=10, threshold=0.3):
    """
    优化版语义搜索知识库
    
    Args:
        keyword (str): 搜索关键词
        n_results (int): 返回结果数量
        threshold (float): 相似度阈值
        
    Returns:
        list: 搜索结果列表
    """
    init_knowledge_base()
    
    cache_key = f"{keyword}_{n_results}_{threshold}"
    if cache_key in SEARCH_CACHE:
        SEARCH_CACHE.move_to_end(cache_key)
        return SEARCH_CACHE[cache_key]
    
    expanded_keywords = expand_keywords(keyword)
    all_results = []
    seen_ids = set()
    
    for kw in expanded_keywords:
        results = collection.query(
            query_texts=[kw],
            n_results=n_results * 2
        )
        
        for i, metadata in enumerate(results['metadatas'][0]):
            entry_id = metadata.get('id')
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            
            distance = results['distances'][0][i]
            similarity = 1 - distance
            score = calculate_composite_score(metadata, keyword, similarity)
            
            all_results.append({
                **metadata,
                'similarity': similarity,
                'composite_score': score
            })
    
    filtered_results = [r for r in all_results if r['similarity'] >= threshold]
    filtered_results.sort(key=lambda x: x['composite_score'], reverse=True)
    final_results = filtered_results[:n_results]
    
    update_cache(cache_key, final_results)
    return final_results


def calculate_composite_score(entry, keyword, base_similarity):
    """
    计算综合得分
    
    Args:
        entry (dict): 条目数据
        keyword (str): 搜索关键词
        base_similarity (float): 基础相似度
        
    Returns:
        float: 综合得分
    """
    score = base_similarity * 0.5
    keyword_lower = keyword.lower()
    
    product_name = entry.get('产品名称', '').lower()
    if keyword_lower in product_name or product_name in keyword_lower:
        score += 0.3
    
    content = entry.get('文案内容', '').lower()
    if keyword_lower in content:
        score += 0.1
    
    return min(score, 1.0)


def update_cache(key, value):
    """
    更新搜索缓存（LRU策略）
    """
    SEARCH_CACHE[key] = value
    while len(SEARCH_CACHE) > MAX_CACHE_SIZE:
        SEARCH_CACHE.popitem(last=False)


def get_search_suggestions(keyword):
    """
    获取搜索建议
    
    Args:
        keyword (str): 输入关键词
        
    Returns:
        list: 搜索建议列表
    """
    init_knowledge_base()
    all_entries = get_all_entries()
    suggestions = set()
    
    for entry in all_entries:
        product_name = entry.get('产品名称', '')
        
        if keyword.lower() in product_name.lower():
            suggestions.add(product_name)
        if product_name.lower() in keyword.lower():
            suggestions.add(product_name)
        
        # 正确处理标签
        tags = entry.get('标签', [])
        if isinstance(tags, list):
            for tag in tags:
                if keyword.lower() in str(tag).lower():
                    suggestions.add(str(tag))
    
    expanded = expand_keywords(keyword)
    suggestions.update(expanded)
    suggestions.discard(keyword)
    
    return sorted(list(suggestions))[:5]


def get_random_entry_by_product(product_name):
    """
    根据产品名称获取随机条目
    
    Args:
        product_name (str): 产品名称
        
    Returns:
        dict or None: 随机条目
    """
    entries = search_knowledge_base(product_name)
    if not entries:
        return None
    
    weights = [entry.get('composite_score', entry.get('similarity', 0)) for entry in entries]
    total_weight = sum(weights)
    
    if total_weight == 0:
        return random.choice(entries)
    
    random_value = random.uniform(0, total_weight)
    current = 0
    for entry, weight in zip(entries, weights):
        current += weight
        if current >= random_value:
            return entry
    
    return entries[0]


def add_entry(entry):
    """
    添加新条目到知识库
    
    Args:
        entry (dict): 条目数据
        
    Returns:
        dict: 添加后的完整条目
    """
    init_knowledge_base()
    
    timestamp = str(int(time.time()))
    random_suffix = str(random.randint(1000, 9999))
    new_id = timestamp + random_suffix
    
    entry['id'] = new_id
    
    if '创建时间' not in entry:
        entry['创建时间'] = timestamp
    if '来源' not in entry:
        entry['来源'] = config.SOURCE_MANUAL
    if '发布次数' not in entry:
        entry['发布次数'] = 0
    
    # ChromaDB 不允许空列表作为 metadata
    if '标签' in entry and len(entry['标签']) > 0:
        # 确保标签是字符串列表
        entry['标签'] = [str(tag) for tag in entry['标签']]
    elif '标签' in entry:
        del entry['标签']
    
    document = build_document(entry)
    collection.add(
        ids=[f"entry_{new_id}"],
        documents=[document],
        metadatas=[entry]
    )
    
    # 只清除条目缓存（搜索缓存可能仍然有效）
    ENTRY_CACHE.clear()
    return entry


def update_entry(entry_id, updated_data):
    """
    更新知识库条目
    
    Args:
        entry_id (str): 条目ID
        updated_data (dict): 更新的数据
        
    Returns:
        dict or None: 更新后的条目，失败返回None
    """
    init_knowledge_base()
    
    existing_entry = get_entry_by_id(entry_id)
    if not existing_entry:
        return None
    
    # 合并数据
    merged_entry = {**existing_entry, **updated_data}
    
    # 保留重要字段
    merged_entry['id'] = entry_id
    if '创建时间' in existing_entry:
        merged_entry['创建时间'] = existing_entry['创建时间']
    
    # 更新更新时间
    merged_entry['更新时间'] = str(int(time.time()))
    
    # ChromaDB 不允许空列表作为 metadata
    if '标签' in merged_entry and len(merged_entry['标签']) > 0:
        merged_entry['标签'] = [str(tag) for tag in merged_entry['标签']]
    elif '标签' in merged_entry:
        del merged_entry['标签']
    
    document = build_document(merged_entry)
    
    collection.update(
        ids=[f"entry_{entry_id}"],
        documents=[document],
        metadatas=[merged_entry]
    )
    
    # 只清除条目缓存（搜索缓存可能仍然有效）
    ENTRY_CACHE.clear()
    return merged_entry


def update_publish_count(entry_id, increment=1):
    """
    更新条目的发布次数
    
    Args:
        entry_id (str): 条目ID
        increment (int): 增量，默认1
        
    Returns:
        dict: 更新后的条目
    """
    init_knowledge_base()
    
    existing_entry = get_entry_by_id(entry_id)
    if not existing_entry:
        logger.warning("更新发布次数失败：条目不存在", extra={"entry_id": entry_id})
        return None
    
    current_count = int(existing_entry.get('发布次数', 0))
    new_count = current_count + increment
    
    return update_entry(entry_id, {'发布次数': new_count})


def delete_entry(entry_id):
    """
    删除知识库条目
    
    Args:
        entry_id (str): 条目ID
        
    Returns:
        bool: 是否删除成功
    """
    init_knowledge_base()
    
    try:
        collection.delete(ids=[f"entry_{entry_id}"])
        # 只清除条目缓存（搜索缓存可能仍然有效）
        ENTRY_CACHE.clear()
        return True
    except Exception:
        return False


def get_entry_by_id(entry_id):
    """
    根据ID获取条目
    
    Args:
        entry_id (str): 条目ID
        
    Returns:
        dict or None: 条目数据
    """
    init_knowledge_base()
    
    results = collection.get(ids=[f"entry_{entry_id}"])
    if results['metadatas']:
        return results['metadatas'][0]
    return None


def get_all_entries(force_refresh=False):
    """
    获取所有知识库条目（优化版，带缓存）
    
    Args:
        force_refresh (bool): 是否强制刷新缓存（默认False，使用缓存）
    
    Returns:
        list: 所有条目列表
    """
    global ENTRY_CACHE
    
    # 检查缓存
    cache_key = 'all_entries'
    if not force_refresh and cache_key in ENTRY_CACHE:
        cached = ENTRY_CACHE[cache_key]
        if time.time() - cached['timestamp'] < ENTRY_CACHE_TTL:
            return cached['data']
    
    init_knowledge_base()
    results = collection.get()
    
    entries = []
    for metadata in results['metadatas']:
        entries.append(metadata)
    
    # 更新缓存
    ENTRY_CACHE[cache_key] = {
        'timestamp': time.time(),
        'data': entries
    }
    
    return entries


def get_entries_by_tag(tag):
    """
    根据标签获取条目
    
    Args:
        tag (str): 标签
        
    Returns:
        list: 匹配的条目列表
    """
    init_knowledge_base()
    all_entries = get_all_entries()
    
    results = []
    for entry in all_entries:
        tags = entry.get('标签', [])
        # 处理可能没有标签字段或者标签不是列表的情况
        if isinstance(tags, list) and tag in tags:
            results.append(entry)
    
    return results


def calculate_similarity(text1, text2):
    """
    计算两段文本的语义相似度
    
    Args:
        text1 (str): 第一段文本
        text2 (str): 第二段文本
        
    Returns:
        float: 相似度分数（0-1）
    """
    import numpy as np
    
    # 使用嵌入函数获取两段文本的向量表示
    embeddings = sentence_transformer_ef([text1, text2])
    
    # 计算余弦相似度
    vec1 = np.array(embeddings[0])
    vec2 = np.array(embeddings[1])
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(similarity)


def clear_cache():
    """
    清空搜索缓存和条目缓存
    """
    SEARCH_CACHE.clear()
    ENTRY_CACHE.clear()


def search_by_field(field_name, value, n_results=10):
    """
    按指定字段精确搜索
    
    Args:
        field_name (str): 字段名称
        value (str): 搜索值
        n_results (int): 返回数量
        
    Returns:
        list: 匹配的条目列表
    """
    init_knowledge_base()
    all_entries = get_all_entries()
    
    results = []
    for entry in all_entries:
        if field_name in entry:
            entry_value = str(entry[field_name]).lower()
            search_value = value.lower()
            
            if search_value in entry_value or entry_value in search_value:
                similarity = calculate_similarity(value, entry[field_name])
                results.append({
                    **entry,
                    'similarity': similarity
                })
    
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:n_results]

