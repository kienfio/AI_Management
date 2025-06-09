#!/bin/bash
# 更新pip
python -m pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 确保gunicorn安装正确
pip install gunicorn

echo "依赖安装完成" 