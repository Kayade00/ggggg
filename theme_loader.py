import json
import os
from typing import Dict, Any, Optional
import discord

class ThemeLoader:
    """
    A utility class for loading and managing bot theme configuration.
    Provides easy access to colors, emojis, formatting, and templates.
    """
    
    def __init__(self, theme_file_path: str = "theme.json"):
        self.theme_file_path = theme_file_path
        self._theme_data = None
        self.load_theme()
    
    def load_theme(self) -> None:
        """Load theme data from the JSON file"""
        try:
            if os.path.exists(self.theme_file_path):
                with open(self.theme_file_path, "r", encoding="utf-8") as f:
                    self._theme_data = json.load(f)
                print(f"✅ Theme loaded: {self._theme_data.get('name', 'Unknown')}")
            else:
                print(f"❌ Theme file not found: {self.theme_file_path}")
                self._theme_data = self._get_default_theme()
        except Exception as e:
            print(f"❌ Error loading theme: {e}")
            self._theme_data = self._get_default_theme()
    
    def _get_default_theme(self) -> Dict[str, Any]:
        """Fallback theme if file loading fails"""
        return {
            "colors": {"primary": "0x2b2d31", "error": "0xed4245", "success": "0x57f287"},
            "emojis": {"currency": {"coins": "🪙", "diamonds": "💎"}},
            "formatting": {"progress_bar": {"filled_char": "▰", "empty_char": "▱"}}
        }
    
    def reload_theme(self) -> bool:
        """Reload theme from file"""
        try:
            self.load_theme()
            return True
        except Exception as e:
            print(f"❌ Error reloading theme: {e}")
            return False
    
    # Color helpers
    def get_color(self, color_name: str) -> int:
        """Get color value as integer for discord.Embed"""
        color_hex = self._theme_data.get("colors", {}).get(color_name, "0x2b2d31")
        if isinstance(color_hex, str) and color_hex.startswith("0x"):
            return int(color_hex, 16)
        return 0x2b2d31
    
    def color(self, name: str) -> int:
        """Shorthand for get_color"""
        return self.get_color(name)
    
    # Emoji helpers
    def get_emoji(self, category: str, name: str) -> str:
        """Get emoji from category"""
        return self._theme_data.get("emojis", {}).get(category, {}).get(name, "❓")
    
    def emoji(self, category: str, name: str) -> str:
        """Shorthand for get_emoji"""
        return self.get_emoji(category, name)
    
    # Formatting helpers
    def get_progress_bar(self, current: int, total: int, length: Optional[int] = None) -> str:
        """Create a progress bar using theme settings"""
        progress_config = self._theme_data.get("formatting", {}).get("progress_bar", {})
        bar_length = length or progress_config.get("length", 5)
        filled_char = progress_config.get("filled_char", "▰")
        empty_char = progress_config.get("empty_char", "▱")
        
        # Ensure values are integers (handle string inputs safely)
        try:
            current = int(current)
            total = int(total)
        except (ValueError, TypeError):
            return empty_char * bar_length
        
        if total == 0:
            return empty_char * bar_length
        
        filled = min(int((current / total) * bar_length), bar_length)
        return filled_char * filled + empty_char * (bar_length - filled)
    
    def get_separator(self, sep_type: str) -> str:
        """Get separator character"""
        return self._theme_data.get("formatting", {}).get("separators", {}).get(sep_type, "•")
    
    def format_text(self, style: str, text: str) -> str:
        """Format text with theme style"""
        template = self._theme_data.get("formatting", {}).get("text_styles", {}).get(style, "{text}")
        return template.format(text=text)
    
    # Template helpers
    def get_template(self, template_name: str) -> str:
        """Get a formatting template"""
        return self._theme_data.get("templates", {}).get(template_name, "{text}")
    
    def format_template(self, template_name: str, **kwargs) -> str:
        """Format a template with provided arguments"""
        template = self.get_template(template_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            print(f"❌ Missing template variable: {e}")
            return template
    
    # Embed helpers
    def create_embed(self, title: str, description: str = "", color_name: str = "primary") -> discord.Embed:
        """Create a themed embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=self.get_color(color_name)
        )
    
    def success_embed(self, title: str, description: str = "") -> discord.Embed:
        """Create a success-themed embed"""
        return self.create_embed(title, description, "success")
    
    def error_embed(self, title: str, description: str = "") -> discord.Embed:
        """Create an error-themed embed"""
        return self.create_embed(title, description, "error")
    
    def info_embed(self, title: str, description: str = "") -> discord.Embed:
        """Create an info-themed embed"""
        return self.create_embed(title, description, "info")
    
    # Balance formatting
    def format_balance(self, coins: int, diamonds: int) -> str:
        """Format balance display using theme template"""
        return self.format_template(
            "balance_display",
            coins_emoji=self.emoji("currency", "coins"),
            diamonds_emoji=self.emoji("currency", "diamonds"),
            coins=coins,
            diamonds=diamonds
        )
    
    # Quest formatting
    def format_quest_progress(self, name: str, current: int, total: int, reward: str, emoji: str = "") -> str:
        """Format quest progress using theme template"""
        progress_bar = self.get_progress_bar(current, total)
        return self.format_template(
            "quest_progress",
            emoji=emoji,
            name=name,
            progress_bar=progress_bar,
            current=current,
            total=total,
            reward=reward
        )
    
    # Shop formatting
    def format_shop_item(self, name: str, price: int, currency: str, description: str, emoji: str = "") -> str:
        """Format shop item using theme template"""
        currency_emoji = self.emoji("currency", currency)
        return self.format_template(
            "shop_item",
            emoji=emoji,
            name=name,
            currency=currency_emoji,
            price=price,
            description=description
        )
    
    # Category formatting
    def format_category_list(self, name: str, count: int, available: bool = True) -> str:
        """Format category list item"""
        status = "available" if count > 0 else "Coming soon!"
        return self.format_template(
            "category_list",
            name=name,
            count=count,
            status=status
        )
    
    # Timeout helpers
    def get_timeout(self, timeout_type: str) -> int:
        """Get timeout value for UI elements"""
        return self._theme_data.get("timeouts", {}).get(timeout_type, 300)
    
    # Message helpers
    def get_message(self, category: str, key: str) -> str:
        """Get predefined message"""
        return self._theme_data.get("messages", {}).get(category, {}).get(key, "Unknown")
    
    # Utility methods
    def get_type_emoji(self, pokemon_type: str) -> str:
        """Get emoji for Pokemon type"""
        return self.emoji("types", pokemon_type.lower())
    
    def get_stat_emoji(self, stat_name: str) -> str:
        """Get emoji for Pokemon stat"""
        return self.emoji("stats", stat_name.lower())
    
    # Raw access for advanced usage
    def get_raw(self, *keys) -> Any:
        """Get raw theme data by key path"""
        data = self._theme_data
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data

# Global theme instance
theme = ThemeLoader()

# Convenience functions for easy importing
def get_color(name: str) -> int:
    return theme.get_color(name)

def get_emoji(category: str, name: str) -> str:
    return theme.get_emoji(category, name)

def create_embed(title: str, description: str = "", color_name: str = "primary") -> discord.Embed:
    return theme.create_embed(title, description, color_name)

def format_balance(coins: int, diamonds: int) -> str:
    return theme.format_balance(coins, diamonds)

def get_progress_bar(current: int, total: int, length: int = 5) -> str:
    return theme.get_progress_bar(current, total, length) 