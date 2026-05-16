"""
Kimi AI API服务
用于从PDF文本中智能提取单词和释义

官方文档：https://www.kimi.com/code/docs/

Kimi Code API 端点（OpenAI兼容）：
    https://api.kimi.com/coding/v1

注意：Kimi Code 平台（api.kimi.com）和 Moonshot 开放平台（api.moonshot.cn）
是两个完全独立的账号体系，API Key 互不通用。

在 settings.py 中配置：
    KIMI_API_KEY = "sk-kimi-xxxxxxxx"   # 在 https://www.kimi.com/code/console 创建
    KIMI_BASE_URL = "https://api.kimi.com/coding/v1"
    KIMI_MODEL = "kimi-for-coding"       # 固定模型ID，后端自动升级
"""
import requests
import json
import re
from django.conf import settings


class KimiService:
    """Kimi Code API封装（OpenAI兼容格式）"""

    def __init__(self):
        self.api_key = settings.KIMI_API_KEY
        # Kimi Code API 官方端点
        self.base_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.kimi.com/coding/v1')
        # 确保 base_url 不以 /chat/completions 结尾
        if self.base_url.endswith('/chat/completions'):
            self.base_url = self.base_url[:-len('/chat/completions')]
        # kimi-for-coding 是固定模型ID
        self.model = getattr(settings, 'KIMI_MODEL', 'kimi-for-coding')

    def chat(self, messages, temperature=0.3, max_tokens=4000, response_format=None):
        """
        调用Kimi Code API

        Args:
            messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数。
                         注意：kimi-for-coding 对 temperature 有限制，
                         如果报错 "invalid temperature"，请改为 0.6 或 1.0 [^6^]
            max_tokens: 最大输出token数
            response_format: 强制JSON输出格式 {"type": "json_object"}

        Returns:
            str: 模型回复内容
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # 尝试使用 response_format 强制JSON输出（如果平台支持）
        if response_format:
            payload["response_format"] = response_format

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                msg = result['choices'][0]['message']
                return msg.get('content', '')
            elif 'error' in result:
                err_msg = result['error'].get('message', '未知错误')
                # 检测 temperature 限制错误并给出明确提示
                if 'temperature' in err_msg.lower() or 'invalid temperature' in err_msg.lower():
                    err_msg += (
                        " [提示：Kimi Code 的 kimi-for-coding 模型对 temperature 有限制，"
                        "建议在 settings.py 中设置 KIMI_TEMPERATURE = 0.6 或 1.0]"
                    )
                raise Exception(f"API错误: {err_msg}")
            else:
                raise Exception(f"未知响应格式: {result}")
        except requests.Timeout:
            raise Exception("API请求超时，请稍后重试")
        except Exception as e:
            raise Exception(f"API调用失败: {str(e)}")

    def _safe_json_loads(self, text):
        """多层容错JSON解析"""
        text = text.strip()
        if not text:
            return []

        text = text.lstrip('\ufeff')
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)

        # 第一层：直接解析
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            for key in ['words', 'data', 'result', 'list', 'items']:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data] if isinstance(data, dict) else []
        except (json.JSONDecodeError, ValueError):
            pass

        # 第二层：去掉markdown代码块标记后再解析
        cleaned = text
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            for key in ['words', 'data', 'result', 'list', 'items']:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data] if isinstance(data, dict) else []
        except (json.JSONDecodeError, ValueError):
            pass

        # 第三层：用正则提取JSON数组 [ ... ]
        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            try:
                data = json.loads(array_match.group())
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, ValueError):
                pass

        # 第四层：逐行解析
        objects = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue
            line = line.rstrip(',')
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    objects.append(obj)
            except (json.JSONDecodeError, ValueError):
                continue
        return objects

    def extract_words_from_text(self, text, max_words=100):
        """
        从文本中提取单词和释义

        Args:
            text: PDF提取的文本内容
            max_words: 最大提取单词数

        Returns:
            list: 单词列表
        """
        if len(text) > 6000:
            text = text[:6000] + "..."

        prompt = f"""请从以下文本中提取英语单词及其中文释义。要求：
1. 只提取英语单词，忽略纯中文内容
2. 每个单词包含：单词本身、音标（如果有）、中文释义
3. 如果文本中有例句，可以提取例句和翻译
4. 最多提取{max_words}个单词
5. 必须返回JSON数组格式，不要包含其他说明文字

文本内容：
{text}

请严格按照以下JSON格式返回：
[
  {{"word": "apple", "pronunciation": "/ˈæpl/", "definition": "n. 苹果", "example": "I eat an apple.", "example_translation": "我吃一个苹果。"}},
  {{"word": "book", "pronunciation": "/bʊk/", "definition": "n. 书；v. 预订"}}
]

如果没有找到单词，返回空数组：[]
"""

        messages = [{"role": "user", "content": prompt}]

        try:
            # 读取可选的 temperature 配置（处理 kimi-for-coding 的限制）
            temp = getattr(settings, 'KIMI_TEMPERATURE', 0.3)

            result = self.chat(
                messages, 
                temperature=temp, 
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            words = self._safe_json_loads(result)

            if not isinstance(words, list):
                raise ValueError("返回格式错误：不是数组")

            valid_words = []
            for item in words:
                if not isinstance(item, dict):
                    continue

                word = None
                for key in ['word', 'Word', '单词', 'wordword', 'en', 'english']:
                    if key in item and item[key]:
                        word = str(item[key]).strip()
                        break

                definition = None
                for key in ['definition', 'Definition', '释义', 'meaning', 'meaning_cn', 'translation', 'translate']:
                    if key in item and item[key]:
                        definition = str(item[key]).strip()
                        break

                if word and definition:
                    valid_words.append({
                        'word': word,
                        'pronunciation': str(item.get('pronunciation', item.get('phonetic', ''))).strip(),
                        'definition': definition,
                        'example': str(item.get('example', item.get('sentence', ''))).strip(),
                        'example_translation': str(item.get('example_translation', item.get('sentence_translation', ''))).strip()
                    })

            return valid_words

        except json.JSONDecodeError as e:
            raise Exception(f"解析AI返回结果失败: {str(e)}")
        except Exception as e:
            raise Exception(f"单词提取失败: {str(e)}")


# 创建全局实例
kimi_service = KimiService()
