# -*- coding: utf-8 -*-
"""
开发环境启动脚本

使用 Flask 内置开发服务器运行应用。

运行方式：
    python run.py
    
环境变量：
    FLASK_ENV: development (默认), production, testing
    FLASK_DEBUG: True/False (是否启用调试模式)
    PORT: 端口号，默认5000
"""

import os
from app import create_app, register_index_route

# 获取环境配置
config_name = os.getenv('FLASK_ENV', 'development')
debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
port = int(os.getenv('PORT', 5000))

# 创建应用
app = create_app(config_name)

# 注册首页路由
register_index_route(app)

# 初始化定时任务调度器
from app.services.scheduler_service import init_scheduler
init_scheduler()

if __name__ == '__main__':
    print(f"🚀 启动应用，配置环境: {config_name}")
    print(f"📡 服务地址: http://localhost:{port}")
    
    use_reloader = os.getenv('FLASK_RELOADER', str(debug_mode)).lower() == 'true'
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port,
        use_reloader=use_reloader
    )