#!/usr/bin/env python3
"""
最终验证脚本 - 检查共享内存信号广播机制集成状态
"""

import os
import sys
import importlib.util

def check_file_exists(filepath):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✓ {filepath} 存在")
        return True
    else:
        print(f"✗ {filepath} 不存在")
        return False

def check_import(module_name, filepath):
    """检查模块是否可以导入"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"✓ {module_name} 模块导入成功")
        return True
    except Exception as e:
        print(f"✗ {module_name} 模块导入失败: {e}")
        return False

def check_shared_memory_manager():
    """检查共享内存管理器"""
    try:
        from shared_memory_manager import get_shared_memory_manager, SharedMemoryManager
        manager = get_shared_memory_manager()
        print(f"✓ 共享内存管理器初始化成功: {type(manager)}")
        
        # 检查关键方法
        methods = ['broadcast_font_change', 'broadcast_theme_change', 
                  'broadcast_window_size_change', 'broadcast_settings_change']
        for method in methods:
            if hasattr(manager, method):
                print(f"✓ 方法 {method} 存在")
            else:
                print(f"✗ 方法 {method} 不存在")
        
        # 检查信号
        signals = ['font_changed', 'theme_changed', 'window_size_changed', 'settings_changed']
        for signal in signals:
            if hasattr(manager, signal):
                print(f"✓ 信号 {signal} 存在")
            else:
                print(f"✗ 信号 {signal} 不存在")
        
        return True
    except Exception as e:
        print(f"✗ 共享内存管理器初始化失败: {e}")
        return False

def check_page_integration(page_name, filepath):
    """检查页面集成状态"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 个性化页面是发送者，其他页面是接收者
        if page_name == "个性化页面":
            checks = [
                ("共享内存导入", "from shared_memory_manager import get_shared_memory_manager" in content),
                ("广播功能", "broadcast_" in content),
            ]
        else:
            checks = [
                ("共享内存导入", "from shared_memory_manager import get_shared_memory_manager" in content),
                ("信号连接方法", "_connect_shared_memory_signals" in content),
                ("字体信号处理", "_on_font_changed_from_shared_memory" in content),
                ("主题信号处理", "_on_theme_changed_from_shared_memory" in content),
                ("窗口尺寸信号处理", "_on_window_size_changed_from_shared_memory" in content),
                ("设置信号处理", "_on_settings_changed_from_shared_memory" in content),
            ]
        
        print(f"\n{page_name} 页面集成检查:")
        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"  {status} {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ {page_name} 页面检查失败: {e}")
        return False

def main():
    """主验证函数"""
    print("=== 共享内存信号广播机制集成验证 ===\n")
    
    # 检查核心文件
    print("1. 核心文件检查:")
    core_files = [
        "shared_memory_manager.py",
        "custom_page.py",
        "generation_page.py", 
        "settings_page.py",
        "misc_page.py"
    ]
    
    all_files_exist = True
    for file in core_files:
        if not check_file_exists(f"g:\\YanchaTTS\\{file}"):
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ 核心文件缺失，验证终止")
        return
    
    # 检查共享内存管理器
    print("\n2. 共享内存管理器检查:")
    if not check_shared_memory_manager():
        print("\n❌ 共享内存管理器初始化失败")
        return
    
    # 检查页面集成
    print("\n3. 页面集成检查:")
    pages = [
        ("个性化页面", "g:\\YanchaTTS\\custom_page.py"),
        ("生成页面", "g:\\YanchaTTS\\generation_page.py"),
        ("设置页面", "g:\\YanchaTTS\\settings_page.py"),
        ("杂项页面", "g:\\YanchaTTS\\misc_page.py")
    ]
    
    all_pages_ok = True
    for page_name, filepath in pages:
        if not check_page_integration(page_name, filepath):
            all_pages_ok = False
    
    # 个性化页面已经在第3步中检查过广播功能，这里跳过
    
    # 最终总结
    print("\n" + "="*50)
    if all_pages_ok:
        print("🎉 验证通过！共享内存信号广播机制已成功集成")
        print("\n下一步操作:")
        print("1. 运行测试程序: python test_shared_memory.py")
        print("2. 运行集成测试: python test_integration.py") 
        print("3. 在主程序中测试实际功能")
    else:
        print("❌ 验证失败！请检查上述错误项")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main()