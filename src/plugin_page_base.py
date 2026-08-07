"""
Plugin Page Base Class

This module provides the PluginPageBase class that serves as the standard
base class for all plugin pages, ensuring consistent lifecycle management
and integration with the application.
"""

try:
    from PyQt5.QtWidgets import QWidget
    from PyQt5.QtCore import pyqtSignal
except ImportError:
    # Fallback for development/testing without PyQt5
    class QWidget:
        def __init__(self, parent=None):
            pass
    
    class pyqtSignal:
        def __init__(self, *args):
            pass


class PluginPageBase(QWidget):
    """
    Base class for plugin pages
    
    Provides standardized lifecycle management, resource cleanup,
    and convenience methods for plugin configuration access.
    All plugin pages should inherit from this class.
    """
    
    # Signals for lifecycle events
    page_created = pyqtSignal()
    page_shown = pyqtSignal()
    page_hidden = pyqtSignal()
    page_destroyed = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        Initialize the plugin page base
        
        Args:
            parent: Parent widget (usually None for plugin pages)
        """
        super().__init__(parent)
        self.plugin_api = None      # Set by plugin manager
        self.plugin_name = None     # Set by plugin manager
        self._is_initialized = False
        
    def set_plugin_context(self, plugin_api, plugin_name: str):
        """
        Set the plugin context (called by plugin manager)
        
        Args:
            plugin_api: PluginAPI instance for this plugin
            plugin_name: Name of the plugin owning this page
        """
        self.plugin_api = plugin_api
        self.plugin_name = plugin_name
        
    def on_page_created(self):
        """
        Called when the page is first created
        
        Override this method to perform initialization that should
        happen only once when the page is created.
        """
        if not self._is_initialized:
            self._is_initialized = True
            self.page_created.emit()
            
    def on_page_shown(self):
        """
        Called when the page becomes visible to the user
        
        Override this method to perform actions when the user
        switches to this tab (e.g., refresh data, start timers).
        """
        self.page_shown.emit()
        
    def on_page_hidden(self):
        """
        Called when the page is hidden from the user
        
        Override this method to perform cleanup when the user
        switches away from this tab (e.g., pause operations, save state).
        """
        self.page_hidden.emit()
        
    def on_page_destroyed(self):
        """
        Called when the page is being destroyed
        
        Override this method to perform final cleanup before
        the page is removed (e.g., close files, stop threads).
        """
        self.page_destroyed.emit()
        
    def get_plugin_config(self, key: str, default=None):
        """
        Convenience method to get plugin configuration
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if self.plugin_api and self.plugin_name:
            return self.plugin_api.get_config(self.plugin_name, key, default)
        return default
        
    def set_plugin_config(self, key: str, value) -> bool:
        """
        Convenience method to set plugin configuration
        
        Args:
            key: Configuration key
            value: Value to save
            
        Returns:
            True if configuration saved successfully, False otherwise
        """
        if self.plugin_api and self.plugin_name:
            return self.plugin_api.set_config(self.plugin_name, key, value)
        return False
        
    def get_plugin_resource_path(self, resource_name: str) -> str:
        """
        Convenience method to get plugin resource path
        
        Args:
            resource_name: Name of the resource file
            
        Returns:
            Absolute path to resource file or empty string if not found
        """
        if self.plugin_api and self.plugin_name:
            path = self.plugin_api.get_resource_path(self.plugin_name, resource_name)
            return path if path else ""
        return ""
        
    def emit_plugin_event(self, event_type: str, data: dict = None):
        """
        Convenience method to emit plugin events
        
        Args:
            event_type: Type of event to emit
            data: Event data dictionary (optional)
        """
        if self.plugin_api and self.plugin_name:
            self.plugin_api.emit_plugin_event(
                self.plugin_name, 
                event_type, 
                data or {}
            )
            
    def subscribe_to_event(self, event_type: str, callback):
        """
        Convenience method to subscribe to events
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
            
        Returns:
            True if subscription successful, False otherwise
        """
        if self.plugin_api and self.plugin_name:
            return self.plugin_api.subscribe_event(
                self.plugin_name, 
                event_type, 
                callback
            )
        return False