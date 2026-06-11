#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek API 客户端
用于调用DeepSeek V4 Pro模型
"""

import sys
import os
import json
import requests
from pathlib import Path

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DeepSeekClient:
    """DeepSeek API客户端"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or "sk-0Uj687veHGqP4f6dvTflFtfhAn52hOXuQUJ6A9Zb94DAayT1"
        self.base_url = base_url or "https://spanagent.xyz/v1"
        self.model = model or "deepseek-v4-pro"

    def chat(self, messages, temperature=0.7, max_tokens=4096):
        """发送聊天请求"""
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
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
                proxies={'http': None, 'https': None}  # 禁用代理
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "content": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {})
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def test_connection(self):
        """测试API连接"""
        result = self.chat([{"role": "user", "content": "Hello, this is a test."}])
        if result["success"]:
            print("API连接成功!")
            print(f"响应: {result['content'][:100]}...")
            return True
        else:
            print(f"API连接失败: {result['error']}")
            return False


if __name__ == "__main__":
    client = DeepSeekClient()
    client.test_connection()
