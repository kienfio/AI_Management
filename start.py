import os
import multiprocessing
import asyncio
from app import create_app

def run_flask():
    """运行Flask应用"""
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    # 在生产环境中禁用调试模式
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot_wrapper():
    """包装异步bot运行函数"""
    import asyncio
    from bot.main import run_bot
    # 创建新的事件循环并运行协程
    asyncio.run(run_bot())

if __name__ == '__main__':
    # 启动Flask进程
    flask_process = multiprocessing.Process(target=run_flask)
    flask_process.start()
    
    # 启动Bot进程（使用包装器处理异步协程）
    bot_process = multiprocessing.Process(target=run_bot_wrapper)
    bot_process.start()
    
    # 等待两个进程结束
    flask_process.join()
    bot_process.join() 
