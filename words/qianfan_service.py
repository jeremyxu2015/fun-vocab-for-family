"""
AI 大模型API服务
用于从PDF文本中智能提取单词和释义
支持硅基流动、百度千帆等 OpenAI 兼容 API
"""
import requests
import json
import re
from django.conf import settings


class AIService:
    """AI API封装 (支持 OpenAI 兼容接口)"""

    def __init__(self):
        self.api_key = getattr(settings, 'AI_API_KEY', '')
        self.model = getattr(settings, 'AI_MODEL', 'Qwen/Qwen2.5-7B-Instruct')
        self.base_url = getattr(settings, 'AI_BASE_URL', 'https://api.siliconflow.cn/v1/chat/completions')

    def chat(self, messages, temperature=0.3, max_tokens=4000):
        """
        调用 AI 对话 API (OpenAI 兼容接口)

        Args:
            messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数，0-1
            max_tokens: 最大输出token数

        Returns:
            str: 模型回复内容
        """
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

        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            elif 'error' in result:
                raise Exception(f"API调用错误: {result['error'].get('message', '未知错误')}")
            else:
                raise Exception(f"未知响应格式: {result}")
        except Exception as e:
            raise Exception(f"API调用失败: {str(e)}")

    def _safe_json_loads(self, text):
        """
        多层容错JSON解析
        处理各种AI返回的脏数据
        """
        text = text.strip()
        if not text:
            return []

        # 去掉BOM和控制字符
        text = text.lstrip('\ufeff')
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)

        # 第一层：直接解析
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            # 有些模型会把数组包在对象里
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

        # 第四层：逐行解析（处理每行一个JSON对象的情况）
        objects = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue
            # 去掉行尾逗号
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
            list: 单词列表，格式 [{"word": "...", "definition": "...", "pronunciation": "..."}]
        """
        # 限制文本长度，避免超出API限制
        if len(text) > 8000:
            text = text[:8000] + "..."

        # 优化 prompt：明确要求提取所有单词，用数组格式，不要对象包裹
        prompt = f"""请从以下文本中提取所有英语单词及其中文释义。

要求：
1. 提取文本中所有出现的英语单词，不要遗漏
2. 每个单词包含：word(单词本身)、pronunciation(音标，可选)、definition(中文释义)
3. 如有例句，可包含 example 和 example_translation
4. 最多提取 {max_words} 个单词，请尽量多提取
5. 必须返回 JSON 数组格式，不要返回对象，不要加任何说明文字

返回格式示例：
[
  {{"word": "apple", "pronunciation": "/ˈæpl/", "definition": "n. 苹果", "example": "I eat an apple.", "example_translation": "我吃一个苹果。"}},
  {{"word": "book", "pronunciation": "/bʊk/", "definition": "n. 书；v. 预订"}},
  {{"word": "run", "definition": "v. 跑"}}
]

如果没有找到单词，返回：[]

文本内容：
{text}
"""

        messages = [{"role": "user", "content": prompt}]

        try:
            result = self.chat(messages, temperature=0.3, max_tokens=4000)

            # 使用多层容错解析
            words = self._safe_json_loads(result)

            # 验证格式
            if not isinstance(words, list):
                raise ValueError(f"返回格式错误：不是数组，实际类型: {type(words).__name__}")

            valid_words = []
            for item in words:
                if not isinstance(item, dict):
                    continue

                # 尝试获取单词字段（兼容各种可能的字段名）
                word = None
                for key in ['word', 'Word', '单词', 'wordword', 'en', 'english']:
                    if key in item and item[key]:
                        word = str(item[key]).strip()
                        break

                # 获取释义字段
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

        except Exception as e:
            raise Exception(f"单词提取失败: {str(e)}")


# 创建全局实例
ai_service = AIService()

# 兼容旧代码的别名
qianfan_service = ai_service
