#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮箱客户端模块
负责连接邮箱、登录和获取邮件
"""

import imaplib
import email


class EmailClient:
    """邮箱客户端，负责连接和获取邮件"""
    
    def __init__(self, server, port, email_address, password):
        """
        初始化邮箱客户端
        
        Args:
            server: IMAP 服务器地址
            port: IMAP 端口
            email_address: 邮箱地址
            password: 密码
        """
        self.server = server
        self.port = port
        self.email_address = email_address
        self.password = password
        self.mail = None
    
    def connect(self):
        """
        连接邮箱
        
        Returns:
            self
        """
        print("连接邮箱...")
        self.mail = imaplib.IMAP4_SSL(self.server, self.port)
        self.mail.login(self.email_address, self.password)
        print("登录成功！\n")
        return self
    
    def fetch_emails(self, limit=50, folder='INBOX'):
        """
        获取邮件列表
        
        Args:
            limit: 获取邮件数量限制
            folder: 邮箱文件夹
            
        Returns:
            邮件对象列表
        """
        if not self.mail:
            raise Exception("未连接到邮箱")
        
        self.mail.select(folder)
        status, messages = self.mail.search(None, 'ALL')
        
        if status != 'OK':
            return []
        
        email_ids = messages[0].split()
        print(f"共找到 {len(email_ids)} 封邮件\n")
        
        emails_to_process = email_ids[-limit:]
        emails = []
        
        for idx, email_id in enumerate(reversed(emails_to_process), 1):
            status, msg_data = self.mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    emails.append(email.message_from_bytes(response_part[1]))
        
        return emails
    
    def disconnect(self):
        """断开连接"""
        if self.mail:
            self.mail.logout()
            self.mail = None
