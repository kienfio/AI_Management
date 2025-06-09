import os
import threading
import logging
from flask import Flask, render_template, jsonify
from main import main as start_bot

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 状态变量
bot_status = {"running": False, "start_time": None}

# 启动Telegram机器人的线程
def run_telegram_bot():
    try:
        logger.info("正在启动Telegram机器人...")
        start_bot()
    except Exception as e:
        logger.error(f"启动机器人时出错: {e}")

# 路由：主页
@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "AI财务管理机器人服务已启动"
    })

# 路由：状态检查
@app.route('/status')
def status():
    return jsonify({
        "bot_status": bot_status,
        "service": "running"
    })

# 路由：健康检查
@app.route('/health')
def health():
    return jsonify({
        "status": "healthy"
    })

# 启动机器人线程
if not bot_status["running"]:
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True  # 设置为守护线程，这样它会在主程序结束时终止
    bot_thread.start()
    bot_status["running"] = True
    import datetime
    bot_status["start_time"] = datetime.datetime.now().isoformat()
    logger.info("机器人后台线程已启动")

# 主程序入口
if __name__ == '__main__':
    # 获取端口
    port = int(os.environ.get('PORT', 5000))
    # 启动Web服务
    app.run(host='0.0.0.0', port=port) 