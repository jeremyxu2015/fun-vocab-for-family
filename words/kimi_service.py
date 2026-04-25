"""
Kimi AI API服务
用于从PDF文本中智能提取单词和释义
"""
import requests
import json
from django.conf import settings
from django.core.cache import cache


class KimiService:
    """Kimi API封装（兼容OpenAI格式）"""
    
    def __init__(self):
        self.api_key = settings.KIMI_API_KEY
        self.base_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.kimi.com/coding/v1')
        self.model = getattr(settings, 'KIMI_MODEL', 'kimi-for-coding')
    
    def chat(self, messages, temperature=0.7, max_tokens=2000):
        """
        调用Kimi对话API
        
        Args:
            messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数，0-1
            max_tokens: 最大输出token数
        
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
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            elif 'error' in result:
                raise Exception(f"API错误: {result['error'].get('message', '未知错误')}")
            else:
                raise Exception(f"未知响应格式: {result}")
        except requests.Timeout:
            raise Exception("API请求超时，请稍后重试")
        except Exception as e:
            raise Exception(f"API调用失败: {str(e)}")
    
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
        if len(text) > 6000:
            text = text[:6000] + "..."
        
        prompt = f"""请从以下文本中提取英语单词及其中文释义。要求：
1. 只提取英语单词，忽略纯中文内容
2. 每个单词包含：单词本身、音标（如果有）、中文释义
3. 如果文本中有例句，可以提取例句和翻译
4. 最多提取{max_words}个单词
5. 返回JSON数组格式，不要包含其他说明文字

文本内容：
{text}

请严格按照以下JSON格式返回，不要包含```json标记：
[
  {{"word": "apple", "pronunciation": "/ˈæpl/", "definition": "n. 苹果", "example": "I eat an apple.", "example_translation": "我吃一个苹果。"}},
  {{"word": "book", "pronunciation": "/bʊk/", "definition": "n. 书；v. 预订"}}
]

如果没有找到单词，返回空数组：[]
"""
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = self.chat(messages, temperature=0.3, max_tokens=4000)
            
            # 清理返回结果，移除可能的markdown标记
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            # 解析JSON
            words = json.loads(result)
            
            # 验证格式
            if not isinstance(words, list):
                raise ValueError("返回格式错误：不是数组")
            
            valid_words = []
            for item in words:
                if isinstance(item, dict) and 'word' in item and 'definition' in item:
                    valid_words.append({
                        'word': item['word'].strip(),
                        'pronunciation': item.get('pronunciation', '').strip(),
                        'definition': item['definition'].strip(),
                        'example': item.get('example', '').strip(),
                        'example_translation': item.get('example_translation', '').strip()
                    })
            
            return valid_words
            
        except json.JSONDecodeError as e:
            raise Exception(f"解析AI返回结果失败: {str(e)}")
        except Exception as e:
            raise Exception(f"单词提取失败: {str(e)}")


# 创建全局实例
kimi_service = KimiService()
