import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import io
from PIL import Image, ImageDraw, ImageFont


# Load Pokémon data
with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEMON_DATA = json.load(f)

with open("common.json", "r") as f:
    COMMON_POKEMON = json.load(f)

with open("uncommon.json", "r") as f:
    UNCOMMON_POKEMON = json.load(f)

with open("rare.json", "r") as f:
    RARE_POKEMON = json.load(f)

RARITY_CHANCES = {
    "common": 70,
    "uncommon": 20,
    "rare": 10
}

def is_spawnable_pokemon(pokemon_id):
    """Check if a Pokémon should be able to spawn (exclude Mega, Dynamax, custom)"""
    pokemon_id_str = str(pokemon_id)
    
    if pokemon_id_str not in POKEMON_DATA:
        return False
    
    pokemon_data = POKEMON_DATA[pokemon_id_str]
    pokemon_name = pokemon_data["name"].lower()
    
    if "mega" in pokemon_name or "gmax" in pokemon_name or "gigantamax" in pokemon_name:
        return False
    
    if pokemon_name.startswith("shadow-"):
        return False
    
    return True

def get_filtered_pokemon_list(pokemon_list):
    """Filter a list of Pokémon IDs to only include spawnable ones"""
    return [pokemon_id for pokemon_id in pokemon_list if is_spawnable_pokemon(pokemon_id)]

FILTERED_COMMON = get_filtered_pokemon_list(COMMON_POKEMON)
FILTERED_UNCOMMON = get_filtered_pokemon_list(UNCOMMON_POKEMON)
FILTERED_RARE = get_filtered_pokemon_list(RARE_POKEMON)

def get_random_pokemon_id():
    roll = random.randint(1, 100)
    if roll <= RARITY_CHANCES["rare"]:
        return random.choice(FILTERED_RARE), "rare"
    elif roll <= RARITY_CHANCES["rare"] + RARITY_CHANCES["uncommon"]:
        return random.choice(FILTERED_UNCOMMON), "uncommon"
    else:
        return random.choice(FILTERED_COMMON), "common"

class IncenseSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pokemon_collection = bot.pokemon_collection
        self.user_collection = bot.db["user_profiles"]  # Use user_profiles like shop.py
        self.spawn_collection = bot.spawn_collection
        
        # Incense data will be stored in spawn_collection with "incense_data" field
        self.active_incenses = {}  # channel_id: incense_data
        self.incense_tasks = {} 
         # channel_id: asyncio.Task
        
        # Load alternative names for catch system
        self.altname_map = {}
        try:
           with open("pokemon_altnames.json", "r", encoding="utf-8") as f:
                alt_list = json.load(f)
                for entry in alt_list:
                    canonical = entry["name"].lower()
                    for value in entry.values():
                        if isinstance(value, str):
                            self.altname_map[value.lower()] = canonical
        except Exception as e:
            print(f"Failed to load alternative names: {e}")
        
        # Auto-generate base name mappings for easier catching
        self._generate_base_name_mappings()

        
        # Start the incense manager task
        self.incense_manager.start()

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.incense_manager.cancel()
        for task in self.incense_tasks.values():
            task.cancel()

    async def get_user_balance(self, user_id):
        """Get user's coin and diamond balance"""
        profile = await self.user_collection.find_one({"user_id": user_id})
        if not profile:
            # Create new profile if it doesn't exist
            profile = {
                "user_id": user_id,
                "coins": 1000,  # Starting coins like shop.py
                "diamonds": 0
            }
            await self.user_collection.insert_one(profile)
            return 1000, 0
        return profile.get("coins", 0), profile.get("diamonds", 0)

    async def update_user_balance(self, user_id, coins_change=0, diamonds_change=0):
        """Update user's balance"""
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"coins": coins_change, "diamonds": diamonds_change}},
            upsert=True
        )

    @tasks.loop(seconds=5)
    async def incense_manager(self):
        """Main task to manage all incenses"""
        try:
            # Load active incenses from database
            incense_docs = await self.spawn_collection.find({"incense_data": {"$exists": True}}).to_list(length=None)
            
            for doc in incense_docs:
                incense_data = doc["incense_data"]
                channel_id = incense_data["channel_id"]
                
                # Check if incense is still active
                if not self._is_incense_active(incense_data):
                    # Remove expired incense
                    await self.spawn_collection.delete_one({"_id": doc["_id"]})
                    if channel_id in self.active_incenses:
                        del self.active_incenses[channel_id]
                    if channel_id in self.incense_tasks:
                        self.incense_tasks[channel_id].cancel()
                        del self.incense_tasks[channel_id]
                    continue
                
                # Update local cache
                self.active_incenses[channel_id] = incense_data
                
                # Start incense task if not already running
                if channel_id not in self.incense_tasks or self.incense_tasks[channel_id].done():
                    self.incense_tasks[channel_id] = asyncio.create_task(self._run_incense(channel_id))
                    
        except Exception as e:
            print(f"Error in incense manager: {e}")

    @incense_manager.before_loop
    async def before_incense_manager(self):
        await self.bot.wait_until_ready()

    def _is_incense_active(self, incense_data):
        """Check if an incense is still active"""
        if incense_data.get("paused", False):
            return True  # Paused incenses are still "active"
        
        now = datetime.utcnow()
        start_time = incense_data["start_time"]
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        duration_minutes = incense_data["duration_minutes"]
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        return now < end_time and incense_data.get("spawns_left", 0) > 0

    def _get_remaining_time(self, incense_data):
        """Get remaining time for an incense"""
        if incense_data.get("paused", False):
            return incense_data.get("remaining_time", 0)
        
        now = datetime.utcnow()
        start_time = incense_data["start_time"]
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        duration_minutes = incense_data["duration_minutes"]
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        remaining = end_time - now
        return max(0, int(remaining.total_seconds()))

    async def _run_incense(self, channel_id):
        """Run incense spawning for a specific channel"""
        try:
            # Get the regular spawn system to check for active spawns
            spawn_cog = self.bot.get_cog("SpawnSystem")
            if not spawn_cog:
                print("❌ SpawnSystem cog not found!")
                return
                
            while channel_id in self.active_incenses:
                incense_data = self.active_incenses[channel_id]
                
                # Check if paused
                if incense_data.get("paused", False):
                    await asyncio.sleep(5)
                    continue
                
                # Check if expired or no spawns left
                if not self._is_incense_active(incense_data) or incense_data.get("spawns_left", 0) <= 0:
                    break
                
                # Always spawn a Pokemon every interval (don't check for active spawns)
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await self._spawn_incense_pokemon(channel, incense_data)
                    
                    # Decrease spawns left
                    incense_data["spawns_left"] -= 1
                    await self._update_incense_in_db(channel_id, incense_data)
                
                # Wait for the interval
                interval_seconds = incense_data["interval_seconds"]
                await asyncio.sleep(interval_seconds)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in incense task for channel {channel_id}: {e}")

    async def _spawn_incense_pokemon(self, channel, incense_data):
        """Spawn a Pokémon from incense"""
        try:
            # Get the regular spawn system to integrate with its catch handling
            spawn_cog = self.bot.get_cog("SpawnSystem")
            if not spawn_cog:
                print("❌ SpawnSystem cog not found!")
                return
            
            # Always clear any existing spawn in this channel first (both regular and incense)
            # This ensures we spawn every interval regardless of catches
            if channel.id in spawn_cog.active_spawns:
                print(f"🧹 Clearing previous spawn in {channel.name} for new incense spawn")
                del spawn_cog.active_spawns[channel.id]
            
            # Check if forest event is active (same logic as regular spawn system)
            forest_cog = self.bot.get_cog("ForestEventSystem")
            is_forest_pokemon = False
            
            if forest_cog and forest_cog.should_spawn_forest_pokemon():
                # Spawn forest Pokemon
                pokemon_id, pokemon_name, pokemon_data = forest_cog.get_random_forest_pokemon()
                is_forest_pokemon = True
                rarity = "forest"  # Special rarity for forest Pokemon
                print(f"🌳 Incense spawning forest Pokemon: {pokemon_name}")
            else:
                # Get random regular Pokémon
                pokemon_id, rarity = get_random_pokemon_id()
                pokemon_data = POKEMON_DATA[str(pokemon_id)]
                print(f"🧪 Incense spawning regular Pokemon: {pokemon_data['name']}")
            
            # Create spawn image
            spawn_image = await self._create_spawn_image(pokemon_data)
            
            # Create embed similar to regular spawn system
            if is_forest_pokemon:
                embed = discord.Embed(
                    title="🌿 A wild Forest Pokemon has appeared!",
                    description=f"Guess the pokémon and type `@Botachu catch <pokémon>` to catch it!",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="🌿 A wild pokémon has appeared!",
                    description=f"Guess the pokémon and type `@Botachu catch <pokémon>` to catch it!",
                    color=discord.Color.green()
                )
            
            # Add incense information
            remaining_time = self._get_remaining_time(incense_data)
            hours, remainder = divmod(remaining_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
            
            embed.add_field(
                name="🕐 Incense Timer",
                value=time_str,
                inline=True
            )
            embed.add_field(
                name="⏱️ Spawn Interval", 
                value=f"{incense_data['interval_seconds']}s",
                inline=True
            )
            embed.add_field(
                name="🎯 Spawns Left",
                value=f"{incense_data['spawns_left']}",
                inline=True
            )
            
            # Set footer based on spawn type
            if is_forest_pokemon:
                embed.set_footer(text="🌳 Forest Event • Incense • Special Pokemon Spawn")
            else:
                embed.set_footer(text="Powered by Incense • Botachu")
            
            # Send spawn message
            if spawn_image:
                file = discord.File(spawn_image, filename="spawn.png")
                embed.set_image(url="attachment://spawn.png")
                spawn_msg = await channel.send(embed=embed, file=file)
            else:
                spawn_msg = await channel.send(embed=embed)
            
            # Store spawn data in the REGULAR spawn system's active_spawns
            # This allows the regular catch system to handle incense catches
            spawn_cog.active_spawns[channel.id] = {
                "pokemon_name": pokemon_data["name"],
                "pokemon_id": pokemon_id,
                "pokemon_data": pokemon_data,
                "message_id": spawn_msg.id,
                "timestamp": datetime.utcnow(),
                "rarity": rarity,
                "source": "incense_forest" if is_forest_pokemon else "incense"  # Mark source type
            }
            
            if is_forest_pokemon:
                print(f"✨🌳 Incense spawned FOREST Pokemon {pokemon_data['name']} in {channel.name}")
            else:
                print(f"✨ Incense spawned {pokemon_data['name']} in {channel.name}")
            
        except Exception as e:
            print(f"Error spawning incense Pokémon: {e}")

    async def _create_spawn_image(self, pokemon_data):
        """Create spawn image (reuse from spawn system)"""
        try:
            background_path = "spawn.png"
            pokemon_sprite_path = f"full/{pokemon_data['id']}.png"
            
            if not os.path.exists(background_path) or not os.path.exists(pokemon_sprite_path):
                return None
            
            background = Image.open(background_path).convert("RGBA")
            pokemon_sprite = Image.open(pokemon_sprite_path).convert("RGBA")
            
            sprite_max_size = (400, 400)
            pokemon_sprite.thumbnail(sprite_max_size, Image.Resampling.LANCZOS)
            
            bg_width, bg_height = background.size
            sprite_width, sprite_height = pokemon_sprite.size
            
            x = (bg_width - sprite_width) // 2
            y = (bg_height - sprite_height) // 2
            
            background.paste(pokemon_sprite, (x, y), pokemon_sprite)
            
            img_byte_arr = io.BytesIO()
            background.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
        except Exception as e:
            print(f"Error creating spawn image: {e}")
            return None

    async def _update_incense_in_db(self, channel_id, incense_data):
        """Update incense data in database"""
        await self.spawn_collection.update_one(
            {"incense_data.channel_id": channel_id},
            {"$set": {"incense_data": incense_data}}
        )

    @commands.group(invoke_without_command=True)
    async def incense(self, ctx):
        """Incense system for time-based Pokémon spawning"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🧪 Incense System",
                description="**Available Commands:**\n"
                           f"`{ctx.prefix}incense buy <duration> <interval>` - Purchase incense\n"
                           f"`{ctx.prefix}incense pause` - Pause active incense\n"
                           f"`{ctx.prefix}incense resume` - Resume paused incense\n"
                           f"`{ctx.prefix}incense status` - Check incense status\n\n"
                           "**Duration Options:** 1h, 3h, 6h, 24h\n"
                           "**Interval Options:** 10s, 20s, 30s\n\n"
                           "🌳 **During forest events, incense can spawn forest Pokemon too!**",
                color=0x3498db
            )
            await ctx.send(embed=embed)

    @incense.command()
    async def buy(self, ctx, duration: Optional[str] = None, interval: Optional[str] = None):
        """Buy incense for this channel"""
        await self._handle_incense_buy_prefix(ctx, duration, interval)

    @incense.command()
    async def pause(self, ctx):
        """Pause active incense in this channel"""
        await self._handle_incense_pause_prefix(ctx)

    @incense.command()
    async def resume(self, ctx):
        """Resume paused incense in this channel"""
        await self._handle_incense_resume_prefix(ctx)

    @incense.command()
    async def status(self, ctx):
        """Check incense status in this channel"""
        await self._handle_incense_status_prefix(ctx)

    async def _handle_incense_buy_prefix(self, ctx, duration: Optional[str], interval: Optional[str]):
        """Handle incense purchase via prefix command"""
        if not duration or not interval:
            embed = discord.Embed(
                title="🧪 Incense Shop",
                description="**Duration Prices:**\n"
                           "• 1h: 2,500 coins\n"
                           "• 3h: 5,000 coins\n"
                           "• 6h: 10,000 coins\n"
                           "• 24h: 35,000 coins\n\n"
                           "**Interval Costs:**\n"
                           "• 10s: +2,000 coins\n"
                           "• 20s: +1,000 coins\n"
                           "• 30s: +500 coins\n\n"
                           f"**Usage:** `{ctx.prefix}incense buy <duration> <interval>`\n"
                           f"**Example:** `{ctx.prefix}incense buy 1h 20s`",
                color=0xe74c3c
            )
            return await ctx.send(embed=embed)

        # Check if incense already active in this channel
        if ctx.channel.id in self.active_incenses:
            return await ctx.send("❌ There's already an active incense in this channel!")

        # Validate inputs
        duration_costs = {"1h": 2500, "3h": 5000, "6h": 10000, "24h": 35000}
        interval_costs = {"10s": 2000, "20s": 1000, "30s": 500}
        
        if duration not in duration_costs:
            return await ctx.send("❌ Invalid duration! Use: 1h, 3h, 6h, or 24h")
        
        if interval not in interval_costs:
            return await ctx.send("❌ Invalid interval! Use: 10s, 20s, or 30s")
        
        duration_cost = duration_costs[duration]
        interval_cost = interval_costs[interval]
        total_cost = duration_cost + interval_cost

        # Check user balance
        coins, _ = await self.get_user_balance(ctx.author.id)
        if coins < total_cost:
            return await ctx.send(
                f"❌ You don't have enough coins! You need **{total_cost:,}** but only have **{coins:,}**."
            )

        # Create confirmation embed
        duration_map = {"1h": (1, 60), "3h": (3, 180), "6h": (6, 360), "24h": (24, 1440)}
        interval_map = {"10s": 10, "20s": 20, "30s": 30}
        
        duration_hours, duration_minutes = duration_map[duration]
        interval_seconds = interval_map[interval]
        
        # Calculate total spawns (conservative estimate)
        total_spawns = (duration_minutes * 60) // interval_seconds
        
        embed = discord.Embed(
            title="🧪 Incense Purchase Confirmation",
            description=f"**Duration:** {duration_hours} hour{'s' if duration_hours > 1 else ''}\n"
                       f"**Interval:** {interval_seconds} seconds\n"
                       f"**Estimated Spawns:** ~{total_spawns}\n"
                       f"**Total Cost:** {total_cost:,} coins",
            color=0xf39c12
        )
        embed.add_field(name="Current Balance", value=f"{coins:,} coins", inline=True)
        embed.add_field(name="After Purchase", value=f"{coins - total_cost:,} coins", inline=True)
        embed.set_footer(text="This incense will be active in this channel only")

        view = IncensePurchaseView(self, ctx.author.id, ctx.channel.id, 
                                  duration_minutes, interval_seconds, total_cost, total_spawns)
        await ctx.send(embed=embed, view=view)

    async def _handle_incense_pause_prefix(self, ctx):
        """Handle incense pause via prefix command"""
        channel_id = ctx.channel.id
        
        if channel_id not in self.active_incenses:
            return await ctx.send("❌ No active incense in this channel!")
        
        incense_data = self.active_incenses[channel_id]
        
        if incense_data["user_id"] != ctx.author.id:
            return await ctx.send("❌ You can only pause your own incense!")
        
        if incense_data.get("paused", False):
            return await ctx.send("❌ Incense is already paused!")
        
        # Pause the incense
        incense_data["paused"] = True
        incense_data["pause_time"] = datetime.utcnow()
        incense_data["remaining_time"] = self._get_remaining_time(incense_data)
        
        await self._update_incense_in_db(channel_id, incense_data)
        
        await ctx.send(f"⏸️ Incense paused! Use `{ctx.prefix}incense resume` to continue.")

    async def _handle_incense_resume_prefix(self, ctx):
        """Handle incense resume via prefix command"""
        channel_id = ctx.channel.id
        
        if channel_id not in self.active_incenses:
            return await ctx.send("❌ No active incense in this channel!")
        
        incense_data = self.active_incenses[channel_id]
        
        if incense_data["user_id"] != ctx.author.id:
            return await ctx.send("❌ You can only resume your own incense!")
        
        if not incense_data.get("paused", False):
            return await ctx.send("❌ Incense is not paused!")
        
        # Resume the incense
        incense_data["paused"] = False
        remaining_time = incense_data.get("remaining_time", 0)
        incense_data["start_time"] = datetime.utcnow() - timedelta(
            minutes=incense_data["duration_minutes"] - (remaining_time // 60)
        )
        
        if "pause_time" in incense_data:
            del incense_data["pause_time"]
        if "remaining_time" in incense_data:
            del incense_data["remaining_time"]
        
        await self._update_incense_in_db(channel_id, incense_data)
        
        await ctx.send("▶️ Incense resumed!")

    async def _handle_incense_status_prefix(self, ctx):
        """Handle incense status check via prefix command"""
        channel_id = ctx.channel.id
        
        if channel_id not in self.active_incenses:
            return await ctx.send("❌ No active incense in this channel!")
        
        incense_data = self.active_incenses[channel_id]
        
        remaining_time = self._get_remaining_time(incense_data)
        hours, remainder = divmod(remaining_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
        
        status = "⏸️ Paused" if incense_data.get("paused", False) else "▶️ Active"
        
        embed = discord.Embed(
            title="🧪 Incense Status",
            color=0x3498db
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Time Remaining", value=time_str, inline=True)
        embed.add_field(name="Spawn Interval", value=f"{incense_data['interval_seconds']}s", inline=True)
        embed.add_field(name="Spawns Left", value=incense_data["spawns_left"], inline=True)
        embed.add_field(name="Owner", value=f"<@{incense_data['user_id']}>", inline=True)
        
        await ctx.send(embed=embed)

    def _generate_base_name_mappings(self):
        """Auto-generate base name mappings for Pokemon names"""
        try:
            # Load Pokemon data to generate mappings
            with open("pokedex.json", "r", encoding="utf-8") as f:
                pokemon_data = json.load(f)
            
            for pokemon_id, data in pokemon_data.items():
                if "name" not in data:
                    continue
                
                full_name = data["name"].lower().replace("-", " ")
                base_name = self._extract_base_name(full_name)
                
                # Only add mapping if base name is different from full name
                if base_name != full_name and len(base_name) > 2:  # Avoid very short base names
                    self.altname_map[base_name] = full_name
                    # Also map with hyphens for consistency
                    base_name_hyphen = base_name.replace(" ", "-")
                    full_name_hyphen = full_name.replace(" ", "-")
                    if base_name_hyphen != full_name_hyphen:
                        self.altname_map[base_name_hyphen] = full_name_hyphen
            
            print(f"✅ Incense: Generated {len([k for k in self.altname_map.keys() if self._is_auto_generated(k)])} base name mappings")
        except Exception as e:
            print(f"Failed to generate base name mappings in incense: {e}")

    def _extract_base_name(self, pokemon_name):
        """Extract base Pokemon name from full name"""
        name = pokemon_name.strip().lower()
        
        # Common prefixes to remove (event Pokemon, regional forms, etc.)
        prefixes_to_remove = [
            "sylvan", "verdant", "thorned", "twilight", "briar", "blooming", "spore",
            "shadow", "mega", "gigantamax", "gmax", "primal", "origin", "zen", "therian",
            "incarnate", "resolute", "ordinary", "pirouette", "aria", "step", "blade",
            "shield", "crowned", "ice", "shadow rider", "ice rider", "rapid strike",
            "single strike", "white striped", "blue striped", "red striped", "orange",
            "yellow", "green", "blue", "indigo", "violet", "roaming", "complete",
            "10 percent", "50 percent", "power construct", "disguised", "busted",
            "school", "solo", "meteor", "dawn wings", "dusk mane", "ultra",
            "alolan", "galarian", "hisuian", "paldean", "kantonian", "johtonian"
        ]
        
        # Common suffixes to remove (forms, sizes, etc.)
        suffixes_to_remove = [
            "two segment", "three segment", "four segment", "droopy", "curly", "stretchy",
            "plant", "sandy", "trash", "wash", "heat", "frost", "fan", "mow", "altered",
            "origin", "land", "sky", "normal", "attack", "defense", "speed", "red",
            "blue", "yellow", "orange", "pink", "green", "violet", "indigo", "white",
            "black", "brown", "gray", "grey", "silver", "gold", "copper", "steel",
            "rock", "ground", "flying", "poison", "fighting", "psychic", "bug", "ghost",
            "fire", "water", "grass", "electric", "ice", "dragon", "dark", "fairy",
            "normal mode", "zen mode", "standard mode", "therian forme", "incarnate forme",
            "male", "female", "size s", "size m", "size l", "size xl", "size xs",
            "small", "medium", "large", "super size", "amped", "low key", "full belly",
            "hangry", "gulping", "gorging", "noice", "antique", "phony", "crowned sword",
            "crowned shield", "eternamax", "gigantamax factor", "dynamax factor"
        ]
        
        # Split name into words
        words = name.split()
        if not words:
            return name
        
        # Remove prefixes
        while words and any(words[0].startswith(prefix) or " ".join(words[:len(prefix.split())]) == prefix 
                           for prefix in prefixes_to_remove):
            # Find the longest matching prefix
            longest_match = 0
            for prefix in prefixes_to_remove:
                prefix_words = prefix.split()
                if len(prefix_words) <= len(words):
                    if " ".join(words[:len(prefix_words)]) == prefix:
                        longest_match = max(longest_match, len(prefix_words))
            
            if longest_match > 0:
                words = words[longest_match:]
            else:
                break
        
        # Remove suffixes
        while words and any(" ".join(words[-len(suffix.split()):]) == suffix 
                           for suffix in suffixes_to_remove):
            # Find the longest matching suffix
            longest_match = 0
            for suffix in suffixes_to_remove:
                suffix_words = suffix.split()
                if len(suffix_words) <= len(words):
                    if " ".join(words[-len(suffix_words):]) == suffix:
                        longest_match = max(longest_match, len(suffix_words))
            
            if longest_match > 0:
                words = words[:-longest_match]
            else:
                break
        
        # Return the base name
        base_name = " ".join(words) if words else name
        return base_name.strip()

    def _is_auto_generated(self, key):
        """Check if an altname mapping was auto-generated (simple heuristic)"""
        # This is just for logging purposes - check if it's likely an auto-generated mapping
        return len(key.split()) <= 2 and not key.endswith("'s") and not key.isdigit()

class IncensePurchaseView(discord.ui.View):
    def __init__(self, incense_cog, user_id, channel_id, duration_minutes, interval_seconds, cost, total_spawns):
        super().__init__(timeout=60)
        self.incense_cog = incense_cog
        self.user_id = user_id
        self.channel_id = channel_id
        self.duration_minutes = duration_minutes
        self.interval_seconds = interval_seconds
        self.cost = cost
        self.total_spawns = total_spawns

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.green, emoji="🧪")
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your purchase!", ephemeral=True)

        # Double-check balance
        coins, _ = await self.incense_cog.get_user_balance(self.user_id)
        if coins < self.cost:
            return await interaction.response.send_message("❌ You no longer have enough coins!", ephemeral=True)

        # Deduct coins
        await self.incense_cog.update_user_balance(self.user_id, coins_change=-self.cost)

        # Create incense data
        incense_data = {
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "start_time": datetime.utcnow(),
            "duration_minutes": self.duration_minutes,
            "interval_seconds": self.interval_seconds,
            "spawns_left": self.total_spawns,
            "paused": False
        }

        # Save to database
        await self.incense_cog.spawn_collection.insert_one({"incense_data": incense_data})
        
        # Add to active incenses
        self.incense_cog.active_incenses[self.channel_id] = incense_data

        embed = discord.Embed(
            title="🧪 Incense Activated!",
            description=f"Your incense is now active in <#{self.channel_id}>!",
            color=0x2ecc71
        )
        embed.add_field(name="Duration", value=f"{self.duration_minutes // 60}h", inline=True)
        embed.add_field(name="Interval", value=f"{self.interval_seconds}s", inline=True)
        embed.add_field(name="Total Spawns", value=self.total_spawns, inline=True)

        # Disable the button
        button.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your purchase!", ephemeral=True)

        embed = discord.Embed(
            title="❌ Purchase Cancelled",
            description="Incense purchase has been cancelled.",
            color=0xe74c3c
        )
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(IncenseSystem(bot)) 