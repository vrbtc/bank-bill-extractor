#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本编码批量修复工具
用于快速修复所有脚本文件的编码问题
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict


class EncodingFixer:
    """编码修复工具类"""
    
    def __init__(self, directory: str, create_backup: bool = True):
        """
        初始化工具
        
        Args:
            directory: 要修复的目录路径
            create_backup: 是否创建备份
        """
        self.directory = Path(directory)
        self.create_backup = create_backup
        self.fixed_files = []
        self.failed_files = []
        self.skipped_files = []
        
    def detect_file_encoding(self, file_path: Path) -> str:
        """
        检测文件编码（简化版）
        
        Args:
            file_path: 文件路径
            
        Returns:
            编码名称
        """
        try:
            with open(file_path, 'rb') as f:
                bom = f.read(4)
                
            # 检查 BOM
            if bom.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
            elif bom.startswith(b'\xff\xfe'):
                return 'utf-16-le'
            elif bom.startswith(b'\xfe\xff'):
                return 'utf-16-be'
            
            # 尝试读取内容判断
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read()
                return 'utf-8'
            except:
                pass
            
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    f.read()
                return 'gbk'
            except:
                pass
            
            return 'unknown'
            
        except Exception as e:
            return f'error: {e}'
    
    def has_chinese_content(self, file_path: Path) -> bool:
        """
        检查文件是否包含中文
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果包含中文
        """
        try:
            for encoding in ['utf-8', 'gbk', 'utf-8-sig']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        for char in content:
                            if '\u4e00' <= char <= '\u9fff':
                                return True
                        return False
                except:
                    continue
            return False
        except:
            return False
    
    def fix_file_encoding(self, file_path: Path) -> bool:
        """
        修复文件编码为 UTF-8 with BOM
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果修复成功
        """
        try:
            # 检测原编码
            original_encoding = self.detect_file_encoding(file_path)
            
            if original_encoding == 'utf-8-sig':
                # 已经是 UTF-8 with BOM，跳过
                return True
            
            # 创建备份
            if self.create_backup:
                backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                shutil.copy2(file_path, backup_path)
                print(f"  已创建备份：{backup_path.name}")
            
            # 尝试多种编码读取
            content = None
            used_encoding = None
            
            for encoding in ['utf-8', 'gbk', 'gb2312', 'ansi']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        used_encoding = encoding
                        break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if content is None:
                print(f"  ✗ 无法读取文件")
                return False
            
            # 写入 UTF-8 with BOM
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)
            
            print(f"  ✓ 已转换：{used_encoding} -> UTF-8 with BOM")
            return True
            
        except Exception as e:
            print(f"  ✗ 失败：{e}")
            return False
    
    def add_chcp_to_batch(self, file_path: Path) -> bool:
        """
        为 BAT 文件添加 chcp 65001
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果添加成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # 检查是否已有 chcp 65001
            first_lines = ''.join(lines[:5])
            if 'chcp 65001' in first_lines:
                print(f"  ✓ 已包含 chcp 65001")
                return True
            
            # 添加 chcp 65001
            new_lines = []
            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.strip().startswith('@echo off'):
                    new_lines.insert(-1, 'chcp 65001 >nul 2>&1\n')
                    break
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(new_lines)
            
            print(f"  ✓ 已添加 chcp 65001")
            return True
            
        except Exception as e:
            print(f"  ✗ 失败：{e}")
            return False
    
    def add_encoding_header_to_powershell(self, file_path: Path) -> bool:
        """
        为 PowerShell 脚本添加编码设置
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果添加成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # 检查是否已有编码设置
            if '[Console]::OutputEncoding' in content:
                print(f"  ✓ 已包含编码设置")
                return True
            
            # 添加编码设置（在 param 块之前或文件开头）
            encoding_line = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n\n"
            
            if 'param(' in content:
                content = content.replace('param(', encoding_line + 'param(', 1)
            else:
                # 在 shebang 或注释之后添加
                lines = content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.startswith('#!') or line.startswith('<#') or line.startswith('#'):
                        insert_pos = i + 1
                    else:
                        break
                
                lines.insert(insert_pos, encoding_line)
                content = '\n'.join(lines)
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)
            
            print(f"  ✓ 已添加编码设置")
            return True
            
        except Exception as e:
            print(f"  ✗ 失败：{e}")
            return False
    
    def scan_and_fix(self) -> Dict:
        """
        扫描并修复所有脚本文件
        
        Returns:
            修复统计信息
        """
        print("\n" + "=" * 80)
        print("脚本编码批量修复工具")
        print(f"工作目录：{self.directory.absolute()}")
        print(f"创建备份：{'是' if self.create_backup else '否'}")
        print("=" * 80)
        
        # 查找所有脚本文件
        script_files = []
        for ext in ['.ps1', '.psm1', '.psd1', '.bat', '.cmd']:
            script_files.extend(self.directory.rglob(f'*{ext}'))
        
        if not script_files:
            print("\n未找到任何脚本文件")
            return {'fixed': 0, 'failed': 0, 'skipped': 0}
        
        print(f"\n找到 {len(script_files)} 个脚本文件\n")
        
        # 处理每个文件
        for file_path in script_files:
            print(f"处理：{file_path.relative_to(self.directory)}")
            
            # 检测是否需要修复
            encoding = self.detect_file_encoding(file_path)
            has_chinese = self.has_chinese_content(file_path)
            
            needs_fix = False
            fix_type = []
            
            # BAT/CMD 文件检查
            if file_path.suffix.lower() in ['.bat', '.cmd']:
                if encoding != 'utf-8-sig':
                    needs_fix = True
                    fix_type.append('编码转换')
                if has_chinese:
                    fix_type.append('添加 chcp 65001')
                    needs_fix = True
            
            # PowerShell 文件检查
            if file_path.suffix.lower() in ['.ps1', '.psm1', '.psd1']:
                if encoding not in ['utf-8', 'utf-8-sig']:
                    needs_fix = True
                    fix_type.append('编码转换')
                else:
                    # PowerShell 文件即使编码正确也添加编码设置
                    fix_type.append('添加编码设置')
                    needs_fix = True
            
            if not needs_fix:
                print(f"  ✓ 无需修复")
                self.skipped_files.append(str(file_path))
                print()
                continue
            
            print(f"  需要：{', '.join(fix_type)}")
            
            # 执行修复
            success = True
            
            if '编码转换' in fix_type:
                if not self.fix_file_encoding(file_path):
                    success = False
            
            if '添加 chcp 65001' in fix_type and file_path.suffix.lower() in ['.bat', '.cmd']:
                if not self.add_chcp_to_batch(file_path):
                    success = False
            
            if '添加编码设置' in fix_type and file_path.suffix.lower() in ['.ps1', '.psm1', '.psd1']:
                if not self.add_encoding_header_to_powershell(file_path):
                    success = False
            
            if success:
                self.fixed_files.append(str(file_path))
                print(f"  ✓ 修复完成")
            else:
                self.failed_files.append(str(file_path))
                print(f"  ✗ 修复失败")
            
            print()
        
        # 汇总结果
        print("=" * 80)
        print("修复结果汇总")
        print("=" * 80)
        print(f"成功修复：{len(self.fixed_files)} 个文件")
        print(f"修复失败：{len(self.failed_files)} 个文件")
        print(f"跳过：{len(self.skipped_files)} 个文件")
        
        if self.failed_files:
            print("\n失败文件列表:")
            for f in self.failed_files:
                print(f"  - {f}")
        
        if self.create_backup and (self.fixed_files or self.failed_files):
            print("\n备份文件位置：原文件目录下的 .bak 文件")
            print("确认修复成功后可手动删除备份文件")
        
        print()
        
        return {
            'fixed': len(self.fixed_files),
            'failed': len(self.failed_files),
            'skipped': len(self.skipped_files)
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='脚本编码批量修复工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 修复当前目录（创建备份）
  python fix_encodings.py
  
  # 修复指定目录（不创建备份）
  python fix_encodings.py /path/to/scripts --no-backup
  
  # 仅检测不修复
  python fix_encodings.py /path/to/scripts --dry-run
        """
    )
    
    parser.add_argument('directory', nargs='?', default='.',
                       help='要修复的目录路径（默认：当前目录）')
    parser.add_argument('--no-backup', action='store_true',
                       help='不创建备份文件')
    parser.add_argument('--dry-run', action='store_true',
                       help='仅检测，不实际修复')
    
    args = parser.parse_args()
    
    directory = Path(args.directory).absolute()
    
    if not directory.exists():
        print(f"错误：目录不存在：{directory}")
        sys.exit(1)
    
    if args.dry_run:
        # 仅检测模式
        print("\n" + "=" * 80)
        print("检测模式（不实际修复）")
        print("=" * 80)
        
        from encoding_checker import EncodingChecker
        checker = EncodingChecker(str(directory))
        checker.scan_directory()
        checker.generate_report()
        
    else:
        # 修复模式
        fixer = EncodingFixer(str(directory), create_backup=not args.no_backup)
        stats = fixer.scan_and_fix()
        
        # 退出码
        if stats['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == '__main__':
    main()
