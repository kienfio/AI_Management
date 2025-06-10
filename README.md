# 销售管理 Telegram Bot

这是一个基于Telegram的销售管理机器人，专为销售代理或小企业主设计，用于记录和管理销售发票、费用支出，并生成各类报表。系统使用Google Sheets作为数据存储和同步工具。

## 功能特点

- 📊 **销售记录管理**：记录发票信息、客户类型、佣金计算
- 💰 **费用支出管理**：记录各类费用、供应商信息
- 👥 **代理商管理**：维护代理商信息和佣金比例
- 🏢 **供应商管理**：管理供应商联系方式和产品服务
- 📈 **报表生成**：按月、年生成销售和费用报表

## 技术架构

- **前端界面**：Telegram Bot API
- **后端语言**：Python
- **数据存储**：Google Sheets API
- **部署环境**：Render

## 安装步骤

### 1. 克隆代码库

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

创建`.env`文件，参考`env.example`模板：

```
DEBUG=True
GOOGLE_CREDENTIALS_CONTENT={"your":"credentials"}
GOOGLE_SHEETS_ID=your_sheet_id
TELEGRAM_TOKEN=your_bot_token
```

### 4. 准备Google服务账号

1. 访问[Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目并启用Google Sheets API和Google Drive API
3. 创建服务账号并下载JSON凭证
4. 将JSON内容填入环境变量`GOOGLE_CREDENTIALS_CONTENT`

### 5. 创建Telegram Bot

1. 通过[@BotFather](https://t.me/BotFather)创建新Bot
2. 获取Bot Token并填入环境变量`TELEGRAM_TOKEN`

### 6. 准备Google Sheet

1. 创建新的Google Sheet
2. 从URL获取Sheet ID并填入环境变量`GOOGLE_SHEETS_ID`
3. 与服务账号共享此Sheet（编辑权限）

## 启动服务

本地开发环境：

```bash
python main.py
```

## Render部署指南

1. 在Render上创建新的Web Service
2. 连接到您的Git仓库
3. 设置构建命令：`pip install -r requirements.txt`
4. 设置启动命令：`python main.py`
5. 添加所有环境变量
6. 部署服务

## 使用方法

1. 在Telegram中搜索您的Bot用户名
2. 发送`/start`命令开始使用
3. 通过菜单按钮进行各项操作：
   - 添加销售记录
   - 记录费用支出
   - 查看月度报表
   - 管理代理商和供应商

## 项目结构

- `main.py`: 主程序入口
- `config.py`: 配置文件和常量定义
- `google_sheets.py`: Google Sheets API交互
- `telegram_handlers.py`: Telegram Bot命令处理

## 注意事项

- 确保Google服务账号有足够权限访问Sheet
- 定期备份Google Sheet数据
- 不要在公共场合分享您的环境变量

## 技术支持

如有问题，请联系项目维护者。 