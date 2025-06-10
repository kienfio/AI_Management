import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from common.google_services import GoogleServices

# 配置日志
logger = logging.getLogger(__name__)

class DataManager:
    """数据管理器类，处理所有数据操作"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.google_services = GoogleServices(required=True)
        
    def add_expense(self, data: Dict[str, Union[str, float]]) -> bool:
        """
        添加支出记录
        
        Args:
            data: 包含支出信息的字典
                {
                    'date': '2024-01-01',
                    'category': '餐饮',
                    'amount': 50.0,
                    'description': '午餐',
                    'note': '可选备注',
                    'receipt_url': '可选收据链接'
                }
        
        Returns:
            bool: 是否添加成功
        """
        try:
            # 验证必要字段
            required_fields = ['date', 'category', 'amount', 'description']
            if not all(field in data for field in required_fields):
                logger.error("缺少必要字段")
                return False
                
            # 验证日期格式
            try:
                datetime.strptime(data['date'], '%Y-%m-%d')
            except ValueError:
                logger.error("日期格式错误，应为YYYY-MM-DD")
                return False
                
            # 验证金额
            if not isinstance(data['amount'], (int, float)) or data['amount'] <= 0:
                logger.error("金额必须是大于0的数字")
                return False
                
            # 添加记录
            return self.google_services.add_expense(
                date=data['date'],
                category=data['category'],
                amount=data['amount'],
                description=data['description'],
                note=data.get('note', ''),
                receipt_url=data.get('receipt_url', '')
            )
            
        except Exception as e:
            logger.error(f"添加支出记录时出错: {e}")
            return False
            
    def upload_receipt(self, file_path: str, file_name: Optional[str] = None) -> Optional[str]:
        """
        上传收据照片
        
        Args:
            file_path: 文件路径
            file_name: 可选的文件名
            
        Returns:
            Optional[str]: 文件的Web查看链接，如果上传失败则返回None
        """
        try:
            return self.google_services.upload_file(file_path, file_name)
        except Exception as e:
            logger.error(f"上传收据时出错: {e}")
            return None
            
    def get_categories(self) -> List[str]:
        """
        获取所有支出类别
        
        Returns:
            List[str]: 支出类别列表
        """
        return [
            "餐饮",
            "交通",
            "购物",
            "娱乐",
            "居住",
            "医疗",
            "教育",
            "其他"
        ]
        
    def validate_category(self, category: str) -> bool:
        """
        验证支出类别是否有效
        
        Args:
            category: 要验证的类别
            
        Returns:
            bool: 类别是否有效
        """
        return category in self.get_categories()
        
    def format_amount(self, amount: Union[int, float, str]) -> Optional[float]:
        """
        格式化金额
        
        Args:
            amount: 要格式化的金额
            
        Returns:
            Optional[float]: 格式化后的金额，如果格式无效则返回None
        """
        try:
            if isinstance(amount, str):
                # 移除货币符号和空格
                amount = amount.replace('¥', '').replace('￥', '').strip()
            return float(amount)
        except (ValueError, TypeError):
            return None
            
    def format_date(self, date_str: str) -> Optional[str]:
        """
        格式化日期字符串为YYYY-MM-DD格式
        
        Args:
            date_str: 日期字符串
            
        Returns:
            Optional[str]: 格式化后的日期字符串，如果格式无效则返回None
        """
        try:
            # 尝试解析多种格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
                try:
                    return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return None
        except Exception:
            return None 