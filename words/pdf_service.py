"""
PDF处理服务
用于从PDF文件中提取文本内容，并调用AI服务提取单词
支持后端切换：硅基流动 / Kimi
"""
import os
import tempfile
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings


def extract_text_from_pdf(pdf_file):
    """
    从PDF文件中提取文本

    Args:
        pdf_file: Django UploadedFile对象或文件路径

    Returns:
        str: 提取的文本内容
    """
    # 如果是UploadedFile，先保存到临时文件
    tmp_path = None
    if isinstance(pdf_file, UploadedFile):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            for chunk in pdf_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        pdf_file = tmp_path

    def cleanup():
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    text_parts = []

    # 尝试使用PyMuPDF (fitz) - 推荐，效果最好
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"=== 第{page_num + 1}页 ===\n{text}")
        doc.close()
        cleanup()
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        cleanup()
        raise

    # 尝试使用pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"=== 第{i + 1}页 ===\n{text}")
        cleanup()
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        cleanup()
        raise

    # 尝试使用PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_file)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(f"=== 第{i + 1}页 ===\n{text}")
        cleanup()
        return "\n\n".join(text_parts)
    except ImportError:
        cleanup()
        raise Exception(
            "PDF处理库未安装。请安装以下任一库：\n"
            "pip install PyMuPDF  # 推荐，效果最好\n"
            "pip install pdfplumber\n"
            "pip install PyPDF2"
        )
    except Exception:
        cleanup()
        raise


def _get_ai_service():
    """
    根据 settings.AI_SERVICE_BACKEND 选择AI服务

    settings.py 配置示例：

    # 使用硅基流动（默认）
    AI_SERVICE_BACKEND = 'siliconflow'   # 或 'qianfan'
    AI_API_KEY = "sk-xxxxxxxx"
    AI_BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"
    AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    # 使用 Kimi
    AI_SERVICE_BACKEND = 'kimi'
    KIMI_API_KEY = "sk-xxxxxxxx"
    KIMI_BASE_URL = "https://api.moonshot.cn/v1"   # 通用端点，推荐
    KIMI_MODEL = "kimi-k2.5"
    """
    backend = getattr(settings, 'AI_SERVICE_BACKEND', 'siliconflow').lower()

    if backend in ('kimi', 'moonshot'):
        from .kimi_service import kimi_service
        return kimi_service
    else:
        # 默认使用硅基流动/通用服务
        from .qianfan_service import qianfan_service
        return qianfan_service


def process_pdf_and_extract_words(pdf_file, max_words=100):
    """
    处理PDF文件并提取单词

    Args:
        pdf_file: 上传的PDF文件
        max_words: 最大提取单词数

    Returns:
        tuple: (提取的单词列表, 错误信息)
    """
    try:
        # 1. 从PDF提取文本
        text = extract_text_from_pdf(pdf_file)

        if not text or not text.strip():
            return [], "PDF文件为空或无法读取文本内容"

        # 2. 根据配置选择AI服务并提取单词
        ai_service = _get_ai_service()
        words = ai_service.extract_words_from_text(text, max_words)

        return words, None

    except Exception as e:
        return [], str(e)
