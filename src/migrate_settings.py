# coding=utf-8
"""
settings.ini 配置迁移工具

将旧的 Custom 段落中的配置项迁移到新的分类段落中。
运行此脚本后，settings.ini 将被重新组织为更清晰的结构。
"""

import configparser
import os
import shutil
from datetime import datetime


def backup_settings(config_file):
    """备份原配置文件"""
    if os.path.exists(config_file):
        backup_file = f"{config_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_file, backup_file)
        print(f"✓ 已备份原配置文件到: {backup_file}")
        return backup_file
    return None


def migrate_settings(config_file="config/settings.ini"):
    """迁移配置文件"""
    
    if not os.path.exists(config_file):
        print(f"✗ 配置文件不存在: {config_file}")
        return False
    
    # 备份原文件
    backup_file = backup_settings(config_file)
    
    # 读取原配置
    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')
    
    # 检查是否有 Custom 段落
    if 'Custom' not in config:
        print("✓ 配置文件已经是新格式，无需迁移")
        return True
    
    # 配置项到新段落的映射
    key_mapping = {
        # Window 段落
        'window_size': 'Window',
        'is_first_run': 'Window',
        
        # Theme 段落
        'current_theme': 'Theme',
        'background_color': 'Theme',
        'card_background_color': 'Theme',
        'component_background_color': 'Theme',
        'highlight_button_color': 'Theme',
        'text_color': 'Theme',
        
        # Font 段落
        'global_font': 'Font',
        'min_font_size': 'Font',
        'max_font_size': 'Font',
        
        # Notification 段落
        'notification_info_color': 'Notification',
        'notification_warning_color': 'Notification',
        'notification_error_color': 'Notification',
        'animation_appear': 'Notification',
        'animation_disappear': 'Notification',
        'animation_move': 'Notification',
        'position_m': 'Notification',
        'position_n': 'Notification',
        'width_ratio': 'Notification',
        'height_ratio': 'Notification',
        'max_visible': 'Notification',
        'offset_n': 'Notification',
        'spacing_n': 'Notification',
        'auto_close_time': 'Notification',
        
        # Tab 段落
        'tab_order': 'Tab',
        'tab_visibility': 'Tab',
        'initial_tab': 'Tab',
        'tab_switch_speed': 'Tab',
        'indicator_animation_speed': 'Tab',
        'indicator_x_offset': 'Tab',
        'indicator_y_offset': 'Tab',
        'indicator_width_adjust': 'Tab',
        'indicator_height_adjust': 'Tab',
        
        # Hotkeys 段落
        'hk_toggle_pause': 'Hotkeys',
        'hk_seek_backward': 'Hotkeys',
        'hk_seek_forward': 'Hotkeys',
        'hk_volume_up': 'Hotkeys',
        'hk_volume_down': 'Hotkeys',
        'hk_next_sentence': 'Hotkeys',
        'hk_prev_sentence': 'Hotkeys',
        'use_keyboard_hook': 'Hotkeys',
        'use_sdl_input': 'Hotkeys',
        
        # Dictation 段落
        'default_punctuation_hint': 'Dictation',
        'default_pause_marks': 'Dictation',
        'online_import_mode': 'Dictation',
        
        # Download 段落
        'github_acceleration': 'Download',
        'download_threads': 'Download',
        'max_download_threads': 'Download',
        'github_mirror': 'Download',
        
        # AI_Models 段落
        'ai_model_chat_provider': 'AI_Models',
        'ai_model_chat_model': 'AI_Models',
        'ai_model_vision_provider': 'AI_Models',
        'ai_model_vision_model': 'AI_Models',
        'ai_model_tts_provider': 'AI_Models',
        'ai_model_tts_model': 'AI_Models',
        'default_model_mimo': 'AI_Models',
        'default_model_qwen': 'AI_Models',
        'default_model_chatglm': 'AI_Models',
        'default_model_minimax': 'AI_Models',
        'default_model_ms': 'AI_Models',
        
        # Music 段落
        'music_playlists': 'Music',
        'music_queue_data': 'Music',
        'music_play_mode': 'Music',
    }

    # 迁移 Custom 段落中的配置项
    custom_section = config['Custom']
    migrated_count = 0
    unknown_keys = []
    
    for key, value in custom_section.items():
        target_section = key_mapping.get(key)
        
        if target_section:
            # 创建目标段落（如果不存在）
            if target_section not in config:
                config[target_section] = {}
            
            # 迁移配置项
            config[target_section][key] = value
            migrated_count += 1
            print(f"  迁移: {key} -> [{target_section}]")
        else:
            # 未知的配置项保留在 Custom 段落
            unknown_keys.append(key)
    
    # 清空 Custom 段落（保留未知的配置项）
    config.remove_section('Custom')
    if unknown_keys:
        config['Custom'] = {}
        for key in unknown_keys:
            config['Custom'][key] = custom_section[key]
            print(f"  保留: {key} -> [Custom] (未知配置项)")
    else:
        # 如果没有未知配置项，创建空的 Custom 段落
        config['Custom'] = {}
    
    # 同时检查 Default_Voices 段落
    # 注意：default_voice_1 和 default_voice_2 已废弃，不再使用
    
    # 保存新配置
    with open(config_file, 'w', encoding='utf-8') as f:
        config.write(f)
    
    print(f"\n✓ 迁移完成！共迁移 {migrated_count} 个配置项")
    if unknown_keys:
        print(f"  保留 {len(unknown_keys)} 个未知配置项在 [Custom] 段落")
    print(f"✓ 新配置已保存到: {config_file}")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("settings.ini 配置迁移工具")
    print("=" * 60)
    print()
    
    success = migrate_settings()
    
    if success:
        print("\n迁移成功！现在的配置文件结构更清晰，便于手动编辑。")
        print("\n新的配置段落说明：")
        print("  [Window]       - 窗口相关设置")
        print("  [Theme]        - 主题和颜色设置")
        print("  [Font]         - 字体设置")
        print("  [Notification] - 通知相关设置")
        print("  [Tab]          - 选项卡相关设置")
        print("  [Hotkeys]      - 热键设置")
        print("  [Dictation]    - 听写相关设置")
        print("  [Download]     - 下载相关设置")
        print("  [AI_Models]    - AI模型设置")
        print("  [Music]        - 音乐播放器设置")
        print("  [Streaming]    - 流式播放设置")
        print("  [Custom]       - 自定义/未分类设置")
    else:
        print("\n迁移失败，请检查错误信息。")
    
    print()
    input("按回车键退出...")
