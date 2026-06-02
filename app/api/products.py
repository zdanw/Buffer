# -*- coding: utf-8 -*-
"""
产品管理API蓝本

该模块提供产品管理的增删改查接口。
"""

from flask import request, jsonify
import json
import os

from app.config import Config
from app.services.logger import get_logger
from app.services import delete_entries_by_product
from app.api import api_bp

logger = get_logger(__name__)


def load_products():
    if not os.path.exists(Config.PRODUCTS_FILE):
        os.makedirs(os.path.dirname(Config.PRODUCTS_FILE), exist_ok=True)
        initial_products = []
        with open(Config.PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_products, f, ensure_ascii=False, indent=2)
        return initial_products
    
    with open(Config.PRODUCTS_FILE, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
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
    os.makedirs(os.path.dirname(Config.PRODUCTS_FILE), exist_ok=True)
    with open(Config.PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def get_next_id(products):
    if not products:
        return 1
    return max(p['id'] for p in products) + 1


@api_bp.route('/products', methods=['GET'])
def get_products():
    products = load_products()
    return jsonify({"products": products})


@api_bp.route('/products', methods=['POST'])
def add_product():
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


@api_bp.route('/products/<int:index>', methods=['PUT'])
def update_product(index):
    data = request.json
    new_name = data.get('product_name', '').strip()
    new_description = data.get('description', '').strip()
    
    if not new_name:
        return jsonify({"error": "请输入产品名称"}), 400
    
    products = load_products()
    
    if index < 0 or index >= len(products):
        return jsonify({"error": "产品不存在"}), 404
    
    old_name = products[index]['name']
    
    if any(p['name'] == new_name and p != products[index] for p in products):
        return jsonify({"error": "产品已存在"}), 400
    
    products[index]['name'] = new_name
    products[index]['description'] = new_description
    save_products(products)
    
    logger.info("产品已修改", extra={"old_name": old_name, "new_name": new_name})
    return jsonify({"status": "success", "old_name": old_name, "new_name": new_name, "products": products})


@api_bp.route('/products/<int:index>', methods=['DELETE'])
def delete_product(index):
    products = load_products()
    
    if index < 0 or index >= len(products):
        return jsonify({"error": "产品不存在"}), 404
    
    deleted = products.pop(index)
    save_products(products)
    
    delete_entries_by_product(deleted['name'])
    
    logger.info("产品已删除", extra={"product_name": deleted['name']})
    return jsonify({"status": "success", "deleted": deleted, "products": products})