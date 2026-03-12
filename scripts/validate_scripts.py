#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本文件编码和转义字符检查工具
用于 CI/CD 流程或发布前的自动化检查
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple


class ScriptValidator:
    """脚本验证器类"""
    
    def __init__(self, directory: str):
        """
        初始化验证器
        
        Args:
            directory: 要检查的目录路径
        """
        self.directory = Path(directory)
        self.errors = []
        self.warnings = []
        self.passed = []
        
    def check_encoding(self) -> bool:
        """
        检查所有脚本文件的编码
        
        Returns:
            True 如果所有文件编码正确
        """
        print("\n" + "=" * 80)
        print("检查 1: 文件编码检测")
        print("=" * 80)
        
        try:
            # 调用编码检测工具（在 scripts 目录中）
            checker_script = self.directory / 'scripts' / 'encoding_checker.py'
            
            result = subprocess.run(
                [sys.executable, str(checker_script), str(self.directory)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.directory)
            )
            
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            
            # 如果返回码不为 0，表示有问题文件
            if result.returncode != 0:
                self.errors.append("编码检测发现有问题文件")
                return False
            else:
                self.passed.append("所有文件编码正确")
                return True
                
        except subprocess.TimeoutExpired:
            self.errors.append("编码检测超时")
            return False
        except Exception as e:
            self.errors.append(f"编码检测失败：{e}")
            return False
    
    def check_powershell_escapes(self) -> bool:
        """
        检查 PowerShell 脚本的转义字符
        
        Returns:
            True 如果所有测试通过
        """
        print("\n" + "=" * 80)
        print("检查 2: PowerShell 转义字符测试")
        print("=" * 80)
        
        # 在 scripts 子目录中查找
        ps_script = self.directory / 'scripts' / 'test_powershell_escape.ps1'
        
        if not ps_script.exists():
            # 尝试在根目录查找
            ps_script = self.directory / 'test_powershell_escape.ps1'
        
        if not ps_script.exists():
            self.warnings.append("PowerShell 转义测试脚本不存在")
            return True
        
        try:
            # 尝试使用 pwsh 或 powershell
            for pwsh_cmd in ['pwsh', 'powershell']:
                try:
                    result = subprocess.run(
                        [pwsh_cmd, '-ExecutionPolicy', 'Bypass', '-File', str(ps_script)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        encoding='utf-8',
                        cwd=str(self.directory)
                    )
                    
                    print(result.stdout)
                    
                    if result.returncode == 0:
                        self.passed.append("PowerShell 转义测试通过")
                        return True
                    else:
                        self.errors.append("PowerShell 转义测试失败")
                        print(result.stderr)
                        return False
                        
                except FileNotFoundError:
                    continue
            
            self.warnings.append("未找到 PowerShell，跳过转义测试")
            return True
            
        except subprocess.TimeoutExpired:
            self.errors.append("PowerShell 测试超时")
            return False
        except Exception as e:
            self.errors.append(f"PowerShell 测试失败：{e}")
            return False
    
    def check_batch_chinese(self) -> bool:
        """
        检查 BAT 文件的中文字符显示
        
        Returns:
            True 如果所有测试通过
        """
        print("\n" + "=" * 80)
        print("检查 3: BAT 文件中文字符测试")
        print("=" * 80)
        
        # 在 scripts 子目录中查找
        bat_script = self.directory / 'scripts' / 'test_batch_chinese.bat'
        
        if not bat_script.exists():
            # 尝试在根目录查找
            bat_script = self.directory / 'test_batch_chinese.bat'
        
        if not bat_script.exists():
            self.warnings.append("BAT 中文测试脚本不存在")
            return True
        
        try:
            # 使用 PowerShell 运行 BAT 文件
            result = subprocess.run(
                ['powershell', '-Command', f'& {{ . "{bat_script}" }}'],
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                cwd=str(self.directory)
            )
            
            print(result.stdout)
            
            if result.returncode == 0:
                self.passed.append("BAT 中文测试通过")
                return True
            else:
                self.errors.append("BAT 中文测试失败")
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.errors.append("BAT 测试超时")
            return False
        except Exception as e:
            self.errors.append(f"BAT 测试失败：{e}")
            return False
    
    def check_gitattributes(self) -> bool:
        """
        检查 .gitattributes 文件是否正确配置
        
        Returns:
            True 如果配置正确
        """
        print("\n" + "=" * 80)
        print("检查 4: Git 编码配置检查")
        print("=" * 80)
        
        gitattributes = self.directory / '.gitattributes'
        
        if not gitattributes.exists():
            self.warnings.append(".gitattributes 文件不存在")
            return True
        
        try:
            with open(gitattributes, 'r', encoding='utf-8') as f:
                content = f.read()
            
            required_patterns = [
                '*.ps1',
                '*.bat',
                'utf-8',
                'UTF-8'
            ]
            
            missing = []
            for pattern in required_patterns:
                if pattern not in content:
                    missing.append(pattern)
            
            if missing:
                self.warnings.append(f".gitattributes 缺少配置：{', '.join(missing)}")
                return True  # 只是警告，不阻止
            else:
                self.passed.append(".gitattributes 配置正确")
                return True
                
        except Exception as e:
            self.errors.append(f"读取.gitattributes 失败：{e}")
            return False
    
    def check_script_headers(self) -> bool:
        """
        检查脚本文件的头部注释
        
        Returns:
            True 如果所有脚本都有适当的头部
        """
        print("\n" + "=" * 80)
        print("检查 5: 脚本头部注释检查")
        print("=" * 80)
        
        issues = []
        
        # 检查 PowerShell 脚本
        for ps_file in self.directory.rglob('*.ps1'):
            try:
                with open(ps_file, 'r', encoding='utf-8') as f:
                    first_lines = f.read(500)
                
                if '#!' not in first_lines and '<#' not in first_lines:
                    issues.append(f"PowerShell 脚本缺少头部注释：{ps_file.name}")
                    
            except Exception as e:
                issues.append(f"读取 {ps_file.name} 失败：{e}")
        
        # 检查 BAT 脚本
        for bat_file in self.directory.rglob('*.bat'):
            try:
                with open(bat_file, 'r', encoding='utf-8-sig') as f:
                    first_lines = f.read(200)
                
                if '@echo off' not in first_lines:
                    issues.append(f"BAT 脚本缺少标准头部：{bat_file.name}")
                if 'chcp 65001' not in first_lines:
                    issues.append(f"BAT 脚本缺少 chcp 65001: {bat_file.name}")
                    
            except Exception as e:
                issues.append(f"读取 {bat_file.name} 失败：{e}")
        
        if issues:
            for issue in issues:
                self.warnings.append(issue)
            return True  # 只是警告
        else:
            self.passed.append("所有脚本头部注释完整")
            return True
    
    def run_all_checks(self) -> bool:
        """
        运行所有检查
        
        Returns:
            True 如果所有关键检查通过
        """
        print("\n" + "=" * 80)
        print("脚本文件编码和转义字符验证工具")
        print(f"检查目录：{self.directory.absolute()}")
        print(f"检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 运行所有检查
        results = []
        
        results.append(("编码检测", self.check_encoding()))
        results.append(("PowerShell 转义测试", self.check_powershell_escapes()))
        results.append(("BAT 中文测试", self.check_batch_chinese()))
        results.append(("Git 配置检查", self.check_gitattributes()))
        results.append(("脚本头部检查", self.check_script_headers()))
        
        # 汇总结果
        print("\n" + "=" * 80)
        print("检查结果汇总")
        print("=" * 80)
        
        print(f"\n通过项 ({len(self.passed)}):")
        for item in self.passed:
            print(f"  ✓ {item}")
        
        if self.warnings:
            print(f"\n警告项 ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"  ⚠ {item}")
        
        if self.errors:
            print(f"\n错误项 ({len(self.errors)}):")
            for item in self.errors:
                print(f"  ✗ {item}")
        
        print("\n" + "=" * 80)
        
        # 判断是否通过
        if self.errors:
            print("结果：❌ 检查失败")
            print("=" * 80)
            return False
        else:
            print("结果：✅ 检查通过")
            print("=" * 80)
            return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='脚本文件编码和转义字符检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 检查当前目录
  python validate_scripts.py
  
  # 检查指定目录
  python validate_scripts.py /path/to/scripts
  
  # 在 CI/CD 中使用（失败时退出码为 1）
  python validate_scripts.py --ci
        """
    )
    
    parser.add_argument('directory', nargs='?', default='.',
                       help='要检查的目录路径（默认：当前目录）')
    parser.add_argument('--ci', action='store_true',
                       help='CI/CD 模式：失败时返回非零退出码')
    parser.add_argument('--skip-ps', action='store_true',
                       help='跳过 PowerShell 测试')
    parser.add_argument('--skip-bat', action='store_true',
                       help='跳过 BAT 测试')
    
    args = parser.parse_args()
    
    directory = Path(args.directory).absolute()
    
    if not directory.exists():
        print(f"错误：目录不存在：{directory}")
        sys.exit(1)
    
    validator = ScriptValidator(str(directory))
    
    # 运行检查
    success = validator.run_all_checks()
    
    # 退出码
    if args.ci:
        sys.exit(0 if success else 1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
