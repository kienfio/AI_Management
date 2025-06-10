import os
import multiprocessing
import asyncio
import logging
from app import create_app

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_flask():
    """运行Flask应用"""
    logger.info("正在启动Flask应用...")
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    # 在生产环境中禁用调试模式
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot_wrapper():
    """包装异步bot运行函数"""
    logger.info("正在准备启动机器人...")
    import asyncio
    from bot.main import run_bot
    try:
        # 创建新的事件循环并运行协程
        logger.info("创建新的事件循环...")
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"运行机器人包装器时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    logger.info("启动应用...")
    try:
        # 启动Flask进程
        logger.info("创建Flask进程...")
        flask_process = multiprocessing.Process(target=run_flask)
        flask_process.start()
        
        # 启动Bot进程（使用包装器处理异步协程）
        logger.info("创建Bot进程...")
        bot_process = multiprocessing.Process(target=run_bot_wrapper)
        bot_process.start()
        
        # 等待两个进程结束
        logger.info("主进程等待子进程...")
        flask_process.join()
        bot_process.join()
    except Exception as e:
        logger.error(f"启动进程时出错: {e}")
        import traceback
        logger.error(traceback.format_exc()) 
