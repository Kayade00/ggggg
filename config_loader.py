import json

def load_config():
    """Load bot configuration from config.json"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found! Please create a config file.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing config.json: {e}")
        return None

def get_config():
    """Get the loaded configuration"""
    return load_config()

def get_prefix():
    """Get the bot prefix from config"""
    config = load_config()
    return config.get("prefix", "!") if config else "!"

def get_owner_id():
    """Get the owner ID from config"""
    config = load_config()
    return config.get("owner_id", None) if config else None

# Cache the config to avoid reading file multiple times
_cached_config = None

def get_cached_config():
    """Get cached configuration (loads once, returns same instance)"""
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config 