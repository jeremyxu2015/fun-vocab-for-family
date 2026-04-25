"""
PDF处理服务
用于从PDF文件中提取文本内容
"""
import os
import tempfile
from django.core.files.uploadedfile import UploadedFile


def extract_text_from_pdf(pdf_file):
    """
    从PDF文件中提取文本
    
    Args:
        pdf_file: Django UploadedFile对象或文件路径
    
    Returns:
        str: 提取的文本内容
    """
    # 尝试使用PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF
        
        # 如果是UploadedFile，先保存到临时文件
        if isinstance(pdf_file, UploadedFile):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in pdf_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            pdf_file = tmp_path
        else:
            tmp_path = None
        
        try:
            doc = fitz.open(pdf_file)
            text_parts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"=== 第{page_num + 1}页 ===\n{text}")
            
            doc.close()
            return "\n\n".join(text_parts)
        finally:
            # 清理临时文件
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except ImportError:
        pass
    
    # 尝试使用pdfplumber
    try:
        import pdfplumber
        
        if isinstance(pdf_file, UploadedFile):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in pdf_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            pdf_file = tmp_path
        else:
            tmp_path = None
        
        try:
            text_parts = []
            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(f"=== 第{i + 1}页 ===\n{text}")
            
            return "\n\n".join(text_parts)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except ImportError:
        pass
    
    # 尝试使用PyPDF2
    try:
        from PyPDF2 import PdfReader
        
        if isinstance(pdf_file, UploadedFile):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in pdf_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            pdf_file = tmp_path
        else:
            tmp_path = None
        
        try:
            reader = PdfReader(pdf_file)
            text_parts = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"=== 第{i + 1}页 ===\n{text}")
            
            return "\n\n".join(text_parts)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except ImportError:
        raise Exception(
            "PDF处理库未安装。请安装以下任一库：\n"
            "pip install PyMuPDF  # 推荐，效果最好\n"
            "pip install pdfplumber\n"
            "pip install PyPDF2"
        )


def process_pdf_and_extract_words(pdf_file, max_words=100):
    """
    处理PDF文件并提取单词
    
    Args:
        pdf_file: 上传的PDF文件
        max_words: 最大提取单词数
    
    Returns:
        tuple: (提取的单词列表, 错误信息)
    """
    from .qianfan_service import qianfan_service
    
    try:
        # 1. 从PDF提取文本
        text = extract_text_from_pdf(pdf_file)
        
        if not text or not text.strip():
            return [], "PDF文件为空或无法读取文本内容"
        
        # 2. 使用千帆API提取单词
        words = qianfan_service.extract_words_from_text(text, max_words)
        
        return words, None
        
    except Exception as e:
        return [], str(e)
