#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮箱客户端模块
负责连接邮箱、登录和获取邮件

关键修复：
1. 阿里云邮箱(imap.aliyun.com)要求 LOGIN 命令的用户名必须用双引号包裹
2. 使用 _command + _command_complete 分步调用（_simple_command 会导致 socket 异常）
3. 添加重试逻辑应对网络不稳定
"""

import imaplib
import email
import socket
import time


class AliyunIMAP4_SSL(imaplib.IMAP4_SSL):
    """修复阿里云邮箱登录问题的 IMAP4_SSL 子类"""
    
    def login(self, user, password):
        """
        重写 login 方法，正确引用用户名。
        使用 _command + _command_complete 分步调用。
        """
        quoted_user = self._quote(user)
        quoted_pass = self._quote(password)
        tag = self._command('LOGIN', quoted_user, quoted_pass)
        typ, dat = self._command_complete('LOGIN', tag)
        if typ != 'OK':
            raise self.error("login error: %s" % dat[-1])
        self.state = 'AUTH'
        return typ, dat


class EmailClient:
    """邮箱客户端，负责连接和获取邮件"""
    
    def __init__(self, server, port, email_address, password):
        self.server = str(server).strip() if server else ''
        self.port = int(str(port).strip()) if port else 993
        self.email_address = str(email_address).strip() if email_address else ''
        self.password = str(password).strip() if password else ''
        self.mail = None
    
    def connect(self):
        """连接邮箱并登录（带重试）"""
        print(f"Connecting to {self.server}:{self.port}...")
        print(f"Email: {self.email_address}")
        print(f"Email length: {len(self.email_address)}, Password length: {len(self.password)}")
        
        if not self.email_address:
            raise Exception("EMAIL_ADDRESS is empty, please check configuration")
        if not self.password:
            raise Exception("EMAIL_PASSWORD is empty, please check configuration")
        
        socket.setdefaulttimeout(60)
        
        max_retries = 3
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"\nAttempt {attempt}/{max_retries}...")
                self.mail = AliyunIMAP4_SSL(self.server, self.port)
                caps = ', '.join(self.mail.capabilities)
                print(f"SSL connected. Capabilities: {caps}")
                
                self.mail.login(self.email_address, self.password)
                print("Login successful!")
                return self
                
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt} failed: {e}")
                if self.mail:
                    try:
                        self.mail.logout()
                    except:
                        pass
                    self.mail = None
                
                if attempt < max_retries:
                    wait = attempt * 5
                    print(f"Waiting {wait}s before retry...")
                    time.sleep(wait)
        
        raise Exception(f"Failed after {max_retries} attempts. Last error: {last_error}")
    
    def fetch_emails(self, limit=50, folder='INBOX'):
        """获取邮件列表"""
        if not self.mail:
            raise Exception("Not connected to email")
        
        typ, data = self.mail.select(folder)
        print(f"SELECT {folder}: {typ}")
        
        status, messages = self.mail.search(None, 'ALL')
        
        if status != 'OK':
            return []
        
        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} emails\n")
        
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
            try:
                self.mail.logout()
            except:
                pass
            self.mail = None
