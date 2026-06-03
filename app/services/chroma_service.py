# -*- coding: utf-8 -*-
"""
Chroma向量知识库服务模块

该模块提供基于Chroma向量数据库的图文知识库操作，包括：
1. 知识库初始化
2. 语义搜索
3. 条目管理（添加、查询、编辑、删除）
4. 相似度计算
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os
import random
import time
from collections import OrderedDict
from app.config import Config
from app.services.logger import get_logger

logger = get_logger(__name__)

CHROMA_DIR = Config.CHROMA_DB_DIR
LOCAL_EMBEDDING_MODEL_PATH = Config.LOCAL_EMBEDDING_MODEL_PATH

sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=LOCAL_EMBEDDING_MODEL_PATH,
    trust_remote_code=True
)

client = chromadb.PersistentClient(
    path=CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=sentence_transformer_ef
)

INITIAL_DATA = [
    {
        "id": "1",
        "产品名称": "初始化",
        "文案内容": "xxxxxxxxxxxxxx。",
        "prompt": "xxxxxxxxxxxxxxxxxx",
        "image_url": None,
        "创建时间": str(int(time.time())),
        "来源": Config.SOURCE_MANUAL
    },
]

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

SEARCH_CACHE = OrderedDict()
MAX_CACHE_SIZE = Config.SEARCH_CACHE_MAX_SIZE

ENTRY_CACHE = {}
ENTRY_CACHE_TTL = 300

FIELD_WEIGHTS = {
    '产品名称': 2.0,
    '文案内容': 1.0,
    'prompt': 0.5
}

_last_init_check = 0
_INIT_CHECK_INTERVAL = 60
_is_initialized = None


def init_knowledge_base(force=False):
    global _last_init_check, _is_initialized
    
    now = time.time()
    if not force and _is_initialized is not None and (now - _last_init_check) < _INIT_CHECK_INTERVAL:
        return
    
    _last_init_check = now
    
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
    parts = []
    
    product_name = entry.get('产品名称', '')
    if product_name:
        parts.append(f"产品名称: {product_name}" * 2)
    else:
        parts.append("产品名称: 未知")
    
    content = entry.get('文案内容', '')
    if content:
        parts.append(f"文案内容: {content}")
    else:
        parts.append("文案内容: 暂无")
    
    if 'prompt' in entry and entry['prompt']:
        parts.append(f"提示词: {entry['prompt']}")
    
    if '标签' in entry and isinstance(entry['标签'], list) and len(entry['标签']) > 0:
        parts.append(f"标签: {', '.join(entry['标签'])}")
    
    return " ".join(parts)


def expand_keywords(keyword):
    expanded = [keyword]
    words = keyword.replace(' ', '').replace('，', ',').split(',')
    
    for word in words:
        if word in SYNONYM_DICT:
            expanded.extend(SYNONYM_DICT[word])
    
    return list(OrderedDict.fromkeys(expanded))


def search_knowledge_base(keyword, n_results=10, threshold=0.3):
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
    
    if not keyword:
        return []
    
    expanded_keywords_lower = [kw.lower() for kw in expanded_keywords]
    
    def matches_keyword(entry):
        entry_name = entry.get('产品名称', '').lower()
        entry_content = entry.get('文案内容', '').lower()
        entry_prompt = entry.get('prompt', '').lower()
        entry_tags = entry.get('标签', [])
        
        for kw in expanded_keywords_lower:
            if kw in entry_name or kw in entry_content or kw in entry_prompt:
                return True
            if isinstance(entry_tags, list):
                for tag in entry_tags:
                    if kw in str(tag).lower():
                        return True
        
        return False
    
    high_confidence_results = [r for r in filtered_results if r['similarity'] >= 0.5]
    low_confidence_results = [r for r in filtered_results if r['similarity'] < 0.5]
    
    low_confidence_filtered = [r for r in low_confidence_results if matches_keyword(r)]
    
    filtered_results = high_confidence_results + low_confidence_filtered
    
    filtered_results.sort(key=lambda x: x['composite_score'], reverse=True)
    final_results = filtered_results[:n_results]
    
    update_cache(cache_key, final_results)
    return final_results


def calculate_composite_score(entry, keyword, base_similarity):
    score = base_similarity * 0.7
    keyword_lower = keyword.lower()
    
    product_name = entry.get('产品名称', '').lower()
    if keyword_lower in product_name:
        score += 0.2
    elif product_name in keyword_lower:
        score += 0.1
    
    content = entry.get('文案内容', '').lower()
    if keyword_lower in content:
        score += 0.05
    
    prompt = entry.get('prompt', '').lower()
    if keyword_lower in prompt:
        score += 0.05
    
    return min(score, 1.0)


def update_cache(key, value):
    SEARCH_CACHE[key] = value
    while len(SEARCH_CACHE) > MAX_CACHE_SIZE:
        SEARCH_CACHE.popitem(last=False)


def get_search_suggestions(keyword):
    init_knowledge_base()
    all_entries = get_all_entries()
    suggestions = set()
    
    for entry in all_entries:
        product_name = entry.get('产品名称', '')
        
        if keyword.lower() in product_name.lower():
            suggestions.add(product_name)
        if product_name.lower() in keyword.lower():
            suggestions.add(product_name)
        
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
    init_knowledge_base()
    
    timestamp = str(int(time.time()))
    random_suffix = str(random.randint(1000, 9999))
    new_id = timestamp + random_suffix
    
    entry['id'] = new_id
    
    if '创建时间' not in entry:
        entry['创建时间'] = timestamp
    if '来源' not in entry:
        entry['来源'] = Config.SOURCE_MANUAL
    if '发布次数' not in entry:
        entry['发布次数'] = 0
    
    if '标签' in entry and len(entry['标签']) > 0:
        entry['标签'] = [str(tag) for tag in entry['标签']]
    elif '标签' in entry:
        del entry['标签']
    
    document = build_document(entry)
    
    cleaned_entry = {}
    for key, value in entry.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool, list)):
            cleaned_entry[key] = value
        else:
            cleaned_entry[key] = str(value)
    
    try:
        collection.add(
            ids=[f"entry_{new_id}"],
            documents=[document],
            metadatas=[cleaned_entry]
        )
        ENTRY_CACHE.clear()
        logger.info(f"条目添加成功: entry_{new_id}")
        return entry
    except Exception as e:
        logger.error(f"添加条目到Chroma失败: {str(e)}", extra={"entry_id": new_id, "document_length": len(document), "entry_keys": list(entry.keys())})
        raise


def update_entry(entry_id, updated_data):
    init_knowledge_base()
    
    existing_entry = get_entry_by_id(entry_id)
    if not existing_entry:
        return None
    
    merged_entry = {**existing_entry, **updated_data}
    merged_entry['id'] = entry_id
    if '创建时间' in existing_entry:
        merged_entry['创建时间'] = existing_entry['创建时间']
    
    merged_entry['更新时间'] = str(int(time.time()))
    
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
    
    ENTRY_CACHE.clear()
    return merged_entry


def update_publish_count(entry_id, increment=1):
    init_knowledge_base()
    
    existing_entry = get_entry_by_id(entry_id)
    if not existing_entry:
        logger.warning("更新发布次数失败：条目不存在", extra={"entry_id": entry_id})
        return None
    
    current_count = int(existing_entry.get('发布次数', 0))
    new_count = current_count + increment
    
    return update_entry(entry_id, {'发布次数': new_count})


def delete_entry(entry_id):
    init_knowledge_base()
    
    try:
        collection.delete(ids=[f"entry_{entry_id}"])
        ENTRY_CACHE.clear()
        SEARCH_CACHE.clear()
        return True
    except Exception:
        return False


def delete_entries_by_product(product_name):
    init_knowledge_base()
    
    try:
        all_entries = get_all_entries()
        deleted_count = 0
        
        for entry in all_entries:
            if entry.get('产品名称') == product_name:
                collection.delete(ids=[f"entry_{entry['id']}"])
                deleted_count += 1
        
        ENTRY_CACHE.clear()
        SEARCH_CACHE.clear()
        return deleted_count
    except Exception:
        return 0


def get_entry_by_id(entry_id):
    init_knowledge_base()
    
    results = collection.get(ids=[f"entry_{entry_id}"])
    if results['metadatas']:
        return results['metadatas'][0]
    return None


def get_all_entries(force_refresh=False):
    global ENTRY_CACHE
    
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
    
    ENTRY_CACHE[cache_key] = {
        'timestamp': time.time(),
        'data': entries
    }
    
    return entries


def get_entries_by_tag(tag):
    init_knowledge_base()
    all_entries = get_all_entries()
    
    results = []
    for entry in all_entries:
        tags = entry.get('标签', [])
        if isinstance(tags, list) and tag in tags:
            results.append(entry)
    
    return results


def calculate_similarity(text1, text2):
    import numpy as np
    
    embeddings = sentence_transformer_ef([text1, text2])
    
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
    SEARCH_CACHE.clear()
    ENTRY_CACHE.clear()


def search_by_field(field_name, value, n_results=10):
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