"""
Demonstration of plugin lifecycle management

This script demonstrates the complete plugin lifecycle:
1. Loading a plugin
2. Enabling a plugin
3. Disabling a plugin
4. Unloading a plugin
"""

from pathlib import Path
from unittest.mock import Mock
import tempfile
import json

from plugin_manager import PluginManager
from plugin_instance import PluginStatus


def create_demo_plugin(plugin_dir: Path):
    """Create a demo plugin for testing"""
    plugin_path = plugin_dir / "demo-plugin"
    plugin_path.mkdir(parents=True, exist_ok=True)
    
    # Create manifest
    manifest = {
        "name": "demo-plugin",
        "version": "1.0.0",
        "description": "A demonstration plugin",
        "entry_point": "main.py",
        "author": {
            "github": "https://github.com/demo/plugin"
        }
    }
    
    with open(plugin_path / "plugin.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    # Create entry point with lifecycle hooks
    entry_point_code = '''
"""Demo plugin entry point"""

def on_load():
    """Called when plugin is loaded"""
    print("  [HOOK] on_load() called - Plugin is being loaded")

def on_enable():
    """Called when plugin is enabled"""
    print("  [HOOK] on_enable() called - Plugin is being enabled")

def on_disable():
    """Called when plugin is disabled"""
    print("  [HOOK] on_disable() called - Plugin is being disabled")

def on_unload():
    """Called when plugin is unloaded"""
    print("  [HOOK] on_unload() called - Plugin is being unloaded")
'''
    
    with open(plugin_path / "main.py", 'w', encoding='utf-8') as f:
        f.write(entry_point_code)
    
    return plugin_path


def main():
    """Run the demonstration"""
    print("=" * 60)
    print("Plugin Lifecycle Management Demonstration")
    print("=" * 60)
    
    # Create temporary plugin directory
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        
        # Create demo plugin
        print("\n1. Creating demo plugin...")
        create_demo_plugin(plugin_dir)
        print("   ✓ Demo plugin created")
        
        # Create plugin manager
        print("\n2. Initializing PluginManager...")
        mock_main_window = Mock()
        mock_settings_manager = Mock()
        mock_main_window.settings_manager = mock_settings_manager
        
        manager = PluginManager(mock_main_window)
        manager.plugin_directory = plugin_dir
        manager.settings_manager = mock_settings_manager
        print("   ✓ PluginManager initialized")
        
        # Load plugin
        print("\n3. Loading plugin...")
        result = manager.load_plugin("demo-plugin")
        if result:
            print("   ✓ Plugin loaded successfully")
            status = manager.get_plugin_status("demo-plugin")
            print(f"   Status: {status}")
        else:
            print("   ✗ Failed to load plugin")
            return
        
        # Enable plugin
        print("\n4. Enabling plugin...")
        result = manager.enable_plugin("demo-plugin")
        if result:
            print("   ✓ Plugin enabled successfully")
            status = manager.get_plugin_status("demo-plugin")
            print(f"   Status: {status}")
        else:
            print("   ✗ Failed to enable plugin")
        
        # Disable plugin
        print("\n5. Disabling plugin...")
        result = manager.disable_plugin("demo-plugin")
        if result:
            print("   ✓ Plugin disabled successfully")
            status = manager.get_plugin_status("demo-plugin")
            print(f"   Status: {status}")
        else:
            print("   ✗ Failed to disable plugin")
        
        # Unload plugin
        print("\n6. Unloading plugin...")
        result = manager.unload_plugin("demo-plugin")
        if result:
            print("   ✓ Plugin unloaded successfully")
            print(f"   Plugins remaining: {len(manager.plugins)}")
        else:
            print("   ✗ Failed to unload plugin")
        
        print("\n" + "=" * 60)
        print("Demonstration complete!")
        print("=" * 60)


if __name__ == "__main__":
    main()
