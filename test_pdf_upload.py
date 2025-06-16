#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF上传测试脚本
用于测试上传PDF文件到Google Drive的功能
"""

import os
import io
import logging
from google_drive_uploader import get_drive_uploader

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PDFUploadTest')

def test_pdf_upload():
    """测试PDF文件上传到Google Drive"""
    logger.info("===== 开始PDF上传测试 =====")
    
    # 生成一个简单的PDF文件内容(有效的最小PDF文件内容)
    pdf_content = b"%PDF-1.4\n%Test PDF\n1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n3 0 obj\n<</Type /Page /Parent 2 0 R /Resources <<>> /MediaBox [0 0 200 200] /Contents 4 0 R>>\nendobj\n4 0 obj\n<</Length 44>>\nstream\nBT /F1 12 Tf 72 720 Td (Test Upload PDF) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000110 00000 n\n0000000199 00000 n\ntrailer\n<</Size 5 /Root 1 0 R>>\nstartxref\n299\n%%EOF"
    
    # 创建内存文件对象
    pdf_file = io.BytesIO(pdf_content)
    
    try:
        # 获取上传器实例
        uploader = get_drive_uploader()
        
        # 打印上传器状态
        logger.info(f"上传器文件夹ID: {uploader.FOLDER_IDS}")
        logger.info(f"PDF文件夹ID: {uploader.FOLDER_IDS.get('invoice_pdf')}")
        
        # 测试上传
        logger.info("开始上传PDF文件...")
        result = uploader.upload_receipt(pdf_file, "invoice_pdf", "application/pdf")
        
        # 打印结果
        logger.info(f"上传结果: {result}")
        
        if result:
            logger.info("===== PDF上传测试成功! =====")
            return True
        else:
            logger.error("===== PDF上传测试失败! =====")
            return False
            
    except Exception as e:
        logger.error(f"测试过程中出错: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # 检查环境变量
    logger.info(f"DRIVE_FOLDER_INVOICE_PDF: {os.getenv('DRIVE_FOLDER_INVOICE_PDF', '未设置')}")
    logger.info(f"GOOGLE_CREDENTIALS_BASE64: {'已设置' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else '未设置'}")
    
    # 运行测试
    test_pdf_upload() 