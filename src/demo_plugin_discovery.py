"""
Demonstration script for plugin discovery and manifest parsing

This script demonstrates the plugin discovery functionality implemented in task 2.1.
"""

import json
import logging
from pathlib import Path
from unittest.mock import Mock

from plugin_manager import PluginManager

# Configure logging to see the discovery process
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

def create_sample_plugin(plugin_dir: Path, name: str, version: str):
    """Helper function to create a sample plugin"""
    plugin_path = plugin_dir / name
    plugin_path.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "name": name,
        "version": version,
        "entry_point": "main.py",
        "author": {
            "github": f"https://github.com/example/{name}"
        },
        "description": f"Sample plugin: {name}"
    }
    
    with open(plugin_path / "plugin.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Created sample plugin: {name} v{version}")

def main():
    """Main demonstration function"""
    print("=" * 60)
    print("Plugin Discovery and Manifest Parsing Demo")
    print("=" * 60)
    print()
    
    # Create plugin manager
    mock_main_window = Mock()
    manager = PluginManager(mock_main_window)
    
    print(f"Plugin directory: {manager.plugin_directory.absolute()}")
    print()
    
    # Ensure plugin directory exists
    manager.plugin_directory.mkdir(exist_ok=True)
    
    # Create some sample plugins for demonstration
    print("Creating sample plugins...")
    create_sample_plugin(manager.plugin_directory, "demo-tts-engine", "1.0.0")
    create_sample_plugin(manager.plugin_directory, "demo-custom-tab", "2.1.0")
    print()
    
    # Discover plugins
    print("Discovering plugins...")
    print("-" * 60)
    discovered_plugins = manager.discover_plugins()
    print("-" * 60)
    print()
    
    # Display results
    if discovered_plugins:
        print(f"✓ Discovered {len(discovered_plugins)} plugin(s):")
        print()
        
        for i, plugin in enumerate(discovered_plugins, 1):
            print(f"{i}. {plugin.name}")
            print(f"   Version: {plugin.version}")
            print(f"   Entry Point: {plugin.entry_point}")
            print(f"   Author: {plugin.author}")
            print(f"   Description: {plugin.description}")
            
            # Validate the plugin
            is_valid, error = plugin.validate()
            if is_valid:
                print(f"   Status: ✓ Valid")
            else:
                print(f"   Status: ✗ Invalid - {error}")
            print()
    else:
        print("No plugins discovered.")
    
    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
