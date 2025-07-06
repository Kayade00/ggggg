import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select
from datetime import datetime
from typing import Optional
import random
import json
import os
from PIL import Image, ImageDraw, ImageFont
import io
from evolution_data import EVOLUTION_DATA
from collections import defaultdict
import time
from theme_loader import theme

with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEMON_DATA = json.load(f)

with open("nature.json", "r", encoding="utf-8") as f:
    NATURES = json.load(f)["natures"]

STARTERS = {
    "Kanto": ["Bulbasaur", "Charmander", "Squirtle"],
    "Johto": ["Chikorita", "Cyndaquil", "Totodile"],
    "Hoenn": ["Treecko", "Torchic", "Mudkip"],
    "Sinnoh": ["Turtwig", "Chimchar", "Piplup"],
    "Unova": ["Snivy", "Tepig", "Oshawott"],
    "Kalos": ["Chespin", "Fennekin", "Froakie"],
    "Alola": ["Rowlet", "Litten", "Popplio"],
    "Galar": ["Grookey", "Scorbunny", "Sobble"],
    "Paldea": ["Sprigatito", "Fuecoco", "Quaxly"]
}



class Start(commands.Cog):
    def __init__(self, bot, collection, user_profiles):
        self.bot = bot
        self.collection = collection
        self.user_xp_cooldown = defaultdict(float)
        self.user_profiles = user_profiles
        self.friendship_task.start()  # Start the friendship update task

    def cog_unload(self):
        """Stop the task when cog is unloaded"""
        self.friendship_task.cancel() 

    @tasks.loop(hours=1)
    async def friendship_task(self):
        """Update friendship points every hour"""
        try:
            # Get all Pokemon that can gain friendship
            pokemon_cursor = self.collection.find({})
            
            async for pokemon in pokemon_cursor:
                friendship_gain = 0
                
                # Calculate friendship gain based on status
                if pokemon.get("selected", False):
                    friendship_gain += 2  # Selected Pokemon get +2
                    
                if pokemon.get("favorite", False):
                    friendship_gain += 2  # Favorite adds +2
                    
                if pokemon.get("nickname"):
                    friendship_gain += 2  # Nicknamed adds +2
                
                # Only update if there's friendship to gain
                if friendship_gain > 0:
                    current_friendship = pokemon.get("friendship", 0)
                    new_friendship = min(current_friendship + friendship_gain, 255)  # Cap at 255
                    
                    await self.collection.update_one(
                        {"_id": pokemon["_id"]},
                        {"$set": {"friendship": new_friendship}}
                    )
            
            print("✅ Friendship points updated for all eligible Pokemon")
            
        except Exception as e:
            print(f"Error updating friendship: {e}")

    @friendship_task.before_loop
    async def before_friendship_task(self):
        """Wait until bot is ready before starting the task"""
        await self.bot.wait_until_ready()

    async def can_evolve(self, pokemon):
        """Check if a Pokemon can evolve"""
        pokemon_name = pokemon["pokemon_name"]
        current_friendship = pokemon.get("friendship", 0)
        
        # Try to find evolution data with proper capitalization
        evolution_key = None
        for key in EVOLUTION_DATA.keys():
            if key.lower() == pokemon_name.lower():
                evolution_key = key
                break
        
        if not evolution_key:
            return False, None, None
            
        evolution_data = EVOLUTION_DATA[evolution_key]
        required_friendship = evolution_data["friendship_required"]
        evolves_to = evolution_data["evolves_to"]
        
        if current_friendship >= required_friendship:
            return True, evolves_to, required_friendship
        
        return False, evolves_to, required_friendship

    async def evolve_pokemon(self, pokemon, evolution_choice=None):
        """Evolve a Pokemon"""
        can_evolve, evolves_to, required_friendship = await self.can_evolve(pokemon)
        
        if not can_evolve:
            return False, "This Pokémon cannot evolve yet!"
        
        # Handle multiple evolution choices
        if isinstance(evolves_to, list):
            if not evolution_choice or evolution_choice not in evolves_to:
                return False, f"Please choose an evolution: {', '.join(evolves_to)}"
            final_evolution = evolution_choice
        else:
            final_evolution = evolves_to
        
        # Check if evolution exists in pokedex
        evolution_exists = any(
            isinstance(data, dict) and data.get("name", "").lower() == final_evolution.lower() 
            for data in POKEMON_DATA.values()
        )
        
        if not evolution_exists:
            return False, f"Evolution data for {final_evolution} not found!"
        
        # Perform evolution
        await self.collection.update_one(
            {"_id": pokemon["_id"]},
            {"$set": {"pokemon_name": final_evolution}}
        )
        
        # Give evolution bonus coins
        await self.update_user_balance(pokemon["user_id"], coins_change=50)
        
        return True, f"🌟 {pokemon['pokemon_name']} evolved into {final_evolution}! 🌟\n💰 You earned 50 coins!"

    def calculate_xp_for_level(self, level):
        return 3750 if level == 100 else int(375 + 33.75 * (level - 1))

    def calculate_stat(self, iv, level, base_stat, ev, is_hp=False):
        if is_hp:
            return ((2 * base_stat + iv + (ev // 4)) * level // 100) + level + 10
        return ((2 * base_stat + iv + (ev // 4)) * level // 100) + 5 

    async def create_profile_card(self, user, all_pokemon, selected_pokemon):
        """Create a profile card image"""
        try:
            # Card dimensions and colors
            width, height = 1000, 600
            bg_color = (47, 49, 54)  # Dark theme background
            green_color = (88, 166, 78)  # Green accent color
            text_color = (255, 255, 255)  # White text
            gray_color = (153, 153, 153)  # Gray text
            
            # Create image and draw object
            img = Image.new('RGB', (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Try to load fonts (fallback to default if not available)
            try:
                title_font = ImageFont.truetype("arial.ttf", 24)
                header_font = ImageFont.truetype("arial.ttf", 20)
                text_font = ImageFont.truetype("arial.ttf", 16)
                small_font = ImageFont.truetype("arial.ttf", 14)
            except:
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Calculate stats
            total_caught = len(all_pokemon)
            total_shiny = sum(1 for p in all_pokemon if p.get("shiny", False))
            pokedex_count = len(set(p["pokemon_name"] for p in all_pokemon))
            
            # Get registration date
            first_pokemon = min(all_pokemon, key=lambda x: x.get("caught_at", x.get("timestamp", datetime.utcnow())))
            register_date = first_pokemon.get("caught_at", first_pokemon.get("timestamp", datetime.utcnow()))
            
            # Draw green border
            border_width = 3
            draw.rectangle([0, 0, width-1, height-1], outline=green_color, width=border_width)
            
            # User info section (top-left)
            draw.rectangle([20, 20, 350, 180], outline=green_color, width=2)
            draw.text((30, 30), user.display_name, fill=text_color, font=title_font)
            draw.text((30, 60), "Pokémon Trainer", fill=gray_color, font=text_font)
            draw.text((30, 140), register_date.strftime('%d %b %Y'), fill=text_color, font=text_font)
            
            # Stats section (top-middle)
            draw.rectangle([370, 20, 650, 280], outline=green_color, width=2)
            draw.text((380, 30), "Stats", fill=green_color, font=header_font)
            
            # Pokemon Caught stats
            draw.text((380, 60), "Pokémon Caught", fill=text_color, font=text_font)
            draw.text((380, 85), f"Total: {total_caught:,}", fill=text_color, font=text_font)
            draw.text((380, 110), f"Mythical: 0", fill=gray_color, font=small_font)
            draw.text((380, 130), f"Legendary: 0", fill=gray_color, font=small_font)
            draw.text((380, 150), f"Ultra Beast: 0", fill=gray_color, font=small_font)
            draw.text((380, 175), f"Pokédex: {pokedex_count}/1025", fill=text_color, font=text_font)
            draw.text((380, 200), f"Gigantamax: 0", fill=text_color, font=text_font)
            draw.text((380, 225), f"Shiny: {total_shiny}", fill=text_color, font=text_font)
            
            # Pokemon Hatched section (top-right)
            draw.rectangle([670, 20, 950, 180], outline=green_color, width=2)
            draw.text((680, 30), "Pokémon Hatched", fill=text_color, font=text_font)
            draw.text((680, 55), "Total: 0", fill=text_color, font=text_font)
            draw.text((680, 80), "Gigantamax: 0", fill=gray_color, font=small_font)
            draw.text((680, 105), f"Shiny: {total_shiny}", fill=gray_color, font=small_font)
            
            # Display Pokemon section (bottom)
            draw.rectangle([20, 300, 680, 560], outline=green_color, width=2)
            draw.text((30, 310), "Display Pokémon", fill=green_color, font=header_font)
            
            if selected_pokemon:
                # Pokemon name and details
                pokemon_name = selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']
                shiny_text = "✨ " if selected_pokemon.get("shiny", False) else ""
                draw.text((30, 350), f"{shiny_text}{pokemon_name}", fill=text_color, font=title_font)
                draw.text((30, 380), f"Level {selected_pokemon['level']}", fill=text_color, font=text_font)
                draw.text((30, 405), f"Nature: {selected_pokemon['nature']}", fill=text_color, font=text_font)
                
                # Calculate and display IV
                total_iv = sum([selected_pokemon.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
                iv_percentage = round((total_iv / 186) * 100, 1)
                draw.text((30, 430), f"IV: {iv_percentage}%", fill=text_color, font=text_font)
                
                # Try to add Pokemon sprite
                pokemon_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == selected_pokemon["pokemon_name"].lower().replace("-", " ")), None)
                if pokemon_data and 'id' in pokemon_data:
                    sprite_path = f"full/{pokemon_data['id']}.png"
                    if os.path.exists(sprite_path):
                        try:
                            sprite = Image.open(sprite_path).convert("RGBA")
                            # Resize sprite to fit in the display area
                            sprite.thumbnail((200, 200), Image.Resampling.LANCZOS)
                            # Position sprite on the right side of display area
                            sprite_x = 500
                            sprite_y = 350
                            img.paste(sprite, (sprite_x, sprite_y), sprite)
                        except Exception as e:
                            print(f"Error loading Pokemon sprite: {e}")
            else:
                draw.text((30, 350), "No display pokémon set", fill=gray_color, font=text_font)
            
            # Top Badges section (bottom-right)
            draw.rectangle([700, 300, 950, 460], outline=green_color, width=2)
            draw.text((710, 310), "Top Badges", fill=green_color, font=header_font)
            draw.text((710, 350), "Coming soon...", fill=gray_color, font=text_font)
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
        except Exception as e:
            print(f"Error creating profile card: {e}")
            return None

    async def ensure_user_profile(self, user_id):
        """Ensure user has a profile in the database"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        if not profile:
            new_profile = {
                "user_id": user_id,
                "coins": 0,
                "diamonds": 0,
                "created_at": datetime.utcnow()
            }
            await self.user_profiles.insert_one(new_profile)
            return new_profile
        return profile

    async def update_user_balance(self, user_id, coins_change=0, diamonds_change=0):
        """Update user's balance"""
        await self.ensure_user_profile(user_id)
        await self.user_profiles.update_one(
            {"user_id": user_id},
            {"$inc": {"coins": coins_change, "diamonds": diamonds_change}}
        )

    async def get_user_balance(self, user_id):
        """Get user's current balance"""
        profile = await self.ensure_user_profile(user_id)
        return profile.get("coins", 0), profile.get("diamonds", 0)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        lowered = message.content.lower()
        if any(bot_user.mention in message.content for bot_user in message.mentions):
            return

        if lowered.startswith(("/", "!", ".", "-", "?", "$")):
            return

        user_data = await self.collection.find_one({"user_id": message.author.id, "selected": True})
        if not user_data or user_data["level"] >= 100 or user_data.get("xp_blocker", False):
            return

        user_id = message.author.id
        now = time.time()
        cooldown = self.user_xp_cooldown[user_id]
        is_spamming = (now - cooldown) < 7
        self.user_xp_cooldown[user_id] = now

        gained_xp = 3 if is_spamming else 10
        new_xp = user_data["xp"] + gained_xp
        level = user_data["level"]

        leveled_up = False

        while level < 100:
            xp_for_next = self.calculate_xp_for_level(level + 1)
            if new_xp >= xp_for_next:
                new_xp -= xp_for_next  # remove used XP for that level
                level += 1
                leveled_up = True
            else:
                break

        # Cap at level 100
        if level == 100:
            new_xp = self.calculate_xp_for_level(100)

        await self.collection.update_one(
            {"user_id": user_id, "selected": True},
            {"$set": {"xp": new_xp, "level": level}}
        )

        if leveled_up:
            await message.channel.send(
                f"🎉 {message.author.mention}, your **{user_data['pokemon_name']}** leveled up to **Level {level}**!"
            )

        # Handle mention-based commands
        if message.guild and message.guild.me in message.mentions:
            # Remove the mention and get the command part
            content = message.content
            for mention in message.mentions:
                if mention == message.guild.me:
                    content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '').strip()
                    break
            
            if content:
                # Parse the mention command
                parts = content.split()
                if not parts:
                    return
                
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # Handle different mention commands
                if command in ['profile', 'prof']:
                    await self.handle_mention_profile(message)
                elif command in ['balance', 'bal', 'money']:
                    await self.handle_mention_balance(message)
                elif command in ['evolve', 'evo']:
                    await self.handle_mention_evolve(message)

        

    async def handle_mention_profile(self, message):
        """Handle mention-based profile command"""
        user_id = message.author.id
        
        # Get all user's Pokemon
        all_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
        
        if not all_pokemon:
            prefix = message.bot.get_primary_prefix()
            return await message.reply(f"{theme.emoji('ui', 'cross')} You don't have any Pokémon yet! Use `{prefix}start` to begin your journey.")
        
        # Get selected Pokemon for display
        selected_pokemon = next((p for p in all_pokemon if p.get("selected", False)), None)
        
        # Create profile card image
        profile_image = await self.create_profile_card(message.author, all_pokemon, selected_pokemon)
        
        if profile_image:
            file = discord.File(profile_image, filename="profile.png")
            await message.reply(file=file)
        else:
            await message.reply(f"{theme.emoji('ui', 'cross')} Failed to generate profile card. Please try again later.")

    async def handle_mention_balance(self, message):
        """Handle @bot balance command"""
        try:
            coins, diamonds = await self.get_user_balance(message.author.id)
            
            # Create themed balance embed
            embed = theme.create_embed(
                title=f"{message.author.display_name}'s Balance",
                description=theme.format_balance(coins, diamonds),
                color_name="primary"
            )
            
            # Set thumbnail to user avatar
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
            
            await message.reply(embed=embed)
            
        except Exception as e:
            await message.reply(f"{theme.emoji('ui', 'cross')} Failed to retrieve balance. Please try again later.")

    async def handle_mention_evolve(self, message):
        """Handle mention-based evolve command"""
        try:
            # Get user's selected Pokemon
            pokemon = await self.collection.find_one({"user_id": message.author.id, "selected": True})
            
            if not pokemon:
                return await message.reply(f"{theme.emoji('ui', 'cross')} You don't have a selected Pokémon! Use `/select <number>` first.")
            
            # Check if Pokemon can evolve
            can_evolve, evolves_to, required_friendship = await self.can_evolve(pokemon)
            
            if not can_evolve:
                return await message.reply(f"{theme.emoji('ui', 'cross')} Your {pokemon['pokemon_name']} cannot evolve yet! Current friendship: {pokemon.get('friendship', 0)}, Required: {required_friendship}")
            
            # Handle multiple evolution paths
            if isinstance(evolves_to, list):
                class EvolutionSelect(Select):
                    def __init__(self, evolutions, pokemon_data):
                        self.pokemon_data = pokemon_data
                        options = [discord.SelectOption(label=evolution, value=evolution) for evolution in evolutions]
                        super().__init__(placeholder="Choose an evolution...", options=options)
                    
                    async def callback(self, interaction: discord.Interaction):
                        if interaction.user.id != self.pokemon_data["user_id"]:
                            return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} This is not your Pokémon!", ephemeral=True)
                        
                        evolution_choice = self.values[0]
                        success, result_message = await message.bot.get_cog("Start").evolve_pokemon(self.pokemon_data, evolution_choice)
                        
                        if success:
                            await interaction.response.edit_message(content=result_message, view=None)
                        else:
                            await interaction.response.edit_message(content=f"{theme.emoji('ui', 'cross')} {result_message}", view=None)

                class EvolutionView(View):
                    def __init__(self, evolutions, pokemon_data):
                        super().__init__(timeout=60)
                        self.add_item(EvolutionSelect(evolutions, pokemon_data))

                view = EvolutionView(evolves_to, pokemon)
                embed = theme.create_embed(
                    title="🌟 Evolution Available!",
                    description=f"Your **{pokemon['pokemon_name']}** can evolve! Choose an evolution path:",
                    color_name="success"
                )
                await message.reply(embed=embed, view=view)
            else:
                # Single evolution path
                success, result_message = await self.evolve_pokemon(pokemon)
                await message.reply(result_message)
                
        except Exception as e:
            await message.reply(f"{theme.emoji('ui', 'cross')} Something went wrong with evolution. Please try again later.")

    @app_commands.command(name="start", description="Begin your Pokémon journey!")
    async def start(self, interaction: discord.Interaction):
        existing_pokemon = await self.collection.find_one({"user_id": interaction.user.id})
        if existing_pokemon:
            return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} You have already started your journey!", ephemeral=True)
        
        class RegionSelectView(View):
            def __init__(self, collection):
                super().__init__(timeout=300)
                self.collection = collection
                
                for region in STARTERS.keys():
                    self.add_item(RegionButton(region, collection))
        
        class RegionButton(Button):
            def __init__(self, region, collection):
                super().__init__(label=region, style=discord.ButtonStyle.primary)
                self.region = region
                self.collection = collection
            
            async def callback(self, i: discord.Interaction):
                if i.user.id != interaction.user.id:
                    return await i.response.send_message("❌ This is not your starter selection!", ephemeral=True)
                
                embed = discord.Embed(title=f"Choose your {self.region} starter!", color=discord.Color.blue())
                view = StarterSelectView(self.region, self.collection)
                await i.response.edit_message(embed=embed, view=view)
        
        class StarterSelectView(View):
            def __init__(self, region, collection):
                super().__init__(timeout=300)
                self.region = region
                self.collection = collection
                
                for starter in STARTERS[region]:
                    self.add_item(StarterButton(starter, collection))
        
        class StarterButton(Button):
            def __init__(self, pokemon, collection):
                super().__init__(label=pokemon, style=discord.ButtonStyle.success)
                self.pokemon = pokemon
                self.collection = collection
            
            async def callback(self, i: discord.Interaction):
                if i.user.id != interaction.user.id:
                    return await i.response.send_message("❌ This is not your starter selection!", ephemeral=True)
                
                # Get the next Pokémon number for this user
                last_pokemon = await self.collection.find_one(
                    {"user_id": i.user.id}, 
                    sort=[("pokemon_number", -1)]
                )
                next_number = (last_pokemon["pokemon_number"] + 1) if last_pokemon else 1
                
                # Create the starter Pokémon
                starter_data = {
                    "user_id": i.user.id,
                    "pokemon_name": self.pokemon,
                    "pokemon_number": next_number,
                    "level": 5,
                    "xp": 0,
                    "nature": random.choice(list(NATURES.keys())),
                    "hp_iv": random.randint(0, 31),
                    "atk_iv": random.randint(0, 31),
                    "def_iv": random.randint(0, 31),
                    "sp_atk_iv": random.randint(0, 31),
                    "sp_def_iv": random.randint(0, 31),
                    "spd_iv": random.randint(0, 31),
                    "shiny": False,
                    "selected": True,
                    "favorite": False,
                    "timestamp": datetime.utcnow(),
                    "friendship": 0
                }
                
                await self.collection.insert_one(starter_data)
                
                embed = discord.Embed(
                    title="🎉 Congratulations!",
                    description=f"You've chosen **{self.pokemon}** as your starter!\nYour journey begins now!",
                    color=discord.Color.green()
                )
                await i.response.edit_message(embed=embed, view=None)

        embed = theme.create_embed(
            title="🌟 Choose your region!", 
            description="Select a region to start your Pokémon journey!", 
            color_name="warning"
        )
        view = RegionSelectView(self.collection)
        await interaction.response.send_message(embed=embed, view=view)

    

    @app_commands.command(name="profile", description="View your trainer profile!")
    async def profile(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        all_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
        if not all_pokemon:
            return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} You don't have any Pokémon yet! Use `/start` to begin your journey.", ephemeral=True)

        # Stats
        total_caught = len(all_pokemon)
        total_shiny = sum(1 for p in all_pokemon if p.get("shiny", False))
        unique_species = len(set(p["pokemon_name"] for p in all_pokemon))
        selected_pokemon = next((p for p in all_pokemon if p.get("selected", False)), None)
        favorite_pokemon = next((p for p in all_pokemon if p.get("favorite", False)), None)
        first_pokemon = min(all_pokemon, key=lambda x: x.get("caught_at", x.get("timestamp", datetime.utcnow())))
        join_date = first_pokemon.get("caught_at", first_pokemon.get("timestamp", datetime.utcnow()))
        coins, diamonds = await self.get_user_balance(user_id)

        # Build embed
        embed = theme.create_embed(
            title=f"{interaction.user.display_name}'s Trainer Profile",
            description=f"{theme.emoji('pokemon', 'pokeball')} **Total Caught:** {total_caught}\n"
                        f"{theme.emoji('pokemon', 'shiny')} **Shinies:** {total_shiny}\n"
                        f"{theme.emoji('pokemon', 'pokeball')} **Unique Species:** {unique_species}\n"
                        f"{theme.emoji('currency', 'coins')} **Coins:** {coins:,}   {theme.emoji('currency', 'diamonds')} **Diamonds:** {diamonds:,}\n"
                        f"{theme.emoji('ui', 'info')} **Joined:** {join_date.strftime('%d %b %Y')}",
            color_name="primary"
        )
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)

        if selected_pokemon:
            embed.add_field(
                name=f"{theme.emoji('pokemon', 'pokeball')} Selected Pokémon",
                value=f"{selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']} (Lvl {selected_pokemon['level']})",
                inline=False
            )
        if favorite_pokemon:
            embed.add_field(
                name=f"{theme.emoji('pokemon', 'favorite')} Favorite Pokémon",
                value=f"{favorite_pokemon.get('nickname') or favorite_pokemon['pokemon_name']} (Lvl {favorite_pokemon['level']})",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="balance", description="Check your coin and diamond balance!")
    async def balance(self, interaction: discord.Interaction):
        try:
            coins, diamonds = await self.get_user_balance(interaction.user.id)
            
            # Create themed balance embed
            embed = theme.create_embed(
                title=f"{interaction.user.display_name}'s Balance",
                description=theme.format_balance(coins, diamonds),
                color_name="primary"
            )
            
            # Set thumbnail to user avatar
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} Failed to retrieve balance. Please try again later.", ephemeral=True)

    @app_commands.command(name="evolve", description="Evolve your selected Pokémon!")
    async def evolve(self, interaction: discord.Interaction):
        try:
            # Get user's selected Pokemon
            pokemon = await self.collection.find_one({"user_id": interaction.user.id, "selected": True})
            
            if not pokemon:
                return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} You don't have a selected Pokémon! Use `/select <number>` first.", ephemeral=True)
            
            # Check if Pokemon can evolve
            can_evolve, evolves_to, required_friendship = await self.can_evolve(pokemon)
            
            if not can_evolve:
                return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} Your {pokemon['pokemon_name']} cannot evolve yet!\nCurrent friendship: {pokemon.get('friendship', 0)}\nRequired: {required_friendship}", ephemeral=True)
            
            # Handle multiple evolution paths
            if isinstance(evolves_to, list):
                class EvolutionSelect(Select):
                    def __init__(self, evolutions, pokemon_data):
                        self.pokemon_data = pokemon_data
                        options = [discord.SelectOption(label=evolution, value=evolution) for evolution in evolutions]
                        super().__init__(placeholder="Choose an evolution...", options=options)
                    
                    async def callback(self, select_interaction: discord.Interaction):
                        if select_interaction.user.id != self.pokemon_data["user_id"]:
                            return await select_interaction.response.send_message(f"{theme.emoji('ui', 'cross')} This is not your Pokémon!", ephemeral=True)
                        
                        evolution_choice = self.values[0]
                        cog = interaction.client.get_cog("Start")
                        success, result_message = await cog.evolve_pokemon(self.pokemon_data, evolution_choice)
                        
                        if success:
                            await select_interaction.response.edit_message(content=result_message, view=None)
                        else:
                            await select_interaction.response.edit_message(content=f"{theme.emoji('ui', 'cross')} {result_message}", view=None)

                class EvolutionView(View):
                    def __init__(self, evolutions, pokemon_data):
                        super().__init__(timeout=60)
                        self.add_item(EvolutionSelect(evolutions, pokemon_data))

                view = EvolutionView(evolves_to, pokemon)
                embed = theme.create_embed(
                    title="🌟 Evolution Available!",
                    description=f"Your **{pokemon['pokemon_name']}** can evolve! Choose an evolution path:",
                    color_name="success"
                )
                await interaction.response.send_message(embed=embed, view=view)
            else:
                # Single evolution path
                success, result_message = await self.evolve_pokemon(pokemon)
                await interaction.response.send_message(result_message)
                
        except Exception as e:
            await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} Something went wrong with evolution. Please try again later.", ephemeral=True)


    @app_commands.command(name="info", description="View information about one of your Pokémon.")
    @app_commands.describe(number="Optional: the number of your Pokémon to view")
    async def info(self, interaction: discord.Interaction, number: int = None):
        if number:
            data = await self.collection.find_one({"user_id": interaction.user.id, "pokemon_number": number})
        else:
            data = await self.collection.find_one({"user_id": interaction.user.id, "selected": True})

        if not data:
            return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} You haven't selected a starter Pokémon yet.", ephemeral=True)
        poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == data["pokemon_name"].lower()), None)
        if not poke_data:
            return await interaction.response.send_message(f"{theme.emoji('ui', 'cross')} Pokémon base data missing.", ephemeral=True)
        stats = poke_data["stats"]
        total_iv = sum([data.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
        total_iv_percent = round((total_iv / 186) * 100, 2)
        stat_text = "\n".join([
            f"HP: {stats['hp']} – IV: {data['hp_iv']}/31",
            f"Attack: {stats['attack']} – IV: {data['atk_iv']}/31",
            f"Defense: {stats['defense']} – IV: {data['def_iv']}/31",
            f"Sp. Atk: {stats['special-attack']} – IV: {data['sp_atk_iv']}/31",
            f"Sp. Def: {stats['special-defense']} – IV: {data['sp_def_iv']}/31",
            f"Speed: {stats['speed']} – IV: {data['spd_iv']}/31",
            f"**Total IV**: {total_iv_percent}%"
        ])

        xp_needed = self.calculate_xp_for_level(data["level"] + 1)
        friendship = data.get("friendship", 0)
        
        # Build title with appropriate emoji
        title_emoji = theme.emoji('ui', 'shiny') if data.get('shiny') else theme.emoji('pokemon', 'pokeball')
        embed = theme.create_embed(
            title=f"{title_emoji} {data['nickname'] or data['pokemon_name']} (#{data['pokemon_number']})",
            color_name="warning"
        )
        avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(
            name=f"{theme.emoji('ui', 'info')} Details",
            value=(
                f"**Level**: {data['level']}\n"
                f"**XP**: {data['xp']} / {xp_needed}\n"
                f"**Nature**: {data['nature']}\n"
                f"**Held Item**: {data.get('held_item') or 'None'}\n"
                f"**Friendship**: {friendship}"
                
            ),
            inline=False
        )
        embed.add_field(name=f"{theme.emoji('stats', 'attack')} Stats", value=stat_text, inline=False)
        embed.add_field(name=f"{theme.emoji('battle', 'move')} Moves", value="\n".join([
            data.get("move1", "None"),
            data.get("move2", "None"),
            data.get("move3", "None"),
            data.get("move4", "None")
        ]), inline=False)
        embed.set_footer(
            text=f"Selected: {data.get('selected', False)} | "
                f"Favorite: {data.get('favorite', False)} | "
                f"XP Blocker: {data.get('xp_blocker', False)}"
        )
        poke_id = str(poke_data.get("id"))
        if data.get("shiny"):
           folder = "full_shiny"
           filename = f"{poke_id}_full.png"
        else:
            folder = "full"
            filename = f"{poke_id}.png"
        image_path = f"{folder}/{filename}"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="pokemon.png")
            embed.set_image(url="attachment://pokemon.png")
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    pokemon_db = bot.pokemon_collection
    user_profiles_db = bot.db["user_profiles"]
    await bot.add_cog(Start(bot, pokemon_db, user_profiles_db)) 
