import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from datetime import datetime, timedelta
import json
import random
import asyncio
import os
import sys

# Add the parent directory to sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load event configuration
with open("event_levels.json", "r", encoding="utf-8") as f:
    EVENT_CONFIG = json.load(f)

with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEMON_DATA = json.load(f)

# Custom Pokemon data is now in the main POKEMON_DATA

with open("nature.json", "r", encoding="utf-8") as f:
    NATURES = json.load(f)["natures"]

# Load moves data
try:
    with open("moves_data.json", "r", encoding="utf-8") as f:
        MOVES_DATA = json.load(f)
except FileNotFoundError:
    print("Warning: moves_data.json not found. Move info will be limited.")
    MOVES_DATA = {}

class EventSystem(commands.Cog):
    def __init__(self, bot, collection, user_profiles):
        self.bot = bot
        self.collection = collection
        self.user_profiles = user_profiles
        self.active_battles = {}
        self.gauntlet_config = EVENT_CONFIG["gauntlet"]
        self.event_data = EVENT_CONFIG["gauntlet"]

    def calculate_xp_for_level(self, level):
        return 3750 if level == 100 else int(375 + 33.75 * (level - 1))

    def calculate_stat(self, iv, level, base_stat, ev, is_hp=False):
        if is_hp:
            return ((2 * base_stat + iv + (ev // 4)) * level // 100) + level + 10
        return ((2 * base_stat + iv + (ev // 4)) * level // 100) + 5

    async def ensure_gauntlet_profile(self, user_id):
        """Ensure user has gauntlet progress in database"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        if not profile:
            new_profile = {
                "user_id": user_id,
                "coins": 0,
                "diamonds": 0,
                "gauntlet": {
                    "current_floor": 1,
                    "shards": {
                        "infernal": 0,
                        "frost": 0, 
                        "storm": 0,
                        "sea": 0,
                        "dragon": 0
                    },
                    "last_battle": None,
                    "completed_runs": 0,
                    "shadow_unlocked": []
                },
                "created_at": datetime.utcnow()
            }
            await self.user_profiles.insert_one(new_profile)
            return new_profile
        elif "gauntlet" not in profile:
            # Add gauntlet data to existing profile
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {"$set": {
                    "gauntlet": {
                        "current_floor": 1,
                        "shards": {
                            "infernal": 0,
                            "frost": 0,
                            "storm": 0,
                            "sea": 0,
                            "dragon": 0
                        },
                        "last_battle": None,
                        "completed_runs": 0,
                        "shadow_unlocked": []
                    }
                }}
            )
            profile["gauntlet"] = {
                "current_floor": 1,
                "shards": {"infernal": 0, "frost": 0, "storm": 0, "sea": 0, "dragon": 0},
                "last_battle": None,
                "completed_runs": 0,
                "shadow_unlocked": []
            }
        return profile

    def get_floor_data(self, floor):
        """Get floor configuration based on floor number"""
        # First try to get specific floor data
        floor_data = self.event_data.get("floors", {}).get(str(floor))
        if floor_data:
            return floor_data
        
        # If no specific floor data, return None
        return None

    def is_boss_floor(self, floor):
        """Check if floor is a boss floor"""
        return floor % 20 == 0 and floor <= 100



    def load_event_levels(self):
        """Load event level data from JSON file"""
        try:
            with open("event_levels.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("gauntlet", {})
        except FileNotFoundError:
            print("Warning: event_levels.json not found")
            return {}
        except Exception as e:
            print(f"Error loading event levels: {e}")
            return {}

    def generate_enemy_team(self, floor_number):
        """Generate enemy team for the given floor"""
        # Try to get specific floor data first
        floor_data = self.get_floor_data(floor_number)
        
        if floor_data and "enemy_team" in floor_data:
            # Use specific floor data if available
            return self._build_team_from_data(floor_data["enemy_team"])
        
        # Otherwise generate dynamic team based on floor
        return self._generate_dynamic_team(floor_number)
    
    def _build_team_from_data(self, enemy_team_data):
        """Build enemy team from specific floor data"""
        enemy_team = []
        
        for pokemon_data in enemy_team_data:
            # Get base Pokemon data from pokedex
            pokemon_id = str(pokemon_data["pokemon_id"])
            base_pokemon = None
            
            # Find Pokemon in pokedex data
            for poke_id, poke_data in POKEMON_DATA.items():
                if poke_id == pokemon_id:
                    base_pokemon = poke_data
                    break
            
            if not base_pokemon:
                print(f"Warning: Pokemon ID {pokemon_id} not found in pokedex")
                continue
            
            # Generate the enemy Pokemon
            level = pokemon_data["level"]
            moves = pokemon_data["moves"]
            
            # Calculate stats at the given level (using level 100 stats for battle)
            stats = base_pokemon["stats"]
            battle_stats = {
                "hp": ((2 * stats["hp"] + 31 + 0) * 100 // 100) + 100 + 10,  # Level 100 with max IVs
                "attack": ((2 * stats["attack"] + 31 + 0) * 100 // 100) + 5,
                "defense": ((2 * stats["defense"] + 31 + 0) * 100 // 100) + 5,
                "sp_attack": ((2 * stats["special-attack"] + 31 + 0) * 100 // 100) + 5,
                "sp_defense": ((2 * stats["special-defense"] + 31 + 0) * 100 // 100) + 5,
                "speed": ((2 * stats["speed"] + 31 + 0) * 100 // 100) + 5
            }
            
            # Get move details from moves_data.json
            move_list = []
            for move_name in moves:
                move_data = None
                # Find move in moves data
                for move_id, data in MOVES_DATA.items():
                    if data["name"].lower().replace("-", " ") == move_name.lower().replace("-", " "):
                        move_data = data
                        break
                
                if move_data:
                    # Handle None power values for status moves
                    power = move_data.get("power")
                    if power is None:
                        power = 0  # Status moves have 0 power
                    
                    move_list.append({
                        "name": move_name,
                        "type": move_data.get("type", "Normal"),
                        "power": power,
                        "accuracy": move_data.get("accuracy", 100),
                        "pp": move_data.get("pp", 10),
                        "damage_class": move_data.get("damage_class", "status")
                    })
                else:
                    # Fallback for unknown moves
                    move_list.append({
                        "name": move_name,
                        "type": "Normal", 
                        "power": 50,
                        "accuracy": 100,
                        "pp": 10,
                        "damage_class": "physical"
                    })
            
            enemy_pokemon = {
                "name": pokemon_data["name"],
                "level": level,
                "stats": battle_stats,
                "moves": move_list,
                "types": base_pokemon.get("types", ["Normal"]),
                "current_hp": battle_stats["hp"],
                "pokemon_id": pokemon_data["pokemon_id"]
            }
            
            enemy_team.append(enemy_pokemon)
        
        return enemy_team
    
    def _generate_dynamic_team(self, floor_number):
        """Generate dynamic enemy team based on floor number"""
        # Determine theme/type based on floor range
        if 1 <= floor_number <= 20:
            theme_types = ["Fire", "Ground", "Rock"]
            theme_name = "Volcanic"
        elif 21 <= floor_number <= 40:
            theme_types = ["Ice", "Water"]
            theme_name = "Frozen"
        elif 41 <= floor_number <= 60:
            theme_types = ["Electric", "Flying"]
            theme_name = "Storm"
        elif 61 <= floor_number <= 80:
            theme_types = ["Water", "Psychic"]
            theme_name = "Abyssal"
        elif 81 <= floor_number <= 100:
            theme_types = ["Dragon", "Dark"]
            theme_name = "Dragon"
        else:
            theme_types = ["Normal"]
            theme_name = "Unknown"
        
        # Calculate level based on floor (scale from 20 to 100)
        base_level = min(20 + (floor_number - 1) * 0.8, 100)
        level = int(base_level)
        
        # Generate team of 1-3 Pokemon (more on higher floors)
        team_size = 1 if floor_number <= 10 else (2 if floor_number <= 50 else 3)
        
        # For boss floors, always 3 Pokemon
        is_boss = self.is_boss_floor(floor_number)
        if is_boss:
            team_size = 3
            level = min(level + 10, 100)  # Boss Pokemon are higher level
        
        enemy_team = []
        
        # Get suitable Pokemon for this theme
        suitable_pokemon = []
        for poke_id, poke_data in POKEMON_DATA.items():
            if any(ptype in theme_types for ptype in poke_data.get("types", [])):
                suitable_pokemon.append((poke_id, poke_data))
        
        # Fallback if no themed Pokemon found
        if not suitable_pokemon:
            suitable_pokemon = [(poke_id, poke_data) for poke_id, poke_data in POKEMON_DATA.items() 
                             if int(poke_id) <= 150]  # Use gen 1 Pokemon as fallback
        
        # Select random Pokemon for team
        selected_pokemon = random.sample(suitable_pokemon, min(team_size, len(suitable_pokemon)))
        
        for poke_id, poke_data in selected_pokemon:
            # Calculate battle stats
            stats = poke_data["stats"]
            battle_stats = {
                "hp": ((2 * stats["hp"] + 25 + 0) * 100 // 100) + 100 + 10,
                "attack": ((2 * stats["attack"] + 25 + 0) * 100 // 100) + 5,
                "defense": ((2 * stats["defense"] + 25 + 0) * 100 // 100) + 5,
                "sp_attack": ((2 * stats["special-attack"] + 25 + 0) * 100 // 100) + 5,
                "sp_defense": ((2 * stats["special-defense"] + 25 + 0) * 100 // 100) + 5,
                "speed": ((2 * stats["speed"] + 25 + 0) * 100 // 100) + 5
            }
            
            # Generate moves (use some basic moves appropriate for the type)
            moves = self._generate_moves_for_pokemon(poke_data, level)
            
            enemy_pokemon = {
                "name": poke_data["name"],
                "level": level,
                "stats": battle_stats,
                "moves": moves,
                "types": poke_data.get("types", ["Normal"]),
                "current_hp": battle_stats["hp"],
                "pokemon_id": int(poke_id)
            }
            
            enemy_team.append(enemy_pokemon)
        
        return enemy_team
    
    def _generate_moves_for_pokemon(self, poke_data, level):
        """Generate appropriate moves for a Pokemon"""
        # Basic moves by type
        type_moves = {
            "Fire": [{"name": "Flamethrower", "type": "Fire", "power": 90, "accuracy": 100, "pp": 15, "damage_class": "special"}],
            "Water": [{"name": "Surf", "type": "Water", "power": 90, "accuracy": 100, "pp": 15, "damage_class": "special"}],
            "Electric": [{"name": "Thunderbolt", "type": "Electric", "power": 90, "accuracy": 100, "pp": 15, "damage_class": "special"}],
            "Grass": [{"name": "Energy Ball", "type": "Grass", "power": 90, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Ice": [{"name": "Ice Beam", "type": "Ice", "power": 90, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Fighting": [{"name": "Close Combat", "type": "Fighting", "power": 120, "accuracy": 100, "pp": 5, "damage_class": "physical"}],
            "Poison": [{"name": "Sludge Bomb", "type": "Poison", "power": 90, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Ground": [{"name": "Earthquake", "type": "Ground", "power": 100, "accuracy": 100, "pp": 10, "damage_class": "physical"}],
            "Flying": [{"name": "Air Slash", "type": "Flying", "power": 75, "accuracy": 95, "pp": 15, "damage_class": "special"}],
            "Psychic": [{"name": "Psychic", "type": "Psychic", "power": 90, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Bug": [{"name": "Bug Buzz", "type": "Bug", "power": 90, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Rock": [{"name": "Stone Edge", "type": "Rock", "power": 100, "accuracy": 80, "pp": 5, "damage_class": "physical"}],
            "Ghost": [{"name": "Shadow Ball", "type": "Ghost", "power": 80, "accuracy": 100, "pp": 15, "damage_class": "special"}],
            "Dragon": [{"name": "Dragon Pulse", "type": "Dragon", "power": 85, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Dark": [{"name": "Dark Pulse", "type": "Dark", "power": 80, "accuracy": 100, "pp": 15, "damage_class": "special"}],
            "Steel": [{"name": "Flash Cannon", "type": "Steel", "power": 80, "accuracy": 100, "pp": 10, "damage_class": "special"}],
            "Fairy": [{"name": "Moonblast", "type": "Fairy", "power": 95, "accuracy": 100, "pp": 15, "damage_class": "special"}]
        }
        
        moves = []
        pokemon_types = poke_data.get("types", ["Normal"])
        
        # Add STAB moves for Pokemon's types
        for ptype in pokemon_types:
            if ptype in type_moves:
                moves.extend(type_moves[ptype])
        
        # Add some generic moves
        generic_moves = [
            {"name": "Tackle", "type": "Normal", "power": 40, "accuracy": 100, "pp": 35, "damage_class": "physical"},
            {"name": "Quick Attack", "type": "Normal", "power": 40, "accuracy": 100, "pp": 30, "damage_class": "physical"},
            {"name": "Hyper Beam", "type": "Normal", "power": 150, "accuracy": 90, "pp": 5, "damage_class": "special"}
        ]
        
        moves.extend(generic_moves)
        
        # Return up to 4 moves
        return moves[:4] if len(moves) >= 4 else moves + generic_moves[:4-len(moves)]

    def create_battle_pokemon(self, poke_data, level, is_boss=False):
        """Create a Pokemon for battle"""
        # Generate decent IVs for enemies
        iv_range = (20, 31) if is_boss else (10, 25)
        
        pokemon = {
            "pokemon_name": poke_data["name"],
            "level": level,
            "nature": random.choice(list(NATURES.keys())),
            "hp_iv": random.randint(*iv_range),
            "atk_iv": random.randint(*iv_range),
            "def_iv": random.randint(*iv_range),
            "sp_atk_iv": random.randint(*iv_range),
            "sp_def_iv": random.randint(*iv_range),
            "spd_iv": random.randint(*iv_range),
            "hp_ev": 85 if is_boss else 50,
            "atk_ev": 85 if is_boss else 50,
            "def_ev": 85 if is_boss else 50,
            "sp_atk_ev": 85 if is_boss else 50,
            "sp_def_ev": 85 if is_boss else 50,
            "spd_ev": 85 if is_boss else 50,
        }
        
        # Add moves
        available_moves = [move["name"].replace("-", " ").title() 
                          for move in poke_data.get("moves", [])
                          if move.get("learn_method") == "level-up" and 
                          move.get("level_learned", 1) <= level]
        
        if not available_moves:
            available_moves = ["Tackle", "Scratch", "Pound"]
        
        # Select up to 4 moves
        selected_moves = random.sample(available_moves, min(4, len(available_moves)))
        while len(selected_moves) < 4:
            selected_moves.append("Tackle")
        
        pokemon.update({
            "move1": selected_moves[0],
            "move2": selected_moves[1], 
            "move3": selected_moves[2],
            "move4": selected_moves[3]
        })
        
        return pokemon

    @commands.group(name="gauntlet", aliases=["g", "shadow", "event"], invoke_without_command=True)
    async def gauntlet(self, ctx):
        """Main gauntlet overview command"""
        # Event is permanently over for everyone except owners
        if not await self.bot.is_owner(ctx.author):
            embed = discord.Embed(
                title="🎉 Shadow Gauntlet Event Completed!",
                description="The Shadow Gauntlet event has ended. Thank you for participating!\n\n"
                           "**🔄 Convert Your Shards to Coins:**\n"
                           "Use `b!gauntlet convert` to exchange your remaining shards for coins!\n"
                           "**Rate:** 1 shard = 500 coins\n\n"
                           "Your progress and Shadow Legendaries are permanently saved!",
                color=0xFFD700
            )
            embed.set_footer(text="Use b!gauntlet convert to exchange shards • Shadow Pokemon remain in your collection")
            return await ctx.reply(embed=embed)
        
        # Owner-only access to original functionality
        profile = await self.ensure_gauntlet_profile(ctx.author.id)
        gauntlet_data = profile["gauntlet"]
        
        current_floor = gauntlet_data["current_floor"]
        shards = gauntlet_data["shards"]
        
        # Get current floor theme
        floor_data = self.get_floor_data(current_floor)
        
        # Check if boss floor
        is_boss = self.is_boss_floor(current_floor)
        
        # Determine shard type based on floor range
        shard_type = "unknown"
        if 1 <= current_floor <= 20:
            shard_type = "infernal"
        elif 21 <= current_floor <= 40:
            shard_type = "frost"
        elif 41 <= current_floor <= 60:
            shard_type = "storm"
        elif 61 <= current_floor <= 80:
            shard_type = "sea"
        elif 81 <= current_floor <= 100:
            shard_type = "dragon"
        
        # Get theme names for display
        theme_names = {
            "infernal": "Volcanic Caverns",
            "frost": "Frozen Wasteland", 
            "storm": "Thunder Peaks",
            "sea": "Abyssal Depths",
            "dragon": "Dragon's Lair"
        }
        theme = theme_names.get(shard_type, "Unknown")

        embed = discord.Embed(
            title="🏛️ The Shadow Gauntlet [OWNER MODE]",
            description=f"**Current Floor:** {current_floor}/100\n**Theme:** {theme}",
            color=0x8B0000 if is_boss else 0x4B0082
        )

        # Shards display
        shard_emojis = {
            "infernal": "🔥", "frost": "❄️", "storm": "⚡", 
            "sea": "🌊", "dragon": "🐉"
        }

        shard_text = ""
        for shard_type_iter, count in shards.items():
            emoji = shard_emojis.get(shard_type_iter, "💎")
            shard_text += f"{emoji} {shard_type_iter.title()}: {count}\n"

        embed.add_field(name="💎 Shards Collected", value=shard_text, inline=True)

        # Shadow Pokemon unlocked
        unlocked = gauntlet_data.get("shadow_unlocked", [])
        if unlocked:
            unlocked_text = "\n".join([f"🌑 {pokemon}" for pokemon in unlocked])
        else:
            unlocked_text = "None unlocked yet"

        embed.add_field(name="🌑 Shadow Legendaries", value=unlocked_text, inline=True)

        # Battle status - always ready now
        embed.add_field(name="⚔️ Battle Status", value="✅ Ready to battle!", inline=False)

        # Progress info
        if is_boss:
            embed.add_field(
                name="👑 Boss Floor!",
                value=f"Defeat the boss to earn 3 {shard_emojis.get(shard_type, '💎')} shards!",
                inline=False
            )
        else:
            embed.add_field(
                name="⚔️ Regular Floor",
                value=f"Battle enemies to earn 1 {shard_emojis.get(shard_type, '💎')} shard!",
                inline=False
            )
        
        embed.set_footer(text="Use b!gauntlet battle to start fighting | b!gauntlet stats to view progress and combine Shadow Legendaries")
        await ctx.reply(embed=embed)

    @gauntlet.command(name="battle", aliases=["fight", "b"])
    async def gauntlet_battle(self, ctx):
        """Start a gauntlet battle"""
        # Event is permanently over for everyone except owners
        if not await self.bot.is_owner(ctx.author):
            embed = discord.Embed(
                title="🎉 Shadow Gauntlet Event Completed!",
                description="The Shadow Gauntlet event has ended. Thank you for participating!\n\n"
                           "**🔄 Convert Your Shards to Coins:**\n"
                           "Use `b!gauntlet convert` to exchange your remaining shards for coins!\n"
                           "**Rate:** 1 shard = 500 coins\n\n"
                           "Your progress and Shadow Legendaries are permanently saved!",
                color=0xFFD700
            )
            embed.set_footer(text="Use b!gauntlet convert to exchange shards • Shadow Pokemon remain in your collection")
            return await ctx.reply(embed=embed)
        
        # Owner-only battle functionality
        user_id = ctx.author.id
        
        # Check if already in battle
        if user_id in self.active_battles:
            return await ctx.reply("❌ You're already in a battle!")
        
        # Get user profile and Pokemon
        profile = await self.ensure_gauntlet_profile(user_id)
        user_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
        
        if not user_pokemon:
            return await ctx.reply("❌ You don't have any Pokémon! Catch some first.")
        
        # Check for party
        party_pokemon_ids = profile.get("party", [])
        party_pokemon = []
        if party_pokemon_ids:
            for pokemon_id in party_pokemon_ids:
                try:
                    from bson import ObjectId
                    pokemon = await self.collection.find_one({"_id": ObjectId(pokemon_id), "user_id": user_id})
                    if pokemon:
                        party_pokemon.append(pokemon)
                except:
                    continue
        
        if len(party_pokemon) < 3:
            return await ctx.reply("❌ You need at least 3 Pokémon in your party! Use `!party` to set up your team.")
        
        # Get gauntlet data
        gauntlet_data = profile["gauntlet"]
        current_floor = gauntlet_data["current_floor"]
        
        # Check if boss floor
        is_boss = self.is_boss_floor(current_floor)
        
        # Generate enemy team
        enemy_team = self.generate_enemy_team(current_floor)
        
        if not enemy_team:
            return await ctx.reply("❌ Failed to generate enemy team. Please try again.")
        
        # Generate enemy name based on floor
        if is_boss:
            enemy_name = f"Floor {current_floor} Boss"
        else:
            enemy_name = f"Floor {current_floor} Enemies"
        
        # Start battle
        self.active_battles[user_id] = {
            "floor": current_floor,
            "enemy_name": enemy_name,
            "is_boss": is_boss,
            "start_time": datetime.utcnow()
        }
        
        # Get battle cog for battle logic
        battle_cog = self.bot.get_cog("Battle")
        if not battle_cog:
            del self.active_battles[user_id]
            return await ctx.reply("❌ Battle system not available! Please contact an administrator.")
        
        # Create battle embed
        theme_names = {
            "infernal": "Volcanic Caverns",
            "frost": "Frozen Wasteland", 
            "storm": "Thunder Peaks",
            "sea": "Abyssal Depths",
            "dragon": "Dragon's Lair"
        }
        
        # Determine shard type based on floor range
        shard_type = "unknown"
        if 1 <= current_floor <= 20:
            shard_type = "infernal"
        elif 21 <= current_floor <= 40:
            shard_type = "frost"
        elif 41 <= current_floor <= 60:
            shard_type = "storm"
        elif 61 <= current_floor <= 80:
            shard_type = "sea"
        elif 81 <= current_floor <= 100:
            shard_type = "dragon"
        
        theme = theme_names.get(shard_type, "Unknown")
        
        embed = discord.Embed(
            title=f"🏛️ Gauntlet Floor {current_floor} [OWNER MODE]",
            description=f"**Location:** {theme}\n**Enemy:** {enemy_name}",
            color=0x8B0000 if is_boss else 0x4B0082
        )
        
        if is_boss:
            embed.add_field(
                name="👑 Boss Battle!",
                value="Defeat this champion to earn 3 shards and advance!",
                inline=False
            )
        
        # Show teams
        user_team_text = ""
        for i, pokemon in enumerate(party_pokemon[:3]):
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            shiny_text = "✨ " if pokemon.get("shiny", False) else ""
            user_team_text += f"{i+1}. {shiny_text}**{display_name}** - Lv.{pokemon['level']}\n"
        
        enemy_team_text = ""
        for i, pokemon in enumerate(enemy_team):
            enemy_team_text += f"{i+1}. **{pokemon['name']}** - Lv.{pokemon['level']}\n"
        
        embed.add_field(name="🎯 Your Team", value=user_team_text, inline=True)
        embed.add_field(name="👹 Enemy Team", value=enemy_team_text, inline=True)
        
        # Create battle view
        view = GauntletBattleView(self, battle_cog, user_id, party_pokemon[:3], enemy_team, enemy_name)
        await ctx.reply(embed=embed, view=view)

    @gauntlet.command(name="stats", aliases=["progress", "s"])
    async def gauntlet_stats(self, ctx):
        """Show gauntlet progress and statistics"""
        # Event is permanently over for everyone except owners
        if not await self.bot.is_owner(ctx.author):
            embed = discord.Embed(
                title="🎉 Shadow Gauntlet Event Completed!",
                description="The Shadow Gauntlet event has ended. Thank you for participating!\n\n"
                           "**🔄 Convert Your Shards to Coins:**\n"
                           "Use `b!gauntlet convert` to exchange your remaining shards for coins!\n"
                           "**Rate:** 1 shard = 500 coins\n\n"
                           "Your progress and Shadow Legendaries are permanently saved!",
                color=0xFFD700
            )
            embed.set_footer(text="Use b!gauntlet convert to exchange shards • Shadow Pokemon remain in your collection")
            return await ctx.reply(embed=embed)
        
        # Owner-only stats functionality
        profile = await self.ensure_gauntlet_profile(ctx.author.id)
        gauntlet_data = profile["gauntlet"]
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}'s Gauntlet Stats [OWNER MODE]",
            color=0x4B0082
        )
        
        # Basic progress
        current_floor = gauntlet_data["current_floor"]
        completed_runs = gauntlet_data.get("completed_runs", 0)
        
        embed.add_field(
            name="🏛️ Progress",
            value=f"**Current Floor:** {current_floor}/100\n**Completed Runs:** {completed_runs}",
            inline=True
        )
        
        # Shards breakdown
        shards = gauntlet_data["shards"]
        total_shards = sum(shards.values())
        
        shard_emojis = {
            "infernal": "🔥", "frost": "❄️", "storm": "⚡", 
            "sea": "🌊", "dragon": "🐉"
        }
        
        shard_text = f"**Total:** {total_shards}\n"
        for shard_type, count in shards.items():
            emoji = shard_emojis.get(shard_type, "💎")
            shard_text += f"{emoji} {shard_type.title()}: {count}\n"
        
        embed.add_field(name="💎 Shards Collected", value=shard_text, inline=True)
        
        # Available combinations
        combinations_text = ""
        legendaries = {
            "Shadow Articuno": {"cost": {"frost": 60}, "emoji": "❄️"},
            "Shadow Moltres": {"cost": {"infernal": 60}, "emoji": "🔥"}, 
            "Shadow Zapdos": {"cost": {"storm": 60}, "emoji": "⚡"},
            "Shadow Lugia": {"cost": {"sea": 100}, "emoji": "🌊"},
            "Shadow Rayquaza": {"cost": {"dragon": 100}, "emoji": "🐉"}
        }
        
        for name, data in legendaries.items():
            emoji = data["emoji"]
            shard_type, cost = list(data["cost"].items())[0]
            available = shards.get(shard_type, 0)
            status = "✅" if available >= cost else "❌"
            combinations_text += f"{status} {emoji} {name}: {available}/{cost}\n"
        
        embed.add_field(name="🌑 Shadow Legendary Combinations", value=combinations_text, inline=False)
        embed.set_footer(text="Use the buttons below to combine Shadow Legendaries!")
        
        # Create view with combination button
        view = GauntletStatsView(self, ctx.author.id, shards)
        await ctx.reply(embed=embed, view=view)

    @gauntlet.command(name="convert", aliases=["exchange", "c"])
    async def gauntlet_convert(self, ctx):
        """Convert remaining shards to coins (1 shard = 500 coins)"""
        profile = await self.ensure_gauntlet_profile(ctx.author.id)
        gauntlet_data = profile["gauntlet"]
        shards = gauntlet_data["shards"]
        
        # Calculate total shards
        total_shards = sum(shards.values())
        
        if total_shards == 0:
            embed = discord.Embed(
                title="❌ No Shards to Convert",
                description="You don't have any shards to convert to coins!",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Calculate coins to receive (1 shard = 500 coins)
        coins_to_receive = total_shards * 500
        
        # Show conversion preview
        shard_emojis = {
            "infernal": "🔥", "frost": "❄️", "storm": "⚡", 
            "sea": "🌊", "dragon": "🐉"
        }
        
        shard_breakdown = []
        for shard_type, count in shards.items():
            if count > 0:
                emoji = shard_emojis.get(shard_type, "💎")
                shard_breakdown.append(f"{emoji} {shard_type.title()}: {count}")
        
        embed = discord.Embed(
            title="🔄 Convert Shards to Coins",
            description=f"**Current Shards:**\n" + "\n".join(shard_breakdown) + f"\n\n"
                       f"**Total Shards:** {total_shards}\n"
                       f"**Conversion Rate:** 1 shard = 500 coins\n"
                       f"**You will receive:** 💰 {coins_to_receive:,} coins\n\n"
                       f"⚠️ **Warning:** This will permanently remove all your shards!",
            color=0xFFD700
        )
        
        # Create confirmation view
        view = ShardConvertView(self, ctx.author.id, total_shards, coins_to_receive)
        await ctx.reply(embed=embed, view=view)

    # Old complete_combination method removed - using create_shadow_pokemon instead

    async def complete_battle(self, user_id, victory, floor, is_boss):
        """Handle battle completion and rewards"""
        if victory:
            # Get floor data for rewards
            floor_data = self.get_floor_data(floor)
            shard_type = floor_data["shard_type"] if floor_data else "infernal"
            
            # Calculate rewards (with fallbacks if config missing)
            rewards_config = self.gauntlet_config.get("rewards", {
                "regular_floor": {"shards": 2, "coins": 100},
                "boss_floor": {"shards": 5, "coins": 500}
            })
            
            if is_boss:
                shards_earned = rewards_config["boss_floor"]["shards"]
                coins_earned = rewards_config["boss_floor"]["coins"]
            else:
                shards_earned = rewards_config["regular_floor"]["shards"]
                coins_earned = rewards_config["regular_floor"]["coins"]
            
            # Advance floor
            next_floor = floor + 1
            if next_floor > 100:
                # Completed the gauntlet!
                next_floor = 1
                await self.user_profiles.update_one(
                    {"user_id": user_id},
                    {"$inc": {"gauntlet.completed_runs": 1}}
                )
            
            # Update database
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "gauntlet.current_floor": next_floor
                    },
                    "$inc": {
                        f"gauntlet.shards.{shard_type}": shards_earned,
                        "coins": coins_earned
                    }
                }
            )
            
            return shards_earned, coins_earned, shard_type, next_floor
        else:
            # No updates needed on loss, just return
            return 0, 0, "", floor

    async def create_shadow_pokemon(self, user_id, legendary_name, pokemon_id):
        """Create a shadow legendary Pokemon and add it to user's collection"""
        import random
        from datetime import datetime
        
        # Get the highest pokemon_number for this user and increment
        last_pokemon = await self.collection.find_one(
            {"user_id": user_id},
            sort=[("pokemon_number", -1)]
        )
        next_number = (last_pokemon.get("pokemon_number", 0) + 1) if last_pokemon else 1
        
        # Generate random IVs (20-31 for legendary)
        ivs = {
            "hp_iv": random.randint(20, 31),
            "atk_iv": random.randint(20, 31), 
            "def_iv": random.randint(20, 31),
            "sp_atk_iv": random.randint(20, 31),
            "sp_def_iv": random.randint(20, 31),
            "spd_iv": random.randint(20, 31)
        }
        
        # Random nature
        natures = ["Hardy", "Docile", "Serious", "Bashful", "Quirky", "Lonely", "Brave", "Adamant", "Naughty", "Bold"]
        nature = random.choice(natures)
        
        # Calculate XP for level 70
        xp = self.calculate_xp_for_level(70)
        
        # Create Pokemon document
        pokemon_doc = {
            "user_id": user_id,
            "pokemon_name": legendary_name,
            "pokemon_id": pokemon_id,
            "pokemon_number": next_number,  # Required for !pokemon command
            "level": 70,  # Start at level 70
            "xp": xp,
            "nature": nature,
            "shiny": False,  # Shadow legendaries aren't shiny
            "caught_at": datetime.utcnow(),
            "timestamp": datetime.utcnow(),
            "custom": True,
            "event_exclusive": True,
            "event_tag": "Shadow Gauntlet",
            "friendship": 0,
            "selected": last_pokemon is None,  # Auto-select if first Pokemon
            "favorite": False,  # Standard field required for compatibility
            **ivs,
            # EVs start at 0
            "hp_ev": 0, "atk_ev": 0, "def_ev": 0,
            "sp_atk_ev": 0, "sp_def_ev": 0, "spd_ev": 0,
            # No nickname initially
            "nickname": None,
            # Perfect IVs for legendary status
            "perfect_ivs": sum(1 for iv in ivs.values() if iv == 31)
        }
        
        # Insert into Pokemon collection
        result = await self.collection.insert_one(pokemon_doc)
        return result.inserted_id

    # ═══════════════════════════════════════════════════════════════════════════════════════
    # OWNER-ONLY EVENT MANAGEMENT COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════════════════
    
    @commands.group(name="eventadmin", aliases=["ea", "admin"], invoke_without_command=True)
    @commands.is_owner()
    async def event_admin(self, ctx):
        """Owner-only event management commands"""
        embed = discord.Embed(
            title="🔧 Event Administration",
            description="Event Management System",
            color=0x8B0000
        )
        
        # Check current status
        config = await self.user_profiles.find_one({"_id": "event_config"}) or {}
        is_active = config.get("gauntlet_active", True)
        
        embed.add_field(
            name="📊 Current Status",
            value=f"**Gauntlet Event:** {'🟢 Active' if is_active else '🔴 Inactive'}",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Available Commands",
            value=(
                "**Gauntlet Event:**\n"
                "`!eventadmin start` - Enable the gauntlet event\n"
                "`!eventadmin stop` - Disable the gauntlet event\n"
                "`!eventadmin reset <user>` - Reset user's gauntlet progress\n"
                "`!eventadmin give <user> <shard_type> <amount>` - Give shards to user\n"
                "`!eventadmin stats` - View event statistics\n\n"
                "**Forest Event:**\n"
                "`!eventadmin forest start <duration>` - Start global forest event\n"
                "`!eventadmin forest stop` - Stop forest event\n"
                "`!eventadmin forest spawn <channel>` - Force spawn forest Pokemon\n"
                "`!eventadmin forest status` - Check forest event status"
            ),
            inline=False
        )
        
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="start", aliases=["enable", "on"])
    @commands.is_owner()
    async def start_event(self, ctx):
        """Start/enable the Shadow Gauntlet event"""
        await self.user_profiles.update_one(
            {"_id": "event_config"},
            {"$set": {"gauntlet_active": True}},
            upsert=True
        )
        
        embed = discord.Embed(
            title="✅ Event Started",
            description="The Shadow Gauntlet event is now **active**!\nPlayers can now access gauntlet commands.",
            color=0x00FF00
        )
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="stop", aliases=["disable", "off"])
    @commands.is_owner()
    async def stop_event(self, ctx):
        """Stop/disable the Shadow Gauntlet event"""
        await self.user_profiles.update_one(
            {"_id": "event_config"},
            {"$set": {"gauntlet_active": False}},
            upsert=True
        )
        
        embed = discord.Embed(
            title="🛑 Event Stopped",
            description="The Shadow Gauntlet event is now **inactive**.\nPlayers cannot access gauntlet commands.",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="reset")
    @commands.is_owner()
    async def reset_user(self, ctx, user: discord.Member):
        """Reset a user's gauntlet progress"""
        # Reset their gauntlet data
        await self.user_profiles.update_one(
            {"user_id": user.id},
            {"$set": {
                "gauntlet.current_floor": 1,
                "gauntlet.shards": {
                    "infernal": 0, "frost": 0, "storm": 0, "sea": 0, "dragon": 0
                },
                "gauntlet.shadow_unlocked": [],
                "gauntlet.completed_runs": 0
            }}
        )
        
        embed = discord.Embed(
            title="🔄 Progress Reset",
            description=f"**{user.display_name}**'s gauntlet progress has been reset to floor 1 with no shards.",
            color=0xFFD700
        )
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="give")
    @commands.is_owner()
    async def give_shards(self, ctx, user: discord.Member, shard_type: str, amount: int):
        """Give shards to a user"""
        valid_types = ["infernal", "frost", "storm", "sea", "dragon"]
        if shard_type.lower() not in valid_types:
            return await ctx.reply(f"❌ Invalid shard type! Valid types: {', '.join(valid_types)}")
        
        if amount <= 0:
            return await ctx.reply("❌ Amount must be positive!")
        
        # Ensure user has gauntlet profile
        await self.ensure_gauntlet_profile(user.id)
        
        # Give shards
        await self.user_profiles.update_one(
            {"user_id": user.id},
            {"$inc": {f"gauntlet.shards.{shard_type.lower()}": amount}}
        )
        
        shard_emojis = {
            "infernal": "🔥", "frost": "❄️", "storm": "⚡", 
            "sea": "🌊", "dragon": "🐉"
        }
        emoji = shard_emojis.get(shard_type.lower(), "💎")
        
        embed = discord.Embed(
            title="🎁 Shards Given",
            description=f"Gave **{amount}x** {emoji} **{shard_type.title()} Shards** to **{user.display_name}**",
            color=0x00FF00
        )
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="stats", aliases=["statistics"])
    @commands.is_owner()
    async def event_stats(self, ctx):
        """View event statistics"""
        # Get all gauntlet players
        players = await self.user_profiles.find({"gauntlet": {"$exists": True}}).to_list(length=None)
        
        if not players:
            return await ctx.reply("📊 No players have started the gauntlet yet!")
        
        total_players = len(players)
        floors_distribution = {}
        total_shards = {"infernal": 0, "frost": 0, "storm": 0, "sea": 0, "dragon": 0}
        total_completions = 0
        shadow_pokemon_created = 0
        
        for player in players:
            gauntlet_data = player["gauntlet"]
            current_floor = gauntlet_data.get("current_floor", 1)
            
            # Floor distribution
            floor_range = f"{((current_floor-1)//20)*20+1}-{min(((current_floor-1)//20+1)*20, 100)}"
            floors_distribution[floor_range] = floors_distribution.get(floor_range, 0) + 1
            
            # Shard totals
            shards = gauntlet_data.get("shards", {})
            for shard_type, count in shards.items():
                if shard_type in total_shards:
                    total_shards[shard_type] += count
            
            # Completions
            total_completions += gauntlet_data.get("completed_runs", 0)
            
            # Shadow Pokemon
            shadow_pokemon_created += len(gauntlet_data.get("shadow_unlocked", []))
        
        embed = discord.Embed(
            title="📊 Shadow Gauntlet Statistics",
            color=0x8B0000
        )
        
        embed.add_field(
            name="👥 Player Stats",
            value=f"**Total Players:** {total_players}\n**Gauntlet Completions:** {total_completions}\n**Shadow Pokemon Created:** {shadow_pokemon_created}",
            inline=True
        )
        
        # Floor distribution
        floor_text = "\n".join([f"Floors {range_str}: {count}" for range_str, count in sorted(floors_distribution.items())])
        embed.add_field(
            name="🏛️ Floor Distribution",
            value=floor_text or "No data",
            inline=True
        )
        
        # Shard totals
        shard_emojis = {"infernal": "🔥", "frost": "❄️", "storm": "⚡", "sea": "🌊", "dragon": "🐉"}
        shard_text = "\n".join([f"{shard_emojis[shard_type]} {shard_type.title()}: {count}" 
                               for shard_type, count in total_shards.items()])
        embed.add_field(
            name="💎 Total Shards Collected",
            value=shard_text,
            inline=False
        )
        
        await ctx.reply(embed=embed)
    
    @event_admin.command(name="forest")
    @commands.is_owner()
    async def forest_event_admin(self, ctx, action: str = None, duration: str = None, channel: discord.TextChannel = None):
        """Manage forest event (owner only)"""
        if not action:
            embed = discord.Embed(
                title="🌳 Forest Event Management",
                description="**Available Actions:**\n"
                           "`start [duration]` - Start global forest event\n"
                           "`stop` - Stop forest event\n"
                           "`spawn <channel>` - Force spawn forest Pokemon\n"
                           "`status` - Check forest event status\n\n"
                           "**Duration Options:** 1h, 3h, 6h, 24h, indefinite\n"
                           "**Default:** indefinite (runs until manually stopped)\n\n"
                           "**Example:** `b!eventadmin forest start indefinite`\n\n"
                           "**How it works:**\n"
                           "Forest Pokemon spawn naturally like regular Pokemon during the event period across ALL servers!",
                color=0x228B22
            )
            return await ctx.reply(embed=embed)
        
        action = action.lower()
        
        if action == "start":
            # Get forest event cog
            forest_cog = self.bot.get_cog("ForestEventSystem")
            if not forest_cog:
                return await ctx.reply("❌ Forest event system not loaded!")
            
            # Check if event already active
            if forest_cog.active_forest_event:
                return await ctx.reply("❌ There's already an active forest event!")
            
            # Handle duration
            if not duration:
                duration = "indefinite"  # Default to indefinite
            
            duration = duration.lower()
            
            # Validate inputs
            duration_map = {"1h": (1, 60), "3h": (3, 180), "6h": (6, 360), "24h": (24, 1440), "indefinite": (None, -1)}
            
            if duration not in duration_map:
                return await ctx.reply("❌ Invalid duration! Use: 1h, 3h, 6h, 24h, or indefinite")
            
            duration_hours, duration_minutes = duration_map[duration]
            
            # Create event data
            event_data = {
                "user_id": ctx.author.id,
                "start_time": datetime.utcnow(),
                "duration_minutes": duration_minutes,  # -1 means indefinite
                "paused": False,
                "indefinite": duration_minutes == -1
            }
            
            # Save to database
            await forest_cog.spawn_collection.insert_one({"forest_event_data": event_data})
            
            # Add to active events
            forest_cog.active_forest_event = event_data
            
            embed = discord.Embed(
                title="🌳 Global Forest Event Started!",
                description=f"Forest event is now active across **ALL servers**!",
                color=0x228B22
            )
            
            if duration_minutes == -1:
                embed.add_field(name="Duration", value="♾️ Indefinite", inline=True)
            else:
                embed.add_field(name="Duration", value=f"{duration_hours}h", inline=True)
            
            embed.add_field(name="Spawn Chance", value=f"{forest_cog.forest_spawn_chance * 100}%", inline=True)
            embed.add_field(name="Scope", value="Global (All Servers)", inline=True)
            embed.add_field(
                name="🌿 How it works", 
                value="Forest Pokemon will spawn naturally like regular Pokemon during the event period across all servers!",
                inline=False
            )
            
            await ctx.reply(embed=embed)
        
        elif action == "stop":
            # Get forest event cog
            forest_cog = self.bot.get_cog("ForestEventSystem")
            if not forest_cog:
                return await ctx.reply("❌ Forest event system not loaded!")
            
            # Remove from database
            await forest_cog.spawn_collection.delete_one({"forest_event_data": {"$exists": True}})
            
            # Remove from active events
            forest_cog.active_forest_event = None
            
            embed = discord.Embed(
                title="🛑 Forest Event Stopped",
                description="Global forest event has been stopped across all servers.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
        
        elif action == "spawn":
            if not channel:
                return await ctx.reply("❌ Please provide a channel!")
            
            # Get forest event cog
            forest_cog = self.bot.get_cog("ForestEventSystem")
            if not forest_cog:
                return await ctx.reply("❌ Forest event system not loaded!")
            
            # Force spawn
            await forest_cog._handle_forest_spawn_prefix(ctx)
        
        elif action == "status":
            # Get forest event cog
            forest_cog = self.bot.get_cog("ForestEventSystem")
            if not forest_cog:
                return await ctx.reply("❌ Forest event system not loaded!")
            
            if not forest_cog.active_forest_event:
                embed = discord.Embed(
                    title="🌳 Forest Event Status",
                    description="No active forest event.",
                    color=0x808080
                )
                return await ctx.reply(embed=embed)
            
            event_data = forest_cog.active_forest_event
            
            remaining_time = forest_cog._get_remaining_time(event_data)
            
            # Handle indefinite time display
            if remaining_time == -1:
                time_str = "♾️ Indefinite"
            else:
                hours, remainder = divmod(remaining_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    time_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
            
            status = "⏸️ Paused" if event_data.get("paused", False) else "▶️ Active"
            
            embed = discord.Embed(
                title="🌳 Global Forest Event Status",
                color=0x228B22
            )
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Time Remaining", value=time_str, inline=True)
            embed.add_field(name="Spawn Chance", value=f"{forest_cog.forest_spawn_chance * 100}%", inline=True)
            embed.add_field(name="Scope", value="Global (All Servers)", inline=True)
            embed.add_field(name="Started By", value=f"<@{event_data['user_id']}>", inline=True)
            
            await ctx.reply(embed=embed)
        
        else:
            await ctx.reply("❌ Invalid action! Use: `start`, `stop`, `spawn`, or `status`")
    
    # ═══════════════════════════════════════════════════════════════════════════════════════

class GauntletBattleView(View):
    def __init__(self, event_cog, battle_cog, user_id, user_team, enemy_team, enemy_name):
        super().__init__(timeout=300)
        self.event_cog = event_cog
        self.battle_cog = battle_cog
        self.user_id = user_id
        self.user_team = user_team
        self.enemy_team = enemy_team
        self.enemy_name = enemy_name

    @discord.ui.button(label="⚔️ Start Battle!", style=discord.ButtonStyle.success)
    async def start_battle(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
        
        # Get battle data from active battles
        if self.user_id not in self.event_cog.active_battles:
            return await interaction.response.send_message("❌ Battle session expired!", ephemeral=True)
        
        battle_data = self.event_cog.active_battles[self.user_id]
        floor = battle_data["floor"]
        is_boss = battle_data["is_boss"]
        
        # Create boss data format for BattleManager
        boss_data = {
            "name": self.enemy_name,
            "title": self.enemy_name,  # Battle system expects this field
            "reward_credits": 0,  # No credits for gauntlet
            "team": []
        }
        
        # Convert enemy team to boss data format
        for pokemon in self.enemy_team:
            boss_pokemon = {
                "pokemon_id": pokemon["pokemon_id"],
                "name": pokemon["name"],
                "level": pokemon["level"],
                "nature": "Hardy",
                "ability": "Unknown",
                "stats": {
                    "hp": pokemon["stats"]["hp"],
                    "attack": pokemon["stats"]["attack"],
                    "defense": pokemon["stats"]["defense"],
                    "sp_attack": pokemon["stats"]["sp_attack"],
                    "sp_defense": pokemon["stats"]["sp_defense"],
                    "speed": pokemon["stats"]["speed"]
                },
                "moves": pokemon["moves"]
            }
            boss_data["team"].append(boss_pokemon)
        
        # Import BattleManager from battle cog
        from .battle import BattleManager, BattleView
        
        # Create battle manager with proper format
        battle_manager = BattleManager(self.user_id, boss_data, self.user_team)
        
        # Store in battle cog's active battles
        self.battle_cog.active_battles[self.user_id] = battle_manager
        
        # Create custom gauntlet battle manager to handle end results
        battle_manager._gauntlet_data = {
            "event_cog": self.event_cog,
            "floor": floor,
            "is_boss": is_boss
        }
        
        # Override the end_battle method to handle gauntlet completion
        original_end_battle = battle_manager.end_battle
        
        async def gauntlet_end_battle(interaction, victory):
            # Clean up from battle cog first
            if self.user_id in self.battle_cog.active_battles:
                del self.battle_cog.active_battles[self.user_id]
            
            # Handle gauntlet-specific completion
            if victory:
                shards_earned, coins_earned, shard_type, next_floor = await self.event_cog.complete_battle(
                    self.user_id, True, floor, is_boss
                )
                
                shard_emojis = {
                    "infernal": "🔥", "frost": "❄️", "storm": "⚡", 
                    "sea": "🌊", "dragon": "🐉"
                }
                shard_emoji = shard_emojis.get(shard_type, "💎")
                
                embed = discord.Embed(
                    title="🎉 Gauntlet Victory!",
                    description=f"You defeated **{self.enemy_name}** on Floor {floor}!",
                    color=0x00FF00
                )
                
                rewards_text = f"{shard_emoji} +{shards_earned} {shard_type.title()} Shards\n💰 +{coins_earned} coins"
                if next_floor == 1 and floor == 100:
                    rewards_text += "\n🏆 **Gauntlet Completed! Starting new run...**"
                
                embed.add_field(name="Rewards", value=rewards_text, inline=False)
                embed.add_field(name="Next Floor", value=f"Floor {next_floor}", inline=False)
            else:
                await self.event_cog.complete_battle(self.user_id, False, floor, is_boss)
                embed = discord.Embed(
                    title="💀 Gauntlet Defeat...",
                    description=f"**{self.enemy_name}** proved too strong this time.",
                    color=0xFF0000
                )
                embed.add_field(
                    name="Try Again",
                    value="Rest up and challenge this floor again when ready!",
                    inline=False
                )
            
            # Clean up gauntlet battle data
            if self.user_id in self.event_cog.active_battles:
                del self.event_cog.active_battles[self.user_id]
            
            # Try to update the battle message
            try:
                if hasattr(battle_manager, 'battle_message') and battle_manager.battle_message:
                    await battle_manager.battle_message.edit(embed=embed, view=None)
                else:
                    # Fallback: try interaction response first
                    try:
                        await interaction.response.edit_message(embed=embed, view=None)
                    except (discord.NotFound, discord.HTTPException):
                        # Final fallback: send new message (don't pass view=None to followup)
                        await interaction.followup.send(embed=embed)
            except (discord.NotFound, discord.HTTPException):
                # Final fallback: send new message
                try:
                    await interaction.followup.send(embed=embed)
                except discord.HTTPException:
                    # If all else fails, just log it
                    print(f"Failed to send gauntlet battle result for user {self.user_id}")
        
        # Replace the end_battle method
        battle_manager.end_battle = gauntlet_end_battle
        
        # Start the actual battle
        view = BattleView(battle_manager, self.user_id)
        battle_image = await battle_manager.create_battle_image()
        
        # Respond to the interaction first, then edit
        await interaction.response.send_message("⚔️ Starting battle...", ephemeral=True)
        
        # Edit the original message (not the interaction response)
        try:
            original_message = interaction.message
            if original_message:
                await original_message.edit(content="", view=view, attachments=[battle_image])
                battle_manager.battle_message = original_message
            else:
                # Fallback: send new message
                msg = await interaction.followup.send(content="", view=view, file=battle_image)
                battle_manager.battle_message = msg
        except discord.HTTPException:
            # Fallback: send new message
            msg = await interaction.followup.send(content="", view=view, file=battle_image)
            battle_manager.battle_message = msg

class GauntletStatsView(View):
    def __init__(self, event_cog, user_id, shards):
        super().__init__(timeout=300)
        self.event_cog = event_cog
        self.user_id = user_id
        self.shards = shards

    @discord.ui.button(label="🌑 Combine Shadow Legendary", style=discord.ButtonStyle.primary, emoji="⚡")
    async def combine_legendary(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your gauntlet!", ephemeral=True)
        
        # Create dropdown view for selecting legendary
        view = ShadowLegendarySelect(self.event_cog, self.user_id, self.shards)
        
        embed = discord.Embed(
            title="🌑 Select Shadow Legendary to Combine",
            description="Choose which Shadow Legendary you want to create using your shards:",
            color=0x8B0000
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ShadowLegendarySelect(View):
    def __init__(self, event_cog, user_id, shards):
        super().__init__(timeout=60)
        self.event_cog = event_cog
        self.user_id = user_id
        self.shards = shards
        
        # Add dropdown
        self.add_item(LegendaryDropdown(event_cog, user_id, shards))

class LegendaryDropdown(discord.ui.Select):
    def __init__(self, event_cog, user_id, shards):
        self.event_cog = event_cog
        self.user_id = user_id
        self.shards = shards
        
        # Define legendary options
        legendaries = [
            {"name": "Shadow Articuno", "id": 1011, "cost_type": "frost", "cost": 60, "emoji": "❄️"},
            {"name": "Shadow Moltres", "id": 1012, "cost_type": "infernal", "cost": 60, "emoji": "🔥"},
            {"name": "Shadow Zapdos", "id": 1013, "cost_type": "storm", "cost": 60, "emoji": "⚡"},
            {"name": "Shadow Lugia", "id": 1014, "cost_type": "sea", "cost": 100, "emoji": "🌊"},
            {"name": "Shadow Rayquaza", "id": 1015, "cost_type": "dragon", "cost": 100, "emoji": "🐉"}
        ]
        
        options = []
        for legendary in legendaries:
            available = shards.get(legendary["cost_type"], 0)
            can_afford = available >= legendary["cost"]
            
            description = f"{legendary['cost']} {legendary['cost_type'].title()} Shards (You have: {available})"
            if not can_afford:
                description += " - ❌ Insufficient shards"
            else:
                description += " - ✅ Available"
            
            options.append(discord.SelectOption(
                label=legendary["name"],
                value=str(legendary["id"]),
                description=description,
                emoji=legendary["emoji"]
            ))
        
        super().__init__(
            placeholder="Choose a Shadow Legendary to combine...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your selection!", ephemeral=True)
        
        selected_id = int(self.values[0])
        
        # Get legendary info
        legendary_info = {
            1011: {"name": "Shadow Articuno", "cost_type": "frost", "cost": 60},
            1012: {"name": "Shadow Moltres", "cost_type": "infernal", "cost": 60},
            1013: {"name": "Shadow Zapdos", "cost_type": "storm", "cost": 60},
            1014: {"name": "Shadow Lugia", "cost_type": "sea", "cost": 100},
            1015: {"name": "Shadow Rayquaza", "cost_type": "dragon", "cost": 100}
        }
        
        legendary = legendary_info[selected_id]
        available = self.shards.get(legendary["cost_type"], 0)
        
        if available < legendary["cost"]:
            embed = discord.Embed(
                title="❌ Insufficient Shards",
                description=f"You need {legendary['cost']} {legendary['cost_type'].title()} shards but only have {available}.",
                color=0xFF0000
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        
        # Create confirmation view
        view = NewConfirmCombineView(self.event_cog, self.user_id, legendary["name"], selected_id, legendary)
        
        shard_emojis = {"infernal": "🔥", "frost": "❄️", "storm": "⚡", "sea": "🌊", "dragon": "🐉"}
        emoji = shard_emojis.get(legendary["cost_type"], "💎")
        
        embed = discord.Embed(
            title=f"🌑 Confirm {legendary['name']} Creation",
            description=f"Are you sure you want to create **{legendary['name']}**?\n\n"
                       f"**Cost:** {emoji} {legendary['cost']} {legendary['cost_type'].title()} Shards\n"
                       f"**You have:** {available} shards\n"
                       f"**After creation:** {available - legendary['cost']} shards remaining\n\n"
                       f"The Pokemon will be added to your collection at **Level 70** with random IVs!",
            color=0x8B0000
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class NewConfirmCombineView(View):
    def __init__(self, event_cog, user_id, legendary_name, pokemon_id, legendary_data):
        super().__init__(timeout=60)
        self.event_cog = event_cog
        self.user_id = user_id
        self.legendary_name = legendary_name
        self.pokemon_id = pokemon_id
        self.legendary_data = legendary_data

    @discord.ui.button(label="✅ Create Pokemon", style=discord.ButtonStyle.success)
    async def confirm_combine(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your combination!", ephemeral=True)
        
        # Check shards again
        profile = await self.event_cog.ensure_gauntlet_profile(self.user_id)
        current_shards = profile["gauntlet"]["shards"].get(self.legendary_data["cost_type"], 0)
        
        if current_shards < self.legendary_data["cost"]:
            embed = discord.Embed(
                title="❌ Insufficient Shards",
                description="You don't have enough shards anymore!",
                color=0xFF0000
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        
        # Deduct shards
        await self.event_cog.user_profiles.update_one(
            {"user_id": self.user_id},
            {"$inc": {f"gauntlet.shards.{self.legendary_data['cost_type']}": -self.legendary_data["cost"]}}
        )
        
        # Create the Pokemon
        pokemon_id = await self.event_cog.create_shadow_pokemon(
            self.user_id, self.legendary_name, self.pokemon_id
        )
        
        embed = discord.Embed(
            title="🎉 Shadow Legendary Created!",
            description=f"**{self.legendary_name}** has been successfully created and added to your Pokemon collection!\n\n"
                       f"**Level:** 70\n"
                       f"**Location:** Check your Pokemon with `!pokemon` or `!party`\n"
                       f"**Special:** This Pokemon has event-exclusive Shadow typing!",
            color=0x00FF00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_combine(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your combination!", ephemeral=True)
        
        embed = discord.Embed(
            title="❌ Creation Cancelled",
            description="Your shards are safe!",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ShardConvertView(View):
    def __init__(self, event_cog, user_id, total_shards, coins_to_receive):
        super().__init__(timeout=60)
        self.event_cog = event_cog
        self.user_id = user_id
        self.total_shards = total_shards
        self.coins_to_receive = coins_to_receive

    @discord.ui.button(label="✅ Convert Shards", style=discord.ButtonStyle.success)
    async def confirm_convert(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your conversion!", ephemeral=True)
        
        # Double-check shards still exist
        profile = await self.event_cog.ensure_gauntlet_profile(self.user_id)
        current_shards = profile["gauntlet"]["shards"]
        current_total = sum(current_shards.values())
        
        if current_total == 0:
            embed = discord.Embed(
                title="❌ No Shards Found",
                description="You don't have any shards to convert!",
                color=0xFF0000
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        
        if current_total != self.total_shards:
            # Shards changed, recalculate
            new_coins = current_total * 500
            embed = discord.Embed(
                title="⚠️ Shard Amount Changed",
                description=f"Your shard count changed! You now have {current_total} shards.\n"
                           f"This would give you {new_coins:,} coins instead.\n"
                           f"Please try the conversion again.",
                color=0xFFA500
            )
            return await interaction.response.edit_message(embed=embed, view=None)
        
        # Perform the conversion
        # Reset all shards to 0 and add coins
        await self.event_cog.user_profiles.update_one(
            {"user_id": self.user_id},
            {
                "$set": {
                    "gauntlet.shards.infernal": 0,
                    "gauntlet.shards.frost": 0,
                    "gauntlet.shards.storm": 0,
                    "gauntlet.shards.sea": 0,
                    "gauntlet.shards.dragon": 0
                },
                "$inc": {"coins": self.coins_to_receive}
            }
        )
        
        embed = discord.Embed(
            title="🎉 Conversion Successful!",
            description=f"Successfully converted **{self.total_shards} shards** into **{self.coins_to_receive:,} coins**!\n\n"
                       f"💰 Coins added to your balance\n"
                       f"💎 All shards have been removed\n\n"
                       f"Thank you for participating in the Shadow Gauntlet event!",
            color=0x00FF00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_convert(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your conversion!", ephemeral=True)
        
        embed = discord.Embed(
            title="❌ Conversion Cancelled",
            description="Your shards remain unchanged.",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    pokemon_db = bot.pokemon_collection
    user_profiles_db = bot.db["user_profiles"]
    await bot.add_cog(EventSystem(bot, pokemon_db, user_profiles_db)) 