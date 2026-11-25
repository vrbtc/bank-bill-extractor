#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮箱客户端模块
负责连接邮箱、登录和获取邮件

关键修复：
1. 阿里云邮箱(imap.aliyun.com)要求 LOGIN 命令的用户名必须用双引号包裹
2. 使用 _command + _command_complete 分步调用（_simple_command 会导致 socket 异常）
3. 添加重试逻辑应对网络不稳定
4. 163 邮箱(imap.163.com)要求 LOGIN 成功后、SELECT 前发送 IMAP ID 命令，
   否则 SELECT 报 "Unsafe Login"（2026-11-25 实测验证）
"""

import imaplib
import email
import socket
import time

# 允许通过 imaplib 发送 ID 扩展命令（RFC 297）
if 'ID' not in imaplib.Commands:
    imaplib.Commands['ID'] = ('AUTH', 'SELECTED', 'NONAUTH')


def _make_id_command(args):
    """构造 IMAP ID 命令参数字符串：("name" "value" ...) 形式。"""
    return '(' + ' '.join('"%s"' % x for x in args) + ')'


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


class NeteaseIMAP4_SSL(imaplib.IMAP4_SSL):
    """163/126 网易邮箱专用 IMAP4_SSL 子类。

    关键坑：网易服务器要求客户端在 LOGIN 成功后、执行 SELECT/SEARCH 等
    命令前先发送 ID 命令表明客户端身份，否则一律拒绝：
        NO [SELECT Unsafe Login. Please contact kefu@188.com for help]
    已验证参数（2026-11-25 实测网易 163 邮箱）：
        ('name', 'Outlook', 'version', '16.0.0',
         'vendor', 'Microsoft', 'contact', <邮箱地址>)
    """

    def login(self, user, password):
        typ, dat = super().login(user, password)
        if typ == 'OK':
            args = ('name', 'Outlook', 'version', '16.0.0',
                    'vendor', 'Microsoft', 'contact', user)
            cmd = _make_id_command(args)
            typ2, dat2 = self._simple_command('ID', cmd)
            if typ2 != 'OK':
                raise self.error("IMAP ID command failed: %s" % (dat2,))
        return typ, dat


class EmailClient:
    """邮箱客户端，负责连接和获取邮件"""

    def __init__(self, server, port, email_address, password):
        self.server = str(server).strip() if server else ''
        self.port = int(str(port).strip()) if port else 993
        self.email_address = str(email_address).strip() if email_address else ''
        self.password = str(password).strip() if password else ''
        self.mail = None

    def _get_imap_class(self):
        """按服务器域名选择 IMAP 子类（网易需 ID 命令，阿里云需引号 LOGIN）。"""
        server = self.server.lower()
        if '163.com' in server or '126.com' in server or 'netease' in server:
            return NeteaseIMAP4_SSL
        return AliyunIMAP4_SSL
    
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
                imap_cls = self._get_imap_class()
                self.mail = imap_cls(self.server, self.port)
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
    
    def fetch_emails(self, limit=100, folder='INBOX'):
        """获取邮件列表

        P0-6：limit 默认 50 → 100。50 封窗口会把跨月账单（如 7 月与 8 月
        的周期邮件）截掉，与 -3 天宽限形成「双重淘汰」导致漏单；
        100 封可覆盖两个月的邮件量（实测两邮箱总量均 < 100）。
        """
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
