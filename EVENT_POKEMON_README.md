# Event Pokemon System 🎉

This document explains how the custom/event Pokemon system works in the bot.

## Overview
The bot now supports custom event Pokemon that are integrated into the main `pokedex.json` file.

## File Structure

### Event Pokemon in pokedex.json
Contains all custom/event Pokemon data. Each Pokemon should have:
- Unique ID (use 10000+ to avoid conflicts)
- Complete stats, types, moves, abilities
- Custom flags: `"custom": true`, `"event_exclusive": true`
- Event information: `"event_tag"` and `"description"`

### Sprite Files
Custom Pokemon sprites should be placed in the `full/` directory with the naming format: `{id}.png`
- Example: `10001.png` for Shadow Pikachu
- If no sprite exists, the Pokemon will still work but without an image

## Commands Added

### User Commands
- `!events` - View all available event Pokemon
- `!myevents` - View user's event Pokemon collection
- `!pokemon` - Now shows event icons (🎃🎄💝🎆) for event Pokemon
- `!info` - Shows event information for custom Pokemon
- `!pokedex <name>` - Works with custom Pokemon names

### Admin Commands
- `!ownerspawn <pokemon_name>` - Spawn Pokemon (owner only)

## Event Icons
The system automatically assigns emojis based on event tags:
- 🎃 Halloween events
- 🎄 Christmas events  
- 💝 Valentine's Day events
- 🎆 New Year events
- 🐰 Easter events
- ☀️ Summer events
- ❄️ Winter events
- ⭐ Default for other events

## Integration Points

### Existing Commands
All existing commands work seamlessly with custom Pokemon:
- Battle system (uses stats from pokedex.json)
- Move learning (uses moves data from pokedex.json)
- Evolution system (if evolution data is added)
- Trading and marketplace
- All collection management commands

### Database Storage
Custom Pokemon are stored in the same MongoDB collection as regular Pokemon, with these additional fields:
- `event_pokemon: true` (set when caught during events)
- `event_tag: "Event Name"` (which event they're from)
- `is_limited_edition: true` (marks them as special)

## Adding New Event Pokemon

1. **Add to pokedex.json**:
   ```json
   "10006": {
     "name": "Your Pokemon Name",
     "id": 10006,
     "types": ["type1", "type2"],
     "stats": { "hp": 80, "attack": 100, ... },
     "custom": true,
     "event_exclusive": true,
     "event_tag": "Your Event 2024",
     "description": "Pokemon description"
   }
   ```

2. **Add sprite** (optional):
   - Place `10006.png` in the `full/` directory
   - 96x96 pixels recommended

3. **Restart bot** to load new Pokemon data

## Time-Limited Events

To make Pokemon only available during certain times:

1. **Event Configuration** (future enhancement):
   - Create `events_config.json` with start/end times
   - Modify spawn system to check active events
   - Only spawn event Pokemon during active periods

2. **Permanent Collection**:
   - Players keep caught event Pokemon forever
   - Only availability is time-limited, not ownership

## Notes
- Custom Pokemon IDs start at 10001 to avoid conflicts
- Original pokedex.json remains unchanged
- System is backwards compatible
- Event Pokemon can be shiny (separate shiny sprites needed)
- Battle system calculates stats normally using base stats from JSON

## Examples Included
The current event Pokemon in pokedex.json include 5 example event Pokemon:
1. Shadow Pikachu (Halloween)
2. Frostmas Eevee (Christmas)  
3. Valentiny (Valentine's Day)
4. Spook Gastly (Halloween)
5. Firework Magikarp (New Year)

These can be used as templates for creating new event Pokemon! 