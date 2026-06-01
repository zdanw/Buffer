# -*- coding: utf-8 -*-
"""
API路由层模块

包含所有 Flask Blueprint 定义。
"""

from flask import Blueprint

api_bp = Blueprint('api', __name__)

# 导入各个子路由模块
from . import knowledge, publish, products, utils