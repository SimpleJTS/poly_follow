#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket 聪明钱监控系统 - 启动入口
"""
import logging
import sys
from flask import Flask
from flask_cors import CORS

from app.config import WEB_HOST, WEB_PORT, LOG_LEVEL
from app.models import init_db
from app.routes import api
from app.services.monitor import get_monitor_service

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(
        __name__,
        template_folder='app/templates',
        static_folder='app/static',
    )
    
    # 启用 CORS
    CORS(app)
    
    # 注册蓝图
    app.register_blueprint(api)
    
    # 首页重定向
    @app.route('/')
    def index():
        from flask import redirect
        return redirect('/api/')
    
    return app


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Polymarket 聪明钱监控系统启动中...")
    logger.info("=" * 50)
    
    # 初始化数据库
    logger.info("初始化数据库...")
    init_db()
    
    # 创建 Flask 应用
    app = create_app()
    
    # 启动监控服务
    logger.info("启动监控服务...")
    monitor = get_monitor_service()
    monitor.start()
    
    # 启动 Web 服务
    logger.info(f"启动 Web 服务: http://{WEB_HOST}:{WEB_PORT}")
    logger.info("=" * 50)
    
    try:
        app.run(
            host=WEB_HOST,
            port=WEB_PORT,
            debug=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        logger.info("收到停止信号...")
    finally:
        monitor.stop()
        logger.info("程序已退出")


if __name__ == '__main__':
    main()
