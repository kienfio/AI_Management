import os
import multiprocessing
from app import create_app
from bot.main import run_bot

def run_flask():
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # 启动Flask进程
    flask_process = multiprocessing.Process(target=run_flask)
    flask_process.start()
    
    # 启动Bot进程
    bot_process = multiprocessing.Process(target=run_bot)
    bot_process.start()
    
    # 等待两个进程结束
    flask_process.join()
    bot_process.join() 