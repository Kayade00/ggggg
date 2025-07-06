# Pokemon Discord Bot

A comprehensive Pokemon Discord bot with catching, battling, trading, and more!

## Configuration

The bot uses a `config.json` file for all settings. Make sure to configure it before running the bot.

### config.json Structure

```json
{
  "prefix": "!",
  "owner_id": 1202397329370386523,
  "bot_settings": {
    "description": "A Pokemon Discord Bot",
    "activity": "Catching Pokemon!",
    "status": "online"
  },
  "features": {
    "spawning_enabled": true,
    "battles_enabled": true,
    "trading_enabled": true,
    "market_enabled": true
  },
  "spawn_settings": {
    "spawn_interval_min": 50,
    "spawn_interval_max": 200,
    "spawn_chance": 0.1,
    "shiny_chance": 0.001,
    "legendary_chance": 0.0001
  },
  "battle_settings": {
    "max_team_size": 6,
    "level_cap": 100,
    "xp_gain_enabled": true
  }
}
```

### Configuration Options

- **prefix**: Command prefix for the bot (default: "!")
- **owner_id**: Discord user ID of the bot owner
- **bot_settings**: Bot presence and activity settings
- **features**: Enable/disable specific bot features
- **spawn_settings**: Pokemon spawning configuration
- **battle_settings**: Battle system configuration

### Environment Variables

You can also set the bot token as an environment variable:
```bash
export BOT_TOKEN="your_bot_token_here"
```

If not set, the bot will use the hardcoded token in main.py.

## Features

- **Pokemon Catching**: Spawn and catch Pokemon with different rarities
- **Battle System**: Turn-based battles with type effectiveness and STAB
- **Trading**: Trade Pokemon with other users
- **Market**: Buy and sell Pokemon
- **Team Management**: Build and manage your Pokemon team
- **Level System**: Pokemon gain experience and level up

## Commands

### Slash Commands
- `/info` - View Pokemon information
- `/pokemon` - View your Pokemon collection
- `/start` - Get your starter Pokemon
- `/select` - Select your active Pokemon
- `/battle` - Start a battle with gym leaders

### Prefix Commands (!)
- `!info` - View Pokemon information
- `!pokemon` - View your Pokemon collection  
- `!start` - Get your starter Pokemon
- `!select` - Select your active Pokemon
- `!redirect` - Configure spawn channels (Admin only)

### Mention Commands (@bot)
- `@bot info` - View Pokemon information
- `@bot pokemon` - View your Pokemon collection
- And more...

## Setup

1. Configure `config.json` with your settings
2. Set up MongoDB database
3. Install required Python packages
4. Run `python main.py`

## Type Effectiveness

The bot uses a comprehensive type effectiveness system with:
- All 18 Pokemon types
- Proper dual-type calculations
- STAB (Same Type Attack Bonus) - 1.5x damage
- Accurate type multipliers (0x, 0.5x, 1x, 2x, 4x) 