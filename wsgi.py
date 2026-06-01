# -*- coding: utf-8 -*-
"""
生产环境 WSGI 入口

用于 Gunicorn、uWSGI 等生产级 WSGI 服务器。

使用示例：
    gunicorn --workers=4 --bind=0.0.0.0:8000 wsgi:app
"""

import os
from app import create_app, register_index_route

# 使用生产环境配置
config_name = os.getenv('FLASK_ENV', 'production')
app = create_app(config_name)

# 注册首页路由
register_index_route(app)

# WSGI 应用对象
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)