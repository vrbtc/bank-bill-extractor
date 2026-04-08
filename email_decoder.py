#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮件解码模块
负责处理 MIME 编码和 HTML 内容解码
"""

import email
from email.header import decode_header


class EmailDecoder:
    """邮件解码器，负责 MIME 和 HTML 解码"""
    
    @staticmethod
    def decode_mime_words(s):
        """
        解码 MIME 编码的文本
        
        Args:
            s: MIME 编码的字符串
            
        Returns:
            解码后的字符串
        """
        if not s:
            return ""
        
        decoded = ""
        for part, encoding in decode_header(s):
            if isinstance(part, bytes):
                try:
                    decoded += part.decode(encoding if encoding else 'utf-8', errors='ignore')
                except:
                    decoded += part.decode('utf-8', errors='ignore')
            else:
                decoded += part
        return decoded
    
    @staticmethod
    def decode_html_content(part):
        """
        处理不同编码的 HTML 内容
        
        Args:
            part: 邮件部分对象
            
        Returns:
            解码后的 HTML 字符串
        """
        html_body = ""
        try:
            charset = part.get_content_charset() or 'utf-8'
            if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
            else:
                html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
        except:
            try:
                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
        return html_body
