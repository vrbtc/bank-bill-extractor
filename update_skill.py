#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单技能更新工具
- 版本管理
- 自动备份
- 增量更新
- 回滚功能
"""

import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path


class SkillUpdater:
    """技能更新管理器"""
    
    def __init__(self, skill_dir='.'):
        self.skill_dir = Path(skill_dir)
        self.version_file = self.skill_dir / 'VERSION.json'
        self.backup_dir = self.skill_dir / '.backups'
        self.current_version = self._load_version()
    
    def _load_version(self):
        """加载当前版本信息"""
        if self.version_file.exists():
            with open(self.version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'version': '0.0.0', 'build': 'unknown'}
    
    def _save_version(self, version_info):
        """保存版本信息"""
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)
    
    def status(self):
        """查看当前版本状态"""
        print("=" * 50)
        print("📦 银行账单技能 - 版本状态")
        print("=" * 50)
        print(f"  当前版本：v{self.current_version['version']}")
        print(f"  构建号：{self.current_version.get('build', 'N/A')}")
        print(f"  发布日期：{self.current_version.get('release_date', 'N/A')}")
        
        if self.backup_dir.exists():
            backups = list(self.backup_dir.glob('*'))
            print(f"  备份数量：{len(backups)} 个")
            if backups:
                latest = max(backups, key=lambda x: x.stat().st_mtime)
                print(f"  最新备份：{latest.name}")
        else:
            print("  备份数量：无")
        
        print("\n📋 更新日志：")
        changelog = self.current_version.get('changelog', '')
        for line in changelog.split('\n'):
            if line.strip():
                print(f"  • {line.strip()}")
        
        return self.current_version
    
    def backup(self, label=None):
        """创建当前版本的备份"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"v{self.current_version['version']}_{timestamp}"
        if label:
            backup_name += f"_{label}"
        
        backup_path = self.backup_dir / backup_name
        
        files_to_backup = [
            'bill_skill.py',
            'this_month_bills.py',
            'email_client.py',
            'email_decoder.py',
            'bank_extractors.py',
            'config.json',
            'VERSION.json',
            '.trae/skills/bank-bill-query/SKILL.md'
        ]
        
        os.makedirs(backup_path, exist_ok=True)
        
        backed_up = []
        for file in files_to_backup:
            src = self.skill_dir / file
            if src.exists():
                dst = backup_path / file
                os.makedirs(dst.parent, exist_ok=True)
                shutil.copy2(src, dst)
                backed_up.append(file)
        
        # 保存备份清单
        manifest = {
            'version': self.current_version['version'],
            'timestamp': timestamp,
            'files': backed_up,
            'label': label or ''
        }
        with open(backup_path / 'backup_manifest.json', 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 备份完成：{backup_name}")
        print(f"   备份位置：{backup_path}")
        print(f"   备份文件：{len(backed_up)} 个")
        
        return str(backup_path)
    
    def update_from_files(self, new_files_dir, version=None, changelog=None):
        """从目录更新技能文件（增量更新）"""
        source_dir = Path(new_files_dir)
        
        if not source_dir.exists():
            raise FileNotFoundError(f"源目录不存在: {source_dir}")
        
        old_version = self.current_version['version']
        
        # 先备份当前版本
        print("📦 正在创建更新前备份...")
        self.backup(label=f'before_update_to_{version or "new"}')
        
        # 要更新的核心文件
        core_files = [
            'bill_skill.py',
            'this_month_bills.py',
            'email_client.py',
            'email_decoder.py',
            'bank_extractors.py'
        ]
        
        updated = []
        skipped = []
        
        for filename in core_files:
            src = source_dir / filename
            dst = self.skill_dir / filename
            
            if src.exists():
                shutil.copy2(src, dst)
                updated.append(filename)
                print(f"  ✓ {filename}")
            else:
                skipped.append(filename)
                print(f"  ⊘ {filename} (未找到)")
        
        # 更新文档（如果存在）
        doc_files = ['.trae/skills/bank-bill-query/SKILL.md', 'OPENCLAW_DEPLOY_GUIDE.md']
        for doc in doc_files:
            src = source_dir / doc
            if src.exists():
                dst = self.skill_dir / doc
                os.makedirs(dst.parent, exist_ok=True)
                shutil.copy2(src, dst)
                updated.append(doc)
                print(f"  ✓ {doc}")
        
        # 更新版本号
        if version:
            new_version_info = {
                'version': version,
                'build': datetime.now().strftime('%Y%m%d'),
                'release_date': datetime.now().strftime('%Y-%m-%d'),
                'changelog': changelog or f'从 v{old_version} 更新',
                'author': self.current_version.get('author', 'Unknown'),
                'files': self.current_version.get('files', {}),
                'compatibility': self.current_version.get('compatibility', {})
            }
            self._save_version(new_version_info)
            self.current_version = new_version_info
            print(f"\n✅ 版本已更新: v{old_version} → v{version}")
        
        print(f"\n📊 更新结果：")
        print(f"   更新文件：{len(updated)} 个")
        if skipped:
            print(f"   跳过文件：{len(skipped)} 个")
        
        return {
            'success': True,
            'old_version': old_version,
            'new_version': version or old_version,
            'updated_files': updated,
            'skipped_files': skipped
        }
    
    def rollback(self, backup_name=None):
        """回滚到指定备份版本"""
        if not self.backup_dir.exists():
            print("❌ 没有可用的备份")
            return None
        
        # 列出所有备份
        backups = sorted(self.backup_dir.glob('v*'), reverse=True)
        
        if not backups:
            print("❌ 没有找到备份")
            return None
        
        if backup_name:
            target_backup = self.backup_dir / backup_name
            if not target_backup.exists():
                print(f"❌ 备份不存在: {backup_name}")
                return None
        else:
            target_backup = backups[0]
            backup_name = target_backup.name
        
        # 读取备份清单
        manifest_file = target_backup / 'backup_manifest.json'
        if manifest_file.exists():
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            manifest = {'version': 'unknown', 'files': []}
        
        # 执行回滚
        restored = []
        for filename in manifest.get('files', []):
            src = target_backup / filename
            dst = self.skill_dir / filename
            
            if src.exists():
                os.makedirs(dst.parent, exist_ok=True)
                shutil.copy2(src, dst)
                restored.append(filename)
        
        # 恢复版本文件
        version_backup = target_backup / 'VERSION.json'
        if version_backup.exists():
            shutil.copy2(version_backup, self.version_file)
            self.current_version = self._load_version()
        
        print(f"✅ 已回滚到：{backup_name}")
        print(f"   恢复文件：{len(restored)} 个")
        print(f"   当前版本：v{self.current_version['version']}")
        
        return {
            'success': True,
            'rollback_to': backup_name,
            'restored_files': restored,
            'current_version': self.current_version['version']
        }
    
    def list_backups(self):
        """列出所有可用备份"""
        print("=" * 50)
        print("📂 可用备份列表")
        print("=" * 50)
        
        if not self.backup_dir.exists():
            print("  （无备份）")
            return []
        
        backups = sorted(self.backup_dir.glob('v*'), reverse=True)
        
        if not backups:
            print("  （无备份）")
            return []
        
        backup_list = []
        for i, backup in enumerate(backups[:10], 1):  # 只显示最近10个
            manifest_file = backup / 'backup_manifest.json'
            if manifest_file.exists():
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                version = manifest.get('version', '?')
                timestamp = manifest.get('timestamp', '?')
                label = manifest.get('label', '')
                files_count = len(manifest.get('files', []))
                
                display_label = f" ({label})" if label else ""
                print(f"  {i:2d}. {backup.name}{display_label}")
                print(f"      版本: v{version} | 文件: {files_count}个 | 时间: {timestamp}")
            
            backup_list.append({
                'name': backup.name,
                'path': str(backup)
            })
        
        if len(backups) > 10:
            print(f"\n  ... 还有 {len(backups) - 10} 个更早的备份")
        
        return backup_list
    
    def create_release_package(self, output_dir=None, include_cache=False):
        """创建发布包（用于分享给OpenClaw）"""
        import zipfile
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        package_name = f"bank-bill-skill_v{self.current_version['version']}_{timestamp}.zip"
        
        if output_dir:
            output_path = Path(output_dir) / package_name
        else:
            output_path = self.skill_dir / package_name
        
        files_to_pack = [
            ('bill_skill.py', 'bill_skill.py'),
            ('this_month_bills.py', 'this_month_bills.py'),
            ('email_client.py', 'email_client.py'),
            ('email_decoder.py', 'email_decoder.py'),
            ('bank_extractors.py', 'bank_extractors.py'),
            ('config.json', 'config.json'),
            ('requirements.txt', 'requirements.txt'),
            ('VERSION.json', 'VERSION.json'),
            ('OPENCLAW_DEPLOY_GUIDE.md', 'OPENCLAW_DEPLOY_GUIDE.md'),
            ('.trae/skills/bank-bill-query/SKILL.md', '.trae/skills/bank-bill-query/SKILL.md')
        ]
        
        if include_cache:
            files_to_pack.append(('this_month_bills.json', 'this_month_bills.json'))
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for src, arcname in files_to_pack:
                src_path = self.skill_dir / src
                if src_path.exists():
                    zf.write(src_path, arcname)
                    print(f"  ✓ {arcname}")
                else:
                    print(f"  ⊘ {arcname} (不存在，跳过)")
        
        size_kb = output_path.stat().st_size / 1024
        print(f"\n✅ 发布包已创建：{package_name}")
        print(f"   大小：{size_kb:.1f} KB")
        print(f"   位置：{output_path}")
        
        return str(output_path)


# 命令行接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='银行账单技能更新工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # status 命令
    subparsers.add_parser('status', help='查看当前版本状态')
    
    # backup 命令
    backup_parser = subparsers.add_parser('backup', help='创建备份')
    backup_parser.add_argument('--label', type=str, default=None, help='备份标签')
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='从目录更新文件')
    update_parser.add_argument('source_dir', help='新文件所在目录')
    update_parser.add_argument('--version', type=str, default=None, help='新版本号')
    update_parser.add_argument('--changelog', type=str, default=None, help='更新说明')
    
    # rollback 命令
    rollback_parser = subparsers.add_parser('rollback', help='回滚到备份版本')
    rollback_parser.add_argument('backup_name', nargs='?', default=None, help='备份名称（默认最新）')
    
    # list 命令
    subparsers.add_parser('list', help='列出所有备份')
    
    # pack 命令
    pack_parser = subparsers.add_parser('pack', help='创建发布包')
    pack_parser.add_argument('--output', type=str, default=None, help='输出目录')
    pack_parser.add_argument('--include-cache', action='store_true', help='包含缓存数据')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    try:
        updater = SkillUpdater()
        
        if args.command == 'status':
            updater.status()
        
        elif args.command == 'backup':
            updater.backup(label=args.label)
        
        elif args.command == 'update':
            result = updater.update_from_files(
                args.source_dir,
                version=args.version,
                changelog=args.changelog
            )
            if result['success']:
                print(f"\n🎉 更新成功！建议运行测试：python bill_skill.py status")
        
        elif args.command == 'rollback':
            updater.rollback(backup_name=args.backup_name)
        
        elif args.command == 'list':
            updater.list_backups()
        
        elif args.command == 'pack':
            path = updater.create_release_package(
                output_dir=args.output,
                include_cache=args.include_cache
            )
            print(f"\n💡 可以把这个压缩包发给 OpenClaw 进行更新")
    
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)
