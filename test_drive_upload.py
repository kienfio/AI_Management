import os
import logging
from google_drive_uploader import GoogleDriveUploader

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 使用DEBUG级别获取更多信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DriveUploaderTest')

def test_pdf_upload():
    """测试PDF文件上传功能"""
    logger.info("=== 开始PDF上传测试 ===")
    
    # 初始化上传器
    uploader = GoogleDriveUploader()
    
    # 创建测试PDF文件
    test_pdf = "test_upload.pdf"
    with open(test_pdf, 'wb') as f:
        f.write(b"%PDF-1.4\n%Test\n1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n3 0 obj\n<</Type /Page /Parent 2 0 R /Resources <<>> /MediaBox [0 0 200 200] /Contents 4 0 R>>\nendobj\n4 0 obj\n<</Length 44>>\nstream\nBT /F1 12 Tf 72 720 Td (Hello World!) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000110 00000 n\n0000000199 00000 n\ntrailer\n<</Size 5 /Root 1 0 R>>\nstartxref\n299\n%%EOF")
    
    logger.info(f"创建测试PDF文件: {test_pdf} (大小: {os.path.getsize(test_pdf)} bytes)")
    
    try:
        # 测试1: 使用文件路径上传
        logger.info("测试1: 通过文件路径上传")
       result = uploader.upload_receipt(test_pdf, "invoice_pdf", mime_type="application/pdf")
        logger.info(f"测试1结果: {result}")
        
        # 测试2: 使用文件流上传
        logger.info("测试2: 通过文件流上传")
        with open(test_pdf, 'rb') as f:
            result = uploader.upload_receipt(f, "invoice_pdf", mime_type="application/pdf")
            logger.info(f"测试2结果: {result}")
        
        return True
    except Exception as e:
        logger.error(f"上传测试失败: {e}", exc_info=True)
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_pdf):
            os.remove(test_pdf)
            logger.info("已清理测试文件")

def check_environment():
    """检查必要的环境变量"""
    logger.info("=== 环境变量检查 ===")
    
    required_vars = [
        'DRIVE_FOLDER_INVOICE_PDF',
        'GOOGLE_CREDENTIALS_BASE64'  # 或其他凭证变量
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"{var}: 已设置 ({value[:10]}...)")
        else:
            logger.error(f"{var}: 未设置!")
            all_set = False
    
    return all_set

if __name__ == "__main__":
    logger.info("===== Google Drive 上传功能测试 =====")
    
    # 检查环境变量
    if not check_environment():
        logger.error("环境变量检查失败，测试中止")
        exit(1)
    
    # 运行上传测试
    if test_pdf_upload():
        logger.info("===== 测试成功完成 =====")
    else:
        logger.error("===== 测试失败 =====")
