import os
import logging
import asyncio
from flask import jsonify, render_template, request
from common.shared import get_bot_status, update_bot_status, logger

# 配置日志
logger = logging.getLogger(__name__)

# 异步任务
webhook_setup_task = None

def register_routes(app):
    """注册所有路由"""
    
    @app.route('/')
    def index():
        """主页"""
        status = get_bot_status()
        
        return render_template('index.html',
            bot_status=status,
            port=os.environ.get('PORT', 5000),
            debug=app.debug
        )

    @app.route('/status')
    def status():
        """获取状态"""
        status = get_bot_status()
        
        return jsonify({
            "bot_status": status,
            "service": "running",
            "port": os.environ.get('PORT', 5000)
        })

    @app.route('/health')
    def health():
        """健康检查"""
        return jsonify({
            "status": "healthy",
            "port": os.environ.get('PORT', 5000)
        })

    @app.route('/restart')
    def restart_bot():
        """重启机器人"""
        update_bot_status(restart_count=True)
        # 这里可以添加实际的重启逻辑
        return jsonify({
            "status": "success",
            "message": "重启命令已发送",
            "bot_status": get_bot_status()
        })

    @app.route('/webhook/<token>', methods=['POST'])
    async def webhook(token):
        """处理Telegram webhook"""
        # 验证令牌
        if token != os.environ.get('TELEGRAM_TOKEN'):
            logger.warning(f"收到无效令牌的webhook请求: {token[:5]}...")
            return jsonify({"status": "error", "message": "无效的令牌"}), 403
        
        # 导入webhook处理器
        from bot.webhook import process_update, setup_webhook
        
        # 确保webhook已设置
        global webhook_setup_task
        if webhook_setup_task is None or webhook_setup_task.done():
            logger.info("初始化webhook...")
            webhook_setup_task = asyncio.create_task(setup_webhook())
            await webhook_setup_task
        
        # 处理更新
        update_json = request.get_json()
        logger.info(f"收到webhook更新: {update_json}")
        
        # 异步处理更新
        success = await process_update(update_json)
        
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "error", "message": "处理更新失败"}), 500
        
    @app.route('/setup_webhook')
    async def setup_webhook_route():
        """手动设置webhook"""
        from bot.webhook import setup_webhook
        
        success = await setup_webhook()
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "Webhook已设置"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "设置Webhook失败"
            }), 500

    @app.route('/debug')
    def debug_info():
        """调试信息"""
        import sys
        import platform
        import psutil
        
        # 获取进程信息
        process = psutil.Process()
        memory_info = process.memory_info()
        
        debug_data = {
            "bot_status": get_bot_status(),
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "cpu_count": psutil.cpu_count(),
                "memory_usage": {
                    "rss": memory_info.rss / (1024 * 1024),  # MB
                    "vms": memory_info.vms / (1024 * 1024)   # MB
                }
            },
            "env_vars": {
                "PORT": os.environ.get("PORT", "未设置"),
                "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", "未设置")[:5] + "..." if os.environ.get("TELEGRAM_TOKEN") else "未设置",
                "GOOGLE_SHEET_ID": os.environ.get("GOOGLE_SHEET_ID", "未设置"),
                "GOOGLE_DRIVE_FOLDER_ID": os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "未设置"),
                "SERVICE_URL": os.environ.get("SERVICE_URL", "未设置")
            }
        }
        
        return jsonify(debug_data)

    @app.errorhandler(404)
    def not_found_error(error):
        """404错误处理"""
        return render_template('error.html',
            error_code=404,
            error_message="页面未找到"
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        return render_template('error.html',
            error_code=500,
            error_message="服务器内部错误"
        ), 500 
