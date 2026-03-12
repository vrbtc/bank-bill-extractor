#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenClaw 集成接口
提供 REST API 供 OpenClaw 调用

使用方法：
1. 启动服务器：python openclaw_api.py
2. OpenClaw 通过 HTTP 请求获取数据

API 端点：
- GET /api/status - 获取系统状态
- GET /api/bills - 获取最新账单
- GET /api/upcoming - 获取待还款账单
- POST /api/extract - 触发提取
- GET /api/report - 获取文本报告
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import sys


# 导入账单提取器
from bill_extractor_main import BillExtractorWithStorage
from bill_storage import BillStorage


class BillAPIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    def send_json_response(self, data, status=200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.wfile.write(response)
    
    def send_text_response(self, text, status=200):
        """发送文本响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        print(f"收到 GET 请求：{path}")
        
        try:
            if path == '/api/status':
                self.handle_status()
            
            elif path == '/api/bills':
                self.handle_bills()
            
            elif path == '/api/upcoming':
                self.handle_upcoming()
            
            elif path == '/api/report':
                self.handle_report()
            
            elif path == '/api/errors':
                self.handle_errors()
            
            elif path == '/':
                self.handle_help()
            
            else:
                self.send_json_response({
                    'error': 'Not Found',
                    'message': f'未知端点：{path}'
                }, 404)
        
        except Exception as e:
            self.send_json_response({
                'error': str(e),
                'traceback': traceback.format_exc()
            }, 500)
    
    def do_POST(self):
        """处理 POST 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        print(f"收到 POST 请求：{path}")
        
        try:
            if path == '/api/extract':
                self.handle_extract()
            else:
                self.send_json_response({
                    'error': 'Not Found',
                    'message': f'未知端点：{path}'
                }, 404)
        
        except Exception as e:
            self.send_json_response({
                'error': str(e),
                'traceback': traceback.format_exc()
            }, 500)
    
    def handle_help(self):
        """返回 API 帮助信息"""
        help_info = {
            'name': '银行账单 API',
            'version': '1.0',
            'endpoints': {
                'GET /api/status': '获取系统状态',
                'GET /api/bills': '获取最新账单数据',
                'GET /api/upcoming': '获取待还款账单',
                'GET /api/report': '获取文本格式报告',
                'GET /api/errors': '获取错误日志',
                'POST /api/extract': '触发账单提取',
                'GET /': '显示此帮助信息'
            },
            'usage': {
                'curl_examples': [
                    'curl http://localhost:8765/api/status',
                    'curl http://localhost:8765/api/upcoming',
                    'curl -X POST http://localhost:8765/api/extract'
                ]
            }
        }
        self.send_json_response(help_info)
    
    def handle_status(self):
        """获取系统状态"""
        extractor = BillExtractorWithStorage()
        status = extractor.get_status()
        self.send_json_response(status)
    
    def handle_bills(self):
        """获取最新账单数据"""
        storage = BillStorage()
        latest = storage.get_latest_bills()
        if latest:
            self.send_json_response({
                'success': True,
                'data': latest
            })
        else:
            self.send_json_response({
                'success': False,
                'message': '暂无账单数据'
            })
    
    def handle_upcoming(self):
        """获取待还款账单"""
        storage = BillStorage()
        upcoming = storage.get_upcoming_bills()
        
        # 计算总额
        total = sum(
            info['total_amount'] for info in upcoming.values()
            if info['total_amount'] > 0
        )
        
        self.send_json_response({
            'success': True,
            'upcoming_bills': upcoming,
            'total_amount': total,
            'bank_count': len([b for b, i in upcoming.items() if i['total_amount'] > 0])
        })
    
    def handle_report(self):
        """获取文本报告"""
        storage = BillStorage()
        report = generate_text_report(storage)
        self.send_text_response(report)
    
    def handle_errors(self):
        """获取错误日志"""
        if os.path.exists('error_log.json'):
            try:
                with open('error_log.json', 'r', encoding='utf-8') as f:
                    errors = json.load(f)
                self.send_json_response({
                    'success': True,
                    'errors': errors
                })
            except:
                self.send_json_response({
                    'success': False,
                    'message': '读取错误日志失败'
                })
        else:
            self.send_json_response({
                'success': True,
                'errors': []
            })
    
    def handle_extract(self):
        """触发账单提取"""
        print("\n开始执行账单提取...")
        
        try:
            extractor = BillExtractorWithStorage()
            result = extractor.run()
            
            # 如果有错误，尝试发送通知
            if not result['success']:
                self.send_notification(result)
            
            self.send_json_response(result)
        
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            self.send_notification(error_result)
            self.send_json_response(error_result, 500)
    
    def send_notification(self, error_result):
        """发送错误通知（预留接口）"""
        # 这里可以集成各种通知方式
        # 1. 邮件通知
        # 2. 微信通知
        # 3. 钉钉通知
        # 4. Telegram 通知
        # 等等...
        
        print(f"\n❌ 检测到错误，准备发送通知:")
        print(f"错误：{error_result.get('error', 'Unknown')}")
        
        # TODO: 实现具体的通知逻辑
        # 例如：发送邮件、发送微信消息等


def run_server(port=8765):
    """启动 HTTP 服务器"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, BillAPIHandler)
    
    print("="*80)
    print("银行账单 API 服务器")
    print("="*80)
    print(f"服务器地址：http://localhost:{port}")
    print(f"API 文档：http://localhost:{port}/")
    print("="*80)
    print("\n按 Ctrl+C 停止服务器\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        httpd.shutdown()


if __name__ == "__main__":
    import traceback
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # 只运行一次提取
        extractor = BillExtractorWithStorage()
        result = extractor.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 启动 API 服务器
        run_server()
