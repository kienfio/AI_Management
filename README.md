# AI财务管理助手

基于Telegram的财务管理机器人，能记录收入支出，保存收据照片，并同步到Google Sheet与Google Drive。

## 功能特点

- 📊 记录各类支出和收入
- 📷 保存收据照片到Google Drive
- 📝 自动将记录同步到Google Sheet
- 📈 生成月度财务报告
- 🔄 支持交互式命令输入

## 环境要求

- Python 3.8+
- Telegram Bot Token
- Google Cloud 项目凭证 (用于Google Sheet和Drive API)

## 安装步骤

1. 克隆本仓库：
```
git clone https://github.com/yourusername/ai-financial-assistant.git
cd ai-financial-assistant
```

2. 安装依赖：
```
pip install -r requirements.txt
```

3. 设置环境变量：
   - 复制`env.example`为`.env`
   - 编辑`.env`文件，填入你的Telegram令牌和Google API凭证信息

## Google API设置

1. 创建Google Cloud项目并启用以下API：
   - Google Sheets API
   - Google Drive API

2. 创建服务账号并下载凭证JSON文件

3. 创建Google表格，并记下表格ID

4. 创建Google Drive文件夹，并记下文件夹ID

5. 将服务账号邮箱添加为Google表格和Drive文件夹的编辑者

## 使用方法

1. 运行机器人：
```
python main.py
```

2. 在Telegram中与机器人交互，使用以下命令：
   - `/start` - 开始使用机器人
   - `/help` - 查看帮助信息
   - `/expense` - 记录支出
   - `/income` - 记录收入
   - `/report` - 生成月度财务报告

## 支持的类别

### 支出类别
- 食品、住房、交通、娱乐、医疗、教育、水电、其他

### 收入类别
- 薪资、奖金、投资、兼职、其他

## 机器人使用示例

### 记录支出
- 直接命令: `/expense 食品 50.5 午餐 公司餐厅`
- 交互式: 发送 `/expense` 然后按提示操作

### 记录收入
- 直接命令: `/income 薪资 5000 8月工资`
- 交互式: 发送 `/income` 然后按提示操作

### 生成报告
- 当前月份: `/report`
- 指定月份: `/report 2023 12` 