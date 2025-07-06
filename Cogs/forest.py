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

# Forest event Pokemon IDs
FOREST_POKEMON = {
    "10283": "verdant charizard",
    "10284": "thorned aegislash", 
    "10285": "twilight lunala",
    "10286": "briar elektrike",
    "10287": "rhydon forestcoat",
    "10288": "blooming mawile",
    "10289": "sylvan ponyta",
    "10290": "spore dreepy"
}

class ForestEventSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pokemon_collection = bot.pokemon_collection
        self.user_collection = bot.db["user_profiles"]
        self.spawn_collection = bot.spawn_collection
        
        # Forest event data will be stored in spawn_collection with "forest_event_data" field
        self.active_forest_event = None  # Single global event data
        self.forest_spawn_chance = 0.15 
        # 15% chance for forest Pokemon during event
        
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
        
        # Start the event checker task
        self.event_checker.start()

    async def load_forest_event(self):
        """Load forest event data from database on startup"""
        try:
            event_data = await self.spawn_collection.find_one({"forest_event_data": {"$exists": True}})
            if event_data and "forest_event_data" in event_data:
                self.active_forest_event = event_data["forest_event_data"]
                
                # Convert string timestamps back to datetime objects if needed
                if isinstance(self.active_forest_event.get("start_time"), str):
                    self.active_forest_event["start_time"] = datetime.fromisoformat(self.active_forest_event["start_time"])
                
                print(f"✅ Loaded active forest event from database (remaining time: {self._get_remaining_time(self.active_forest_event)}s)")
        except Exception as e:
            print(f"Error loading forest event: {e}")

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
            
            print(f"✅ Forest: Generated {len([k for k in self.altname_map.keys() if self._is_auto_generated(k)])} base name mappings")
        except Exception as e:
            print(f"Failed to generate base name mappings in forest: {e}")

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

    async def get_user_balance(self, user_id):
        """Get user's coin and diamond balance"""
        profile = await self.user_collection.find_one({"user_id": user_id})
        if not profile:
            profile = {
                "user_id": user_id,
                "coins": 1000,
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

    def _is_forest_event_active(self, event_data):
        """Check if a forest event is still active"""
        if not event_data:
            return False
            
        if event_data.get("paused", False):
            return True  # Paused events are still "active"
        
        # Check if event is indefinite
        duration_minutes = event_data.get("duration_minutes", 0)
        if duration_minutes == -1 or event_data.get("indefinite", False):
            return True  # Indefinite events are always active until manually stopped
        
        now = datetime.utcnow()
        start_time = event_data["start_time"]
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        return now < end_time

    def _get_remaining_time(self, event_data):
        """Get remaining time for an event"""
        if not event_data:
            return 0
            
        if event_data.get("paused", False):
            return event_data.get("remaining_time", 0)
        
        # Check if event is indefinite
        duration_minutes = event_data.get("duration_minutes", 0)
        if duration_minutes == -1 or event_data.get("indefinite", False):
            return -1  # -1 indicates indefinite time
        
        now = datetime.utcnow()
        start_time = event_data["start_time"]
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        remaining = end_time - now
        return max(0, int(remaining.total_seconds()))

    def should_spawn_forest_pokemon(self):
        """Check if a forest Pokemon should spawn (based on chance)"""
        if not self.active_forest_event:
            return False
        
        if not self._is_forest_event_active(self.active_forest_event):
            return False
        
        if self.active_forest_event.get("paused", False):
            return False
        
        # 15% chance for forest Pokemon during event
        return random.random() < self.forest_spawn_chance

    def get_random_forest_pokemon(self):
        """Get a random forest Pokemon"""
        pokemon_id = random.choice(list(FOREST_POKEMON.keys()))
        pokemon_name = FOREST_POKEMON[pokemon_id]
        pokemon_data = POKEMON_DATA[pokemon_id]
        return pokemon_id, pokemon_name, pokemon_data

    @tasks.loop(minutes=1)
    async def event_checker(self):
        """Periodically check and update event status"""
        try:
            if self.active_forest_event:
                # Check if event has ended naturally
                if not self._is_forest_event_active(self.active_forest_event):
                    print("Forest event has ended naturally")
                    self.active_forest_event = None
                    await self._update_forest_event_in_db(None)
        except Exception as e:
            print(f"Error in event checker: {e}")

    @event_checker.before_loop
    async def before_event_checker(self):
        """Wait until bot is ready before starting checker"""
        await self.bot.wait_until_ready()
        await self.load_forest_event()  # Load any existing event from database

    @commands.group(invoke_without_command=True)
    async def forest(self, ctx):
        """Forest event system for special Pokemon spawning"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🌳 Forest Event System",
                description="**Available Commands:**\n"
                           f"`{ctx.prefix}forest status` - Check event status\n"
                           f"`{ctx.prefix}forest spawn` - Force spawn (admin only)\n\n"
                           "**Forest Pokemon:**\n"
                           "• Verdant Charizard\n"
                           "• Thorned Aegislash\n"
                           "• Twilight Lunala\n"
                           "• Briar Elektrike\n"
                           "• Rhydon Forestcoat\n"
                           "• Blooming Mawile\n"
                           "• Sylvan Ponyta\n"
                           "• Spore Dreepy\n\n"
                           "**How it works:**\n"
                           "Forest Pokemon spawn naturally like regular Pokemon during the event period!",
                color=0x228B22
            )
            await ctx.send(embed=embed)

    @forest.command()
    async def status(self, ctx):
        """Check forest event status"""
        if not self.active_forest_event:
            embed = discord.Embed(
                title="🌳 Forest Event Status",
                description="No active forest event.",
                color=0x808080
            )
            return await ctx.send(embed=embed)
        
        event_data = self.active_forest_event
        
        remaining_time = self._get_remaining_time(event_data)
        
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
            title="🌳 Forest Event Status",
            color=0x228B22
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Time Remaining", value=time_str, inline=True)
        embed.add_field(name="Spawn Chance", value=f"{self.forest_spawn_chance * 100}%", inline=True)
        embed.add_field(name="Started By", value=f"<@{event_data['user_id']}>", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name="forestinfo", aliases=["f"])
    async def forest_info(self, ctx):
        """Show forest event information for everyone"""
        embed = discord.Embed(
            title="🌿 WHISPERS OF THE VERDANT VEIL",
            description="Deep within the heart of the ancient forest lies the Verdant Veil, a mythical woodland said to be untouched by time. It is whispered among the elders that this forest isn't just alive — it is aware.\n\n"
                       "When the balance of nature is threatened by outsiders or corruption, the forest awakens its guardians: the mysterious spirit Twilight Lunala and the legendary beast Verdant Charizard, a dragon whose wings rustle like wind through leaves.\n\n"
                       "Strange phenomena have begun to surface in nearby routes: glowing pollen storms, enchanted roots binding trainers' feet, and whispers in languages no one remembers. Pokémon across the region are acting strangely, drawn to a call only they can hear.\n\n"
                       "The forest is stirring… and it has chosen you as its witness. Will you answer its call or be lost in the green forever?",
            color=0x228B22
        )
        
        # Add current catchable Pokemon field
        forest_pokemon_names = []
        for pokemon_id, pokemon_name in FOREST_POKEMON.items():
            # Get the display name from POKEMON_DATA
            if pokemon_id in POKEMON_DATA:
                display_name = POKEMON_DATA[pokemon_id]["name"].replace("-", " ").title()
                forest_pokemon_names.append(f"• {display_name}")
            else:
                forest_pokemon_names.append(f"• {pokemon_name.replace('-', ' ').title()}")
        
        embed.add_field(
            name="Current catchable pokemons:",
            value="\n".join(forest_pokemon_names),
            inline=False
        )
        
        # Add forest.png image
        try:
            if os.path.exists("forest.png"):
                file = discord.File("forest.png", filename="forest.png")
                embed.set_image(url="attachment://forest.png")
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            print(f"Error loading forest.png: {e}")
            await ctx.send(embed=embed)

    @forest.command()
    @commands.has_permissions(administrator=True)
    async def spawn(self, ctx):
        """Force spawn a forest Pokemon (admin only)"""
        # Get the regular spawn system
        spawn_cog = self.bot.get_cog("SpawnSystem")
        if not spawn_cog:
            return await ctx.send("❌ Spawn system not available!")
        
        # Clear any existing spawn
        if ctx.channel.id in spawn_cog.active_spawns:
            del spawn_cog.active_spawns[ctx.channel.id]
        
        # Get random Forest Pokemon
        pokemon_id, pokemon_name, pokemon_data = self.get_random_forest_pokemon()
        
        # Create spawn image
        spawn_image = await self._create_spawn_image(pokemon_data)
        
        # Create embed
        embed = discord.Embed(
            title="🌿 A wild Forest Pokemon has appeared!",
            description=f"Guess the pokémon and type `@Botachu catch <pokémon>` to catch it!",
            color=discord.Color.green()
        )
        embed.set_footer(text="🌳 Forest Event • Admin Spawn")
        
        # Send spawn message
        if spawn_image:
            file = discord.File(spawn_image, filename="spawn.png")
            embed.set_image(url="attachment://spawn.png")
            spawn_msg = await ctx.send(embed=embed, file=file)
        else:
            spawn_msg = await ctx.send(embed=embed)
        
        # Store spawn data in the regular spawn system
        spawn_cog.active_spawns[ctx.channel.id] = {
            "pokemon_name": pokemon_data["name"],
            "pokemon_id": int(pokemon_id),
            "pokemon_data": pokemon_data,
            "message_id": spawn_msg.id,
            "timestamp": datetime.utcnow(),
            "source": "forest_event_admin"
        }
        
        await ctx.send(f"✅ Force spawned **{pokemon_name}**!")

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

    async def _update_forest_event_in_db(self, event_data):
        """Update forest event data in database"""
        if event_data is None:
            # Remove the event data if None is passed
            await self.spawn_collection.update_one(
                {"forest_event_data": {"$exists": True}},
                {"$unset": {"forest_event_data": ""}},
                upsert=False
            )
        else:
            # Make sure to convert datetime to string for storage
            if "start_time" in event_data and isinstance(event_data["start_time"], datetime):
                event_data["start_time"] = event_data["start_time"].isoformat()
            
            await self.spawn_collection.update_one(
                {"forest_event_data": {"$exists": True}},
                {"$set": {"forest_event_data": event_data}},
                upsert=True
            )

async def setup(bot):
    cog = ForestEventSystem(bot)
    await bot.add_cog(cog)