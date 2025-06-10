import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

class DataManager:
    """数据管理类，用于保存和读取系统配置数据"""
    
    def __init__(self, data_dir="data"):
        """初始化数据管理器"""
        self.data_dir = data_dir
        self.persons_file = os.path.join(data_dir, "persons.json")
        self.agents_file = os.path.join(data_dir, "agents.json")
        self.suppliers_file = os.path.join(data_dir, "suppliers.json")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化数据存储
        self._init_data_files()
    
    def _init_data_files(self):
        """初始化数据文件"""
        for file_path in [self.persons_file, self.agents_file, self.suppliers_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
    
    def _read_data(self, file_path: str) -> List[Dict[str, Any]]:
        """从文件读取数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"读取数据文件出错 {file_path}: {e}")
            return []
    
    def _save_data(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        """保存数据到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存数据到文件出错 {file_path}: {e}")
            return False
    
    def add_person(self, name: str) -> bool:
        """添加负责人"""
        persons = self._read_data(self.persons_file)
        
        # 检查是否已存在同名负责人
        for person in persons:
            if person['name'].lower() == name.lower():
                logger.warning(f"负责人 {name} 已存在")
                return False
        
        # 添加新负责人
        person_data = {
            'id': self._generate_id(),
            'name': name,
            'created_at': datetime.now().isoformat()
        }
        persons.append(person_data)
        
        return self._save_data(self.persons_file, persons)
    
    def add_agent(self, name: str, ic: str) -> bool:
        """添加代理商"""
        agents = self._read_data(self.agents_file)
        
        # 检查是否已存在同名或同IC的代理商
        for agent in agents:
            if agent['name'].lower() == name.lower() or agent['ic'].lower() == ic.lower():
                logger.warning(f"代理商 {name} 或IC {ic} 已存在")
                return False
        
        # 添加新代理商
        agent_data = {
            'id': self._generate_id(),
            'name': name,
            'ic': ic,
            'created_at': datetime.now().isoformat()
        }
        agents.append(agent_data)
        
        return self._save_data(self.agents_file, agents)
    
    def add_supplier(self, category: str, product: str) -> bool:
        """添加供应商"""
        suppliers = self._read_data(self.suppliers_file)
        
        # 添加新供应商
        supplier_data = {
            'id': self._generate_id(),
            'category': category,
            'product': product,
            'created_at': datetime.now().isoformat()
        }
        suppliers.append(supplier_data)
        
        return self._save_data(self.suppliers_file, suppliers)
    
    def get_persons(self) -> List[Dict[str, Any]]:
        """获取所有负责人"""
        return self._read_data(self.persons_file)
    
    def get_agents(self) -> List[Dict[str, Any]]:
        """获取所有代理商"""
        return self._read_data(self.agents_file)
    
    def get_suppliers(self) -> List[Dict[str, Any]]:
        """获取所有供应商"""
        return self._read_data(self.suppliers_file)
    
    def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        """获取特定负责人"""
        persons = self._read_data(self.persons_file)
        for person in persons:
            if person['id'] == person_id:
                return person
        return None
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取特定代理商"""
        agents = self._read_data(self.agents_file)
        for agent in agents:
            if agent['id'] == agent_id:
                return agent
        return None
    
    def get_supplier(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """获取特定供应商"""
        suppliers = self._read_data(self.suppliers_file)
        for supplier in suppliers:
            if supplier['id'] == supplier_id:
                return supplier
        return None
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import uuid
        return str(uuid.uuid4())

# 创建全局数据管理器实例
try:
    data_manager = DataManager()
except Exception as e:
    logger.error(f"初始化数据管理器时出错: {e}")
    data_manager = None 