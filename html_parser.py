#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTML 解析模块
负责 HTML 清理和 Markdown 转换
"""

import re
import html2text
from bs4 import BeautifulSoup


class HTMLParser:
    """HTML 解析器，负责 HTML 清理和转换"""
    
    def __init__(self):
        self.converter = html2text.HTML2Text()
        self.converter.ignore_links = False
        self.converter.ignore_images = True
        self.converter.body_width = 0
    
    def clean_html(self, html_content):
        """
        清理 HTML，移除无用标签
        
        Args:
            html_content: HTML 内容
            
        Returns:
            清理后的 HTML 字符串
        """
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'link']):
            tag.decompose()
        
        return str(soup)
    
    def html_to_markdown(self, html_content):
        """
        将 HTML 转换为 Markdown
        
        Args:
            html_content: HTML 内容
            
        Returns:
            Markdown 格式的字符串
        """
        if not html_content:
            return ""
        
        cleaned_html = self.clean_html(html_content)
        markdown = self.converter.handle(cleaned_html)
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown
