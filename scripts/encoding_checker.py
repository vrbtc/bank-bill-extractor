#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本文件编码检测和转换工具
用于检测 PowerShell、BAT 等脚本文件的编码格式，并提供转换功能
"""

import os
import sys
import json
import chardet
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class EncodingChecker:
    """编码检测和转换工具类"""
    
    # 支持的编码类型
    SUPPORTED_ENCODINGS = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk', 'gb2312', 'big5']
    
    # 文件类型映射
    FILE_TYPE_MAP = {
        '.ps1': 'PowerShell Script',
        '.psm1': 'PowerShell Module',
        '.psd1': 'PowerShell Data File',
        '.bat': 'Batch Script',
        '.cmd': 'Command Script',
        '.psd1': 'PowerShell Data File',
    }
    
    def __init__(self, directory: str):
        """
        初始化工具
        
        Args:
            directory: 要检查的目录路径
        """
        self.directory = Path(directory)
        self.results = []
        self.stats = {
            'total': 0,
            'utf8': 0,
            'utf8_bom': 0,
            'utf16': 0,
            'ansi': 0,
            'other': 0,
            'issues': 0
        }
    
    def detect_encoding(self, file_path: Path) -> Dict:
        """
        检测文件编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含编码信息的字典
        """
        try:
            # 读取文件内容进行检测
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024 * 1024)  # 读取前 1MB
                
            # 使用 chardet 检测编码
            result = chardet.detect(raw_data)
            
            # 检查是否有 BOM
            has_bom = False
            bom_type = None
            
            with open(file_path, 'rb') as f:
                bom = f.read(4)
                
                if bom.startswith(b'\xef\xbb\xbf'):
                    has_bom = True
                    bom_type = 'UTF-8 BOM'
                elif bom.startswith(b'\xff\xfe'):
                    has_bom = True
                    bom_type = 'UTF-16 LE BOM'
                elif bom.startswith(b'\xfe\xff'):
                    has_bom = True
                    bom_type = 'UTF-16 BE BOM'
                elif bom.startswith(b'\x00\x00\xfe\xff'):
                    has_bom = True
                    bom_type = 'UTF-32 BOM'
            
            # 确定编码
            detected_encoding = result['encoding']
            confidence = result['confidence']
            
            # 标准化编码名称
            if detected_encoding:
                detected_encoding = detected_encoding.lower()
                if detected_encoding == 'utf-8' and has_bom:
                    detected_encoding = 'utf-8-sig'
            
            return {
                'encoding': detected_encoding,
                'confidence': confidence,
                'has_bom': has_bom,
                'bom_type': bom_type,
                'error': None
            }
            
        except Exception as e:
            return {
                'encoding': None,
                'confidence': 0,
                'has_bom': False,
                'bom_type': None,
                'error': str(e)
            }
    
    def check_chinese_content(self, file_path: Path) -> bool:
        """
        检查文件是否包含中文字符
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果包含中文，否则 False
        """
        try:
            encodings_to_try = ['utf-8', 'gbk', 'utf-8-sig', 'gb2312']
            
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        # 检查是否包含中文字符
                        for char in content:
                            if '\u4e00' <= char <= '\u9fff':
                                return True
                        return False
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            return False
        except Exception:
            return False
    
    def scan_directory(self) -> List[Dict]:
        """
        扫描目录中的所有脚本文件
        
        Returns:
            检测结果列表
        """
        print(f"\n扫描目录：{self.directory.absolute()}")
        print("=" * 80)
        
        script_files = []
        
        # 查找所有脚本文件
        for ext in ['.ps1', '.psm1', '.psd1', '.bat', '.cmd']:
            script_files.extend(self.directory.rglob(f'*{ext}'))
        
        if not script_files:
            print("未找到任何脚本文件 (.ps1, .psm1, .psd1, .bat, .cmd)")
            return []
        
        print(f"找到 {len(script_files)} 个脚本文件\n")
        
        # 检测每个文件
        for file_path in script_files:
            self.stats['total'] += 1
            
            print(f"检测：{file_path.relative_to(self.directory)}")
            
            # 检测编码
            encoding_info = self.detect_encoding(file_path)
            
            # 检查中文内容
            has_chinese = self.check_chinese_content(file_path)
            
            # 获取文件类型
            file_type = self.FILE_TYPE_MAP.get(file_path.suffix, 'Unknown')
            
            # 判断是否有编码问题
            has_issue = False
            issue_type = None
            
            # BAT/CMD 文件应该使用 UTF-8 with BOM
            if file_path.suffix.lower() in ['.bat', '.cmd']:
                if has_chinese and not encoding_info['has_bom']:
                    has_issue = True
                    issue_type = 'BAT/CMD 含中文但无 BOM'
                    self.stats['issues'] += 1
            
            # PowerShell 文件应该使用 UTF-8
            if file_path.suffix.lower() in ['.ps1', '.psm1', '.psd1']:
                if encoding_info['encoding'] and 'utf' not in encoding_info['encoding']:
                    has_issue = True
                    issue_type = f'PowerShell 文件应使用 UTF-8，检测到：{encoding_info["encoding"]}'
                    self.stats['issues'] += 1
            
            # 更新统计
            if encoding_info['has_bom'] and 'utf-8' in str(encoding_info['encoding']):
                self.stats['utf8_bom'] += 1
            elif encoding_info['encoding'] == 'utf-8':
                self.stats['utf8'] += 1
            elif encoding_info['encoding'] and 'utf-16' in encoding_info['encoding']:
                self.stats['utf16'] += 1
            elif encoding_info['encoding'] in ['gbk', 'gb2312', 'ansi']:
                self.stats['ansi'] += 1
            else:
                self.stats['other'] += 1
            
            # 记录结果
            result = {
                'file': str(file_path.relative_to(self.directory)),
                'type': file_type,
                'encoding': encoding_info['encoding'],
                'confidence': encoding_info['confidence'],
                'has_bom': encoding_info['has_bom'],
                'bom_type': encoding_info['bom_type'],
                'has_chinese': has_chinese,
                'has_issue': has_issue,
                'issue_type': issue_type,
                'error': encoding_info['error']
            }
            
            self.results.append(result)
            
            # 显示结果
            status = "⚠" if has_issue else "✓"
            bom_info = f" ({encoding_info['bom_type']})" if encoding_info['has_bom'] else ""
            chinese_info = " [含中文]" if has_chinese else ""
            
            print(f"  {status} 编码：{encoding_info['encoding']}{bom_info}{chinese_info}")
            if has_issue:
                print(f"     问题：{issue_type}")
            print()
        
        return self.results
    
    def convert_to_utf8_bom(self, file_path: str, output_path: Optional[str] = None) -> bool:
        """
        将文件转换为 UTF-8 with BOM 编码
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径（可选，默认为覆盖原文件）
            
        Returns:
            True 如果转换成功
        """
        try:
            input_path = Path(file_path)
            
            # 尝试多种编码读取
            content = None
            used_encoding = None
            
            for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'ansi']:
                try:
                    with open(input_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        used_encoding = encoding
                        break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if content is None:
                print(f"无法读取文件：{file_path}")
                return False
            
            # 确定输出路径
            if output_path:
                out_path = Path(output_path)
            else:
                out_path = input_path
            
            # 写入 UTF-8 with BOM
            with open(out_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)
            
            print(f"✓ 已转换：{file_path} -> UTF-8 with BOM")
            if used_encoding:
                print(f"  原编码：{used_encoding}")
            
            return True
            
        except Exception as e:
            print(f"✗ 转换失败：{e}")
            return False
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        生成检测报告
        
        Args:
            output_file: 输出文件路径（可选）
            
        Returns:
            报告内容
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = []
        report.append("=" * 80)
        report.append("脚本文件编码检测报告")
        report.append("=" * 80)
        report.append(f"生成时间：{timestamp}")
        report.append(f"检测目录：{self.directory.absolute()}")
        report.append("")
        
        # 统计信息
        report.append("统计信息:")
        report.append(f"  总文件数：{self.stats['total']}")
        report.append(f"  UTF-8 无 BOM: {self.stats['utf8']}")
        report.append(f"  UTF-8 with BOM: {self.stats['utf8_bom']}")
        report.append(f"  UTF-16: {self.stats['utf16']}")
        report.append(f"  ANSI/GBK: {self.stats['ansi']}")
        report.append(f"  其他编码：{self.stats['other']}")
        report.append(f"  发现问题：{self.stats['issues']}")
        report.append("")
        
        # 问题文件列表
        issues = [r for r in self.results if r['has_issue']]
        if issues:
            report.append("问题文件列表:")
            report.append("-" * 80)
            for issue in issues:
                report.append(f"文件：{issue['file']}")
                report.append(f"  类型：{issue['type']}")
                report.append(f"  当前编码：{issue['encoding']}")
                report.append(f"  问题：{issue['issue_type']}")
                report.append("")
        
        # 所有文件详情
        report.append("所有文件详情:")
        report.append("-" * 80)
        for result in self.results:
            status = "⚠" if result['has_issue'] else "✓"
            bom_info = f" ({result['bom_type']})" if result['has_bom'] else ""
            report.append(f"{status} {result['file']}")
            report.append(f"   编码：{result['encoding']}{bom_info}")
            report.append(f"   置信度：{result['confidence']:.2f}")
            report.append(f"   含中文：{'是' if result['has_chinese'] else '否'}")
            if result['has_issue']:
                report.append(f"   问题：{result['issue_type']}")
            report.append("")
        
        report_content = "\n".join(report)
        
        # 保存到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8-sig') as f:
                f.write(report_content)
            print(f"\n报告已保存到：{output_file}")
        
        return report_content


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='脚本文件编码检测和转换工具')
    parser.add_argument('directory', nargs='?', default='.', 
                       help='要检测的目录路径')
    parser.add_argument('-c', '--convert', nargs='+', 
                       help='转换为 UTF-8 with BOM 的文件列表')
    parser.add_argument('-o', '--output', 
                       help='检测报告输出文件路径')
    parser.add_argument('--batch-convert', action='store_true',
                       help='批量转换所有有问题的文件为 UTF-8 with BOM')
    
    args = parser.parse_args()
    
    checker = EncodingChecker(args.directory)
    
    if args.convert:
        # 转换指定文件
        for file_path in args.convert:
            checker.convert_to_utf8_bom(file_path)
    else:
        # 扫描目录
        checker.scan_directory()
        
        # 批量转换
        if args.batch_convert:
            issues = [r for r in checker.results if r['has_issue']]
            if issues:
                print(f"\n开始批量转换 {len(issues)} 个问题文件...")
                for issue in issues:
                    file_path = checker.directory / issue['file']
                    checker.convert_to_utf8_bom(str(file_path))
        
        # 生成报告
        report = checker.generate_report(args.output)
        print(report)
        
        # 如果有问题，返回错误码
        if checker.stats['issues'] > 0:
            sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
