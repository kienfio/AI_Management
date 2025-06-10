    import os
    import io
    import json
    from datetime import datetime
    from dotenv import load_dotenv
    import pandas as pd
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2 import service_account
    from tempfile import NamedTemporaryFile

    class GoogleServices:
        """处理与Google服务（Sheets和Drive）的所有交互"""
        
        def __init__(self):
            # 加载环境变量
            load_dotenv()
            
            # 获取凭证文件路径或内容
            credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
            credentials_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
            self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
            self.drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
            
            # 定义所需权限
            self.scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 加载凭证
            try:
                # 尝试从环境变量内容获取凭证
                if credentials_content:
                    # 从环境变量加载凭证内容
                    credentials_dict = json.loads(credentials_content)
                    
                    # 创建临时文件以供google-auth库使用
                    self.temp_file = NamedTemporaryFile(delete=False)
                    with open(self.temp_file.name, 'w') as tmp:
                        json.dump(credentials_dict, tmp)
                    
                    # 使用临时文件路径加载凭证
                    self.credentials = service_account.Credentials.from_service_account_file(
                        self.temp_file.name, scopes=self.scopes
                    )
                    
                    # 清理临时文件
                    os.unlink(self.temp_file.name)
                    
                # 如果没有环境变量内容，尝试从文件读取
                elif credentials_file:
                    self.credentials = service_account.Credentials.from_service_account_file(
                        credentials_file, scopes=self.scopes
                    )
                else:
                    raise ValueError("未提供Google凭证，请设置GOOGLE_CREDENTIALS_FILE或GOOGLE_CREDENTIALS_CONTENT环境变量")
                
                # 初始化服务
                self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
                self.drive_service = build('drive', 'v3', credentials=self.credentials)
                
                # 检查并创建必要的工作表
                self._setup_sheets()
                
            except Exception as e:
                print(f"初始化Google服务时出错: {e}")
        
        def _setup_sheets(self):
            """检查并创建必要的工作表"""
            try:
                # 获取现有工作表
                sheet_metadata = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
                sheets = sheet_metadata.get('sheets', [])
                
                # 提取工作表名称
                sheet_names = [sheet['properties']['title'] for sheet in sheets]
                
                # 检查并创建支出工作表
                if '支出' not in sheet_names:
                    self._create_sheet('支出', ['日期', '类别', '金额', '描述', '备注', '收据链接'])
                
                # 检查并创建收入工作表
                if '收入' not in sheet_names:
                    self._create_sheet('收入', ['日期', '类别', '金额', '描述', '备注'])
                
            except Exception as e:
                print(f"设置工作表时出错: {e}")
        
        def _create_sheet(self, sheet_name, headers):
            """创建新工作表并添加表头"""
            try:
                # 创建新工作表
                body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': sheet_name
                            }
                        }
                    }]
                }
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
                
                # 添加表头
                range_name = f'{sheet_name}!A1:{chr(65 + len(headers) - 1)}1'
                body = {
                    'values': [headers]
                }
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
            except Exception as e:
                print(f"创建工作表 {sheet_name} 时出错: {e}")
        
        def add_expense(self, date, category, amount, description, note='', receipt_url=''):
            """添加支出记录到Google Sheet"""
            try:
                values = [[date, category, amount, description, note, receipt_url]]
                
                # 获取当前数据以确定下一行
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range='支出!A:F'
                ).execute()
                
                existing_values = result.get('values', [])
                next_row = len(existing_values) + 1
                
                # 添加新记录
                range_name = f'支出!A{next_row}'
                body = {
                    'values': values
                }
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                return True
                
            except Exception as e:
                print(f"添加支出记录时出错: {e}")
                return False
        
        def add_income(self, date, category, amount, description, note=''):
            """添加收入记录到Google Sheet"""
            try:
                values = [[date, category, amount, description, note]]
                
                # 获取当前数据以确定下一行
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range='收入!A:E'
                ).execute()
                
                existing_values = result.get('values', [])
                next_row = len(existing_values) + 1
                
                # 添加新记录
                range_name = f'收入!A{next_row}'
                body = {
                    'values': values
                }
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                return True
                
            except Exception as e:
                print(f"添加收入记录时出错: {e}")
                return False
        
        def upload_receipt(self, image_bytes, description):
            """上传收据照片到Google Drive并返回链接"""
            try:
                # 准备文件元数据
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                file_name = f"收据_{timestamp}_{description}.jpg"
                
                file_metadata = {
                    'name': file_name,
                    'parents': [self.drive_folder_id]
                }
                
                # 准备媒体
                media = MediaIoBaseUpload(
                    io.BytesIO(image_bytes),
                    mimetype='image/jpeg',
                    resumable=True
                )
                
                # 上传文件
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                
                # 返回链接
                return file.get('webViewLink')
                
            except Exception as e:
                print(f"上传收据时出错: {e}")
                return None
        
        def get_monthly_summary(self, year=None, month=None):
            """获取指定月份的收支汇总"""
            if year is None or month is None:
                now = datetime.now()
                year = now.year
                month = now.month
            
            try:
                # 格式化月份
                month_str = str(month).zfill(2)
                date_filter = f"{year}-{month_str}"
                
                # 获取支出数据
                expenses_result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range='支出!A:C'
                ).execute()
                
                expense_values = expenses_result.get('values', [])
                
                # 获取收入数据
                income_result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range='收入!A:C'
                ).execute()
                
                income_values = income_result.get('values', [])
                
                # 处理数据
                total_expense = 0
                total_income = 0
                expense_by_category = {}
                income_by_category = {}
                
                # 处理表头
                if len(expense_values) > 0:
                    expense_values = expense_values[1:]
                if len(income_values) > 0:
                    income_values = income_values[1:]
                
                # 计算支出
                for row in expense_values:
                    if len(row) >= 3 and date_filter in row[0]:
                        category = row[1]
                        try:
                            amount = float(row[2])
                            total_expense += amount
                            if category in expense_by_category:
                                expense_by_category[category] += amount
                            else:
                                expense_by_category[category] = amount
                        except ValueError:
                            continue
                
                # 计算收入
                for row in income_values:
                    if len(row) >= 3 and date_filter in row[0]:
                        category = row[1]
                        try:
                            amount = float(row[2])
                            total_income += amount
                            if category in income_by_category:
                                income_by_category[category] += amount
                            else:
                                income_by_category[category] = amount
                        except ValueError:
                            continue
                
                # 准备汇总数据
                summary = {
                    'year': year,
                    'month': month,
                    'total_income': total_income,
                    'total_expense': total_expense,
                    'net': total_income - total_expense,
                    'expense_by_category': expense_by_category,
                    'income_by_category': income_by_category
                }
                
                return summary
                
            except Exception as e:
                print(f"获取月度汇总时出错: {e}")
                return None 
