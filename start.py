import os
from app import app

if __name__ == "__main__":
    # 获取端口
    port = int(os.environ.get('PORT', 5000))
    # 启动Web服务
    app.run(host='0.0.0.0', port=port, debug=False)
    print(f"应用正在监听端口 {port}") 
