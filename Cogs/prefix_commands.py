import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from datetime import datetime
from typing import Optional
import random
import json
import os
from PIL import Image, ImageDraw, ImageFont
import io
from evolution_data import EVOLUTION_DATA
import requests
import asyncio
import sys

# Add the parent directory to sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokemon_filters import parse_command_with_filters, filter_pokemon_list, get_filter_help, PokemonFilter

with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEMON_DATA = json.load(f)

# Load custom/event Pokemon and merge with main data
try:
    with open("custom_pokemon.json", "r", encoding="utf-8") as f:
        CUSTOM_POKEMON = json.load(f)
        POKEMON_DATA.update(CUSTOM_POKEMON)
        print(f"Loaded {len(CUSTOM_POKEMON)} custom Pokemon!")
except FileNotFoundError:
    print("No custom_pokemon.json file found - only base Pokemon available")
    CUSTOM_POKEMON = {}

with open("nature.json", "r", encoding="utf-8") as f:
    NATURES = json.load(f)["natures"]

# Load moves data
try:
    with open("moves_data.json", "r", encoding="utf-8") as f:
        MOVES_DATA = json.load(f)
except FileNotFoundError:
    print("Warning: moves_data.json not found. Move info will be limited.")
    MOVES_DATA = {}

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

class PrefixCommands(commands.Cog):
    def __init__(self, bot, collection, user_profiles):
        self.bot = bot
        self.collection = collection
        self.user_profiles = user_profiles
    
    def is_custom_pokemon(self, pokemon_name):
        """Check if a Pokemon is a custom/event Pokemon"""
        for pokemon_id, data in POKEMON_DATA.items():
            if data["name"].lower() == pokemon_name.lower():
                return data.get("custom", False)
        return False
    
    def get_event_emoji(self, event_tag):
        """Get emoji for different event types"""
        if not event_tag:
            return "⭐"
        
        event_emojis = {
            "halloween": "🎃",
            "christmas": "🎄", 
            "valentine": "💝",
            "new year": "🎆",
            "easter": "🐰",
            "summer": "☀️",
            "winter": "❄️"
        }
        
        for event_type, emoji in event_emojis.items():
            if event_type in event_tag.lower():
                return emoji
        
        return "⭐"  # Default event emoji

    def calculate_xp_for_level(self, level):
        return 3750 if level == 100 else int(375 + 33.75 * (level - 1))

    def calculate_stat(self, iv, level, base_stat, ev, nature_name=None, stat_index=None, is_hp=False):
        # Calculate base stat first
        if is_hp:
            base_calculated = ((2 * base_stat + iv + (ev // 4)) * level // 100) + level + 10
        else:
            base_calculated = ((2 * base_stat + iv + (ev // 4)) * level // 100) + 5
        
        # Apply nature modifier if provided
        if nature_name and stat_index is not None and not is_hp:
            nature_multiplier = NATURES.get(nature_name, [1, 1, 1, 1, 1, 1])[stat_index]
            base_calculated = int(base_calculated * nature_multiplier)
        
        return base_calculated

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

    async def can_evolve(self, pokemon):
        """Check if a Pokemon can evolve"""
        pokemon_name = pokemon["pokemon_name"]
        if not pokemon_name:
            return False, None, None
            
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
        if not final_evolution:
            return False, "Evolution target not found!"
            
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
                pokemon_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == selected_pokemon["pokemon_name"].lower()), None)
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

    @commands.command(name="info", aliases=["i"])
    async def prefix_info(self, ctx, number = None):
        """Show information about a specific Pokémon"""
        if number and str(number).lower() == "latest":
            data = await self.collection.find_one(
                {"user_id": ctx.author.id}, 
                sort=[("pokemon_number", -1)]
            )
        elif number and str(number).isdigit():
            data = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": int(number)})
        else:
            data = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})

        if not data:
            if number and str(number).isdigit():
                return await ctx.reply(f"❌ I couldn't find a Pokémon with number {number} in your collection.")
            else:
                prefix = ctx.bot.get_primary_prefix()
                return await ctx.reply(f"❌ You haven't selected a Pokémon yet. Use `{prefix}select <number>` to select one.")

        poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == data["pokemon_name"].lower()), None)
        if not poke_data:
            return await ctx.reply("❌ Pokémon base data missing.")

        stats = poke_data["stats"]
        
        # Handle both old and new IV field names
        hp_iv = data.get('hpiv', data.get('hp_iv', 0))
        atk_iv = data.get('atkiv', data.get('atk_iv', 0))
        def_iv = data.get('defiv', data.get('def_iv', 0))
        spatk_iv = data.get('spatkiv', data.get('sp_atk_iv', 0))
        spdef_iv = data.get('spdefiv', data.get('sp_def_iv', 0))
        spd_iv = data.get('spdiv', data.get('spd_iv', 0))
        
        total_iv = hp_iv + atk_iv + def_iv + spatk_iv + spdef_iv + spd_iv
        total_iv_percent = round((total_iv / 186) * 100, 2)

        # Calculate actual stats using Gen 5+ formula with nature modifiers
        nature_name = data.get('nature', 'Hardy')
        calculated_hp = self.calculate_stat(hp_iv, data['level'], stats['hp'], 0, nature_name, 0, is_hp=True)
        calculated_attack = self.calculate_stat(atk_iv, data['level'], stats['attack'], 0, nature_name, 1)
        calculated_defense = self.calculate_stat(def_iv, data['level'], stats['defense'], 0, nature_name, 2)
        calculated_sp_atk = self.calculate_stat(spatk_iv, data['level'], stats['special-attack'], 0, nature_name, 3)
        calculated_sp_def = self.calculate_stat(spdef_iv, data['level'], stats['special-defense'], 0, nature_name, 4)
        calculated_speed = self.calculate_stat(spd_iv, data['level'], stats['speed'], 0, nature_name, 5)

        stat_text = "\n".join([
            f"HP: {calculated_hp} – IV: {hp_iv}/31",
            f"Attack: {calculated_attack} – IV: {atk_iv}/31",
            f"Defense: {calculated_defense} – IV: {def_iv}/31",
            f"Sp. Atk: {calculated_sp_atk} – IV: {spatk_iv}/31",
            f"Sp. Def: {calculated_sp_def} – IV: {spdef_iv}/31",
            f"Speed: {calculated_speed} – IV: {spd_iv}/31",
        ])

        xp_needed = self.calculate_xp_for_level(data["level"] + 1)
        
        # Add shiny indicator to name
        pokemon_name = data.get('nickname') or data['pokemon_name']
        if data.get("shiny", False):
            pokemon_name = f"✨ {pokemon_name}"
        
        embed = discord.Embed(
            title=f"{pokemon_name} (#{data['pokemon_number']})",
            description=(
                f"**Level**: {data['level']}\n"
                f"**XP**: {data['xp']} / {xp_needed}\n"
                f"**Nature**: {data['nature']}\n"
                f"**Held Item**: {data.get('held_item') or 'None'}\n"
                f"**Total IV**: {total_iv_percent}%\n"
                f"**Friendship**: {data.get('friendship', 0)}/255"
            ),
            color=discord.Color.gold()
        )

        embed.add_field(name="Moves", value="\n".join([
            data.get("move1", "None"),
            data.get("move2", "None"),
            data.get("move3", "None"),
            data.get("move4", "None")
        ]), inline=False)

        embed.add_field(name="Stats", value=stat_text, inline=False)
        embed.set_footer(text=f"Selected: {data.get('selected', False)} | Favorite: {data.get('favorite', False)} | XP Blocker: {data.get('xp_blocker', False)}")

        if poke_data and 'id' in poke_data:
            # Check if Pokemon is shiny and use appropriate sprite folder
            if data.get("shiny", False):
                image_path = f"full_shiny/{poke_data['id']}_full.png"
            else:
                image_path = f"full/{poke_data['id']}.png"
                
            if os.path.exists(image_path):
                file = discord.File(image_path, filename="pokemon.png")
                embed.set_image(url="attachment://pokemon.png")
                await ctx.reply(embed=embed, file=file)
                return
        
        await ctx.reply(embed=embed)




    @commands.command(name="pokemon", aliases=["p", "team"])
    async def prefix_pokemon(self, ctx, *args):
        filters, remaining_args = parse_command_with_filters(list(args))
        filter_system = PokemonFilter()

        pokemon_list = await self.collection.find({"user_id": ctx.author.id}).sort("pokemon_number", 1).to_list(length=None)

        if not pokemon_list:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You don't have any Pokémon yet! Use `{prefix}start` to begin your journey.")

        if filters:
            pokemon_list = filter_pokemon_list(pokemon_list, filters)
            if not pokemon_list:
                filter_desc = filter_system.get_filter_description(filters)
                embed = discord.Embed(
                    title="📋 Your Pokémon Collection",
                    description=f"🔍 No Pokémon found matching your filters.\n**Filters:** {filter_desc}",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Try adjusting your filters or use !pokemon to see all Pokémon")
                return await ctx.reply(embed=embed)

        # Format each Pokémon line (mobile-friendly)
        def format_pokemon_line(pokemon):
            name = pokemon["pokemon_name"]
            nickname = pokemon.get("nickname", "")
            level = pokemon["level"]

            total_iv = sum([
                pokemon.get(iv, 0)
                for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]
            ])
            total_iv_percent = round((total_iv / 186) * 100, 2)

            poke_data = next((v for v in POKEMON_DATA.values() if isinstance(v, dict) and v.get("name", "").lower() == name.lower()), None)
            emoji = ""
            if poke_data and 'id' in poke_data:
                emoji = self.bot.pokemon_emojis.get(str(poke_data["id"]), "")
            
            # Status icons
            status_icons = ""
            if pokemon.get("shiny", False):
                status_icons += "✨"
            if pokemon.get("favorite", False):
                status_icons += "❤️"
            # Check for event Pokemon
            if pokemon.get("event_pokemon", False) or (poke_data and poke_data.get("custom", False)):
                event_tag = pokemon.get("event_tag", poke_data.get("event_tag", "") if poke_data else "")
                status_icons += self.get_event_emoji(event_tag)

            # Clean format like other bots with wide spaces
            if nickname:
                name_part = f"{name} \"{nickname}\""
            else:
                name_part = name
            
            # Add status icons after name
            if status_icons:
                name_part += f" {status_icons}"
            
            return f"{pokemon['pokemon_number']:>4}　{emoji}{name_part}　•　Lvl. {level}　•　{total_iv_percent:.2f}%"

        # Pagination
        pokemon_per_page = 20
        total_pages = (len(pokemon_list) + pokemon_per_page - 1) // pokemon_per_page
        embeds = []

        for page in range(total_pages):
            start_idx = page * pokemon_per_page
            end_idx = min(start_idx + pokemon_per_page, len(pokemon_list))
            page_pokemon = pokemon_list[start_idx:end_idx]

            # Mobile-friendly header
            description_lines = [format_pokemon_line(p) for p in page_pokemon]
            description_text = "\n".join(description_lines)

            embed = discord.Embed(
                title=f"📋 Pokémon Collection of {ctx.author.display_name}",
                description=description_text,
                color=discord.Color.dark_magenta()
            )

            if filters:
                filter_desc = filter_system.get_filter_description(filters)
                embed.add_field(name="🔍 Active Filters", value=filter_desc or "None", inline=True)

            embed.set_footer(text=f"Showing entries {start_idx+1}–{end_idx} of {len(pokemon_list)}.")
            embeds.append(embed)

        if len(embeds) == 1:
            return await ctx.reply(embed=embeds[0])

        # Pagination View
        class PokemonPaginationView(View):
            def __init__(self, embeds, author):
                super().__init__(timeout=300)
                self.embeds = embeds
                self.current_page = 0
                self.author = author

            @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple)
            async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can navigate pages!", ephemeral=True)
                self.current_page = (self.current_page - 1) % len(self.embeds)
                await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

            @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
            async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can navigate pages!", ephemeral=True)
                self.current_page = (self.current_page + 1) % len(self.embeds)
                await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

        view = PokemonPaginationView(embeds, ctx.author)
        await ctx.reply(embed=embeds[0], view=view)





    @commands.command(name="nickname", aliases=["nick", "rename"])
    async def prefix_nickname(self, ctx, number: int, *, nickname = None):
        """Give your Pokémon a nickname"""
        # Find the Pokémon
        pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        
        if not pokemon:
            return await ctx.reply("❌ You don't have a Pokémon with that number!")
        
        if nickname is None:
            # Remove nickname
            await self.collection.update_one(
                {"user_id": ctx.author.id, "pokemon_number": number},
                {"$unset": {"nickname": ""}}
            )
            await ctx.reply(f"✅ Removed nickname from **{pokemon['pokemon_name']}** #{number}!")
        else:
            # Set nickname
            await self.collection.update_one(
                {"user_id": ctx.author.id, "pokemon_number": number},
                {"$set": {"nickname": nickname}}
            )
            await ctx.reply(f"✅ **{pokemon['pokemon_name']}** #{number} is now nicknamed **{nickname}**!")





    @commands.command(name="favorite", aliases=["fav", "favourite"])
    async def prefix_favorite(self, ctx, number: int):
        """Toggle a Pokémon as favorite"""
        # Find the Pokémon
        pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        
        if not pokemon:
            return await ctx.reply("❌ You don't have a Pokémon with that number!")
        
        # Toggle favorite status
        new_status = not pokemon.get("favorite", False)
        await self.collection.update_one(
            {"user_id": ctx.author.id, "pokemon_number": number},
            {"$set": {"favorite": new_status}}
        )
        
        status_text = "added to" if new_status else "removed from"
        await ctx.reply(f"{'❤️' if new_status else '💔'} **{pokemon.get('nickname') or pokemon['pokemon_name']}** #{number} {status_text} favorites!")

    @commands.command(name="unfavorite", aliases=["unfav", "unfavourite"])
    async def prefix_unfavorite(self, ctx, number: int):
        """Remove a Pokémon from favorites"""
        # Find the Pokémon
        pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        
        if not pokemon:
            return await ctx.reply("❌ You don't have a Pokémon with that number!")
        
        # Check if it's already not favorited
        if not pokemon.get("favorite", False):
            return await ctx.reply(f"💔 **{pokemon.get('nickname') or pokemon['pokemon_name']}** #{number} is not in your favorites!")
        
        # Remove from favorites
        await self.collection.update_one(
            {"user_id": ctx.author.id, "pokemon_number": number},
            {"$set": {"favorite": False}}
        )
        
        await ctx.reply(f"💔 **{pokemon.get('nickname') or pokemon['pokemon_name']}** #{number} removed from favorites!")

    @commands.command(name="start", aliases=["begin"])
    async def prefix_start(self, ctx):
        """Start your Pokémon journey"""
        existing_pokemon = await self.collection.find_one({"user_id": ctx.author.id})
        if existing_pokemon:
            return await ctx.reply("❌ You have already started your journey!")
        
        embed = discord.Embed(
            title="🌟 Welcome to Pokémon!",
            description="Use `/start` for interactive starter selection with buttons!",
            color=discord.Color.gold()
        )
        await ctx.reply(embed=embed)

    @commands.command(name="help", aliases=["h", "commands"])
    async def prefix_help(self, ctx):
        """Show all available commands"""
        prefix = ctx.bot.get_primary_prefix()
        
        # Create help pages
        pages = {
            "overview": {
                "title": "📋 Pokémon Bot - Overview",
                "description": f"Welcome to Pokémon Bot! Use the dropdown below to navigate through different command categories.\n\n**Current Prefix:** `{prefix}`",
                "fields": [
                    {
                        "name": "🎮 Getting Started",
                        "value": f"`{prefix}start` - Begin your Pokémon journey\n`{prefix}help` - Show this help menu\n`{prefix}invite` - Invite the bot to your server",
                        "inline": False
                    },
                    {
                        "name": "⚡ Alternative Usage",
                        "value": f"• **Slash Commands:** Use `/start`, `/profile`, etc.\n• **Mentions:** Use `@{ctx.bot.user.name} profile`\n• **Type `/` in chat** to see all slash commands!",
                        "inline": False
                    },
                    {
                        "name": "💡 Quick Tips",
                        "value": "• Use `latest` as a number to select your newest Pokémon\n• Most commands work with both numbers and 'latest'\n• Check the other pages for detailed command lists!",
                        "inline": False
                    }
                ]
            },
            "pokemon": {
                "title": "👾 Pokémon Management",
                "description": "Commands for managing your Pokémon collection",
                "fields": [
                    {
                        "name": "📋 Collection Commands",
                        "value": f"`{prefix}pokemon` / `{prefix}p` - View your collection\n`{prefix}info [number]` / `{prefix}i` - View Pokémon details\n`{prefix}select <number>` - Select active Pokémon\n`{prefix}reindex` - Fix numbering gaps",
                        "inline": False
                    },
                    {
                        "name": "✏️ Customization",
                        "value": f"`{prefix}nickname <number> [name]` - Set nickname\n`{prefix}favorite <number>` - Toggle favorite\n`{prefix}unfavorite <number>` - Remove from favorites\n`{prefix}release <number>` - Release Pokémon\n`{prefix}releaseall` or `{prefix}ra` - Release all non-favorites",
                        "inline": False
                    },
                    {
                        "name": "🔍 Filtering",
                        "value": f"`{prefix}pokemon --filters` - Use filters below:\n`--name <n>` or `--n` - Filter by name\n`--shiny` - Show only shinies\n`--favorite` - Show only favorites\n`--level > 50` - Level filters (>, <, >=, <=, =)\n`--spdiv > 25` - IV filters for all stats",
                        "inline": False
                    },

                ]
            },
            "battle": {
                "title": "⚔️ Moves & Combat",
                "description": "Everything related to moves, learning, and battles",
                "fields": [
                    {
                        "name": "📖 Move Information",
                        "value": f"`{prefix}moves [number]` - View Pokémon's current moves\n`{prefix}moveset <pokemon>` / `{prefix}ms` - All learnable moves\n`{prefix}moveinfo <move>` / `{prefix}mi` - Move details",
                        "inline": False
                    },
                    {
                        "name": "🎓 Learning Moves",
                        "value": f"`{prefix}learn <number> <move>` - Teach a move\n• Replace existing moves when learning new ones\n• Some moves require specific levels or methods",
                        "inline": False
                    },
                    {
                        "name": "🎯 Battle Party",
                        "value": f"`{prefix}party` - View your battle party\n`{prefix}party add <number>` - Add Pokémon to party\n`{prefix}party remove <number>` - Remove from party\n`{prefix}party clear` - Clear entire party",
                        "inline": False
                    },
                    {
                        "name": "🥊 Combat",
                        "value": f"`{prefix}pve` / `{prefix}battle` - Challenge PvE bosses\n• Uses your party's first 3 Pokémon\n• Battle AI trainers for coin rewards\n• Strategy matters - type effectiveness applies!\n\n`{prefix}finish` - Clear stuck battle state (emergency fix)",
                        "inline": False
                    }
                ]
            },
            "profile": {
                "title": "📊 Profile & Economy", 
                "description": "Commands for your trainer profile, evolution, and economy",
                "fields": [
                    {
                        "name": "👤 Profile Commands",
                        "value": f"`{prefix}profile` - View trainer profile card\n`{prefix}balance` / `{prefix}bal` - Check coins & diamonds\n`{prefix}friendship` / `{prefix}friend` - View friendship progress",
                        "inline": False
                    },
                    {
                        "name": "🔄 Evolution & Growth",
                        "value": f"`{prefix}evolve [number]` - Evolve Pokémon\n• Some evolutions require friendship\n• Others need specific levels or items\n• Choose from multiple evolution paths",
                        "inline": False
                    },
                    {
                        "name": "💰 Economy",
                        "value": f"`{prefix}shop` - Visit the item shop\n`{prefix}market` - Pokémon marketplace\n`{prefix}buy candy <amount>` - Buy rare candies\n• Earn coins from PvE battles\n• Spend coins on items and trades",
                        "inline": False
                    }
                ]
            },
            "info": {
                "title": "📚 Information & Database",
                "description": "Commands for looking up Pokémon data and information", 
                "fields": [
                    {
                        "name": "📖 Pokédex",
                        "value": f"`{prefix}pokedex [pokemon]` / `{prefix}d` / `{prefix}dex`\n• View detailed Pokémon information\n• Stats, types, abilities, and more\n• Works with names or numbers",
                        "inline": False
                    },
                    {
                        "name": "🔍 Search Examples",
                        "value": f"`{prefix}dex pikachu` - Lookup Pikachu\n`{prefix}dex 25` - Lookup by number\n`{prefix}ms charizard` - All Charizard moves\n`{prefix}mi thunderbolt` - Thunderbolt details",
                        "inline": False
                    },
                    {
                        "name": "💡 Tips",
                        "value": "• Most commands accept partial names\n• Use quotation marks for multi-word names\n• Check move compatibility before learning",
                        "inline": False
                    }
                ]
            },
            "trading": {
                "title": "🤝 Trading & Market",
                "description": "Commands for trading Pokémon with other users",
                "fields": [
                    {
                        "name": "🏪 Marketplace",
                        "value": f"`{prefix}market` - Browse Pokémon listings\n• Use filters to find specific Pokémon\n• Buy Pokémon from other trainers\n• View detailed information before buying",
                        "inline": False
                    },
                    {
                        "name": "📦 Listing Pokémon",
                        "value": f"`{prefix}market list <number> <price>` - List for sale\n• Set your own prices\n• Cannot list your only Pokémon\n• Listings expire after some time",
                        "inline": False
                    },
                    {
                        "name": "⚠️ Important Notes",
                        "value": "• You must always keep at least one Pokémon\n• Check IVs and stats before trading\n• All sales are final - trade carefully!",
                        "inline": False
                    }
                ]
            }
        }
        
        class HelpDropdown(discord.ui.Select):
            def __init__(self, pages, current_page="overview"):
                self.pages = pages
                self.current_page = current_page
                
                options = [
                    discord.SelectOption(
                        label="📋 Overview",
                        description="Getting started and basic information",
                        value="overview",
                        default=current_page == "overview"
                    ),
                    discord.SelectOption(
                        label="👾 Pokémon Management", 
                        description="Collection, nicknames, favorites, filtering",
                        value="pokemon",
                        default=current_page == "pokemon"
                    ),
                    discord.SelectOption(
                        label="⚔️ Moves & Combat",
                        description="Learning moves, move info, PvE battles",
                        value="battle",
                        default=current_page == "battle"
                    ),
                    discord.SelectOption(
                        label="📊 Profile & Economy",
                        description="Profile, balance, evolution, shop",
                        value="profile", 
                        default=current_page == "profile"
                    ),
                    discord.SelectOption(
                        label="📚 Information & Database",
                        description="Pokédex, movesets, move information",
                        value="info",
                        default=current_page == "info"
                    ),
                    discord.SelectOption(
                        label="🤝 Trading & Market",
                        description="Marketplace, listings, trading tips",
                        value="trading",
                        default=current_page == "trading"
                    )
                ]
                
                super().__init__(placeholder="Choose a help category...", options=options)
            
            async def callback(self, interaction: discord.Interaction):
                page_data = self.pages[self.values[0]]
                
                embed = discord.Embed(
                    title=page_data["title"],
                    description=page_data["description"],
                    color=discord.Color.blue()
                )
                
                for field in page_data["fields"]:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field["inline"]
                    )
                
                if self.values[0] == "overview":
                    embed.set_footer(text="💡 Use the dropdown to explore different command categories!")
                else:
                    embed.set_footer(text="💡 Tip: Use 'latest' as a number to select your most recent Pokémon!")
                
                # Update dropdown to show current selection
                new_view = HelpView(self.pages, self.values[0])
                await interaction.response.edit_message(embed=embed, view=new_view)

        class HelpView(discord.ui.View):
            def __init__(self, pages, current_page="overview"):
                super().__init__(timeout=300)
                self.pages = pages
                self.add_item(HelpDropdown(pages, current_page))
            
            async def on_timeout(self):
                # Disable all components when view times out
                for item in self.children:
                    item.disabled = True
                try:
                    await self.message.edit(view=self)
                except:
                    pass
        
        # Create initial embed (overview page)
        page_data = pages["overview"]
        embed = discord.Embed(
            title=page_data["title"],
            description=page_data["description"],
            color=discord.Color.blue()
        )
        
        for field in page_data["fields"]:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field["inline"]
            )
        
        embed.set_footer(text="💡 Use the dropdown to explore different command categories!")
        
        view = HelpView(pages)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    @commands.command(name="select", aliases=["s"])
    async def prefix_select(self, ctx, number=None):
        """Select a Pokémon as your active one"""
        if number is None:
            return await ctx.reply("❌ Please provide a Pokémon number or 'latest'!")
        
        if str(number).lower() == "latest":
            # Find the most recent Pokémon
            pokemon = await self.collection.find_one(
                {"user_id": ctx.author.id}, 
                sort=[("pokemon_number", -1)]
            )
        elif str(number).isdigit():
            # Find by number
            pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": int(number)})
        else:
            return await ctx.reply("❌ Please provide a valid Pokémon number or 'latest'!")
        
        if not pokemon:
            return await ctx.reply("❌ You don't have a Pokémon with that number!")
        
        # Unselect all Pokémon for this user
        await self.collection.update_many(
            {"user_id": ctx.author.id},
            {"$set": {"selected": False}}
        )
        
        # Select the specified Pokémon
        await self.collection.update_one(
            {"_id": pokemon["_id"]},
            {"$set": {"selected": True}}
        )
        
        display_name = pokemon.get('nickname') or pokemon['pokemon_name']
        await ctx.reply(f"✅ **{display_name}** (#{pokemon['pokemon_number']}) is now your selected Pokémon!")

    @commands.command(name="invite", aliases=["inv"])
    async def prefix_invite(self, ctx):
        """Get an invite link for the bot"""
        class InviteView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)

            @discord.ui.button(label="📨 Invite Bot", style=discord.ButtonStyle.green, emoji="📨")
            async def invite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                invite_url = "https://discord.com/oauth2/authorize?client_id=1380984249632423996&permissions=0&integration_type=0&scope=bot"
                
                embed = discord.Embed(
                    title="📨 Bot Invite Link",
                    description=f"[Click here to invite me to your server!]({invite_url})",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Required Permissions",
                    value="• Send Messages\n• Embed Links\n• Attach Files\n• Use Slash Commands\n• Read Message History",
                    inline=False
                )
                embed.add_field(
                    name="🏰 Official Server",
                    value="[Join our Discord server!](https://discord.gg/udMnYbcuaf)\nGet help, updates, and chat with other trainers!",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)

            @discord.ui.button(label="🏰 Official Server", style=discord.ButtonStyle.blurple, emoji="🏰")
            async def server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="🏰 Official Discord Server",
                    description="[Join our Discord server!](https://discord.gg/udMnYbcuaf)",
                    color=discord.Color.blurple()
                )
                embed.add_field(
                    name="What you'll find:",
                    value="• Get help and support\n• Chat with other trainers\n• Bot updates and announcements\n• Community events\n• Feedback and suggestions",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="📨 Invite Pokémon Bot",
            description="Click the button below to get an invite link!",
            color=discord.Color.blue()
        )
        
        view = InviteView()
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="profile", aliases=["prof"])
    async def prefix_profile(self, ctx):
        """View your trainer profile"""
        user_id = ctx.author.id
        
        # Get all user's Pokemon
        all_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
        
        if not all_pokemon:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You don't have any Pokémon yet! Use `{prefix}start` to begin your journey.")
        
        # Get selected Pokemon for display
        selected_pokemon = next((p for p in all_pokemon if p.get("selected", False)), None)
        
        # Create profile card image
        profile_image = await self.create_profile_card(ctx.author, all_pokemon, selected_pokemon)
        
        if profile_image:
            file = discord.File(profile_image, filename="profile.png")
            await ctx.reply(file=file)
        else:
            await ctx.reply("❌ Failed to generate profile card. Please try again later.")

    @commands.command(name="balance", aliases=["bal", "money"])
    async def prefix_balance(self, ctx):
        """Check your coin and diamond balance"""
        try:
            coins, diamonds = await self.get_user_balance(ctx.author.id)
            
            # Create the balance embed with the requested design
            embed = discord.Embed(color=0x58a64e)
            
            # Set author with user avatar and name
            embed.set_author(
                name=f"{ctx.author.display_name}'s balance",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            
            # Add balance fields in the format shown
            embed.add_field(
                name="Pokécoins",
                value=f"{coins:,}",
                inline=True
            )
            embed.add_field(
                name="Diamonds", 
                value=f"{diamonds:,}",
                inline=True
            )
            
            # Set thumbnail to user avatar
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply("❌ Failed to retrieve balance. Please try again later.")

    async def create_friendship_card(self, pokemon, user):
        """Create a friendship progress card image"""
        try:
            # Card dimensions and colors
            width, height = 800, 500
            bg_color = (30, 32, 36)  # Dark background
            primary_color = (88, 166, 78)  # Green
            secondary_color = (255, 193, 7)  # Gold
            text_color = (255, 255, 255)  # White
            gray_color = (153, 153, 153)  # Gray
            
            # Create image and draw object
            img = Image.new('RGB', (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Try to load fonts
            try:
                title_font = ImageFont.truetype("arial.ttf", 28)
                header_font = ImageFont.truetype("arial.ttf", 22)
                text_font = ImageFont.truetype("arial.ttf", 18)
                small_font = ImageFont.truetype("arial.ttf", 14)
            except:
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Get friendship data
            current_friendship = pokemon.get('friendship', 0)
            max_friendship = 255
            is_selected = pokemon.get('selected', False)
            is_favorite = pokemon.get('favorite', False)
            has_nickname = bool(pokemon.get('nickname'))
            
            # Calculate friendship generation rate
            base_rate = 2  # base rate per hour
            multipliers = []
            if is_selected:
                multipliers.append("Selected (+2/hr)")
            if is_favorite:
                multipliers.append("Favorite (+2/hr)")
            if has_nickname:
                multipliers.append("Nicknamed (+2/hr)")
            
            total_rate = base_rate + (len(multipliers) * 2)
            
            # Check evolution data
            evolution_key = None
            for key in EVOLUTION_DATA.keys():
                if key.lower() == pokemon["pokemon_name"].lower():
                    evolution_key = key
                    break
            
            can_evolve_now = False
            next_evolution = None
            friendship_needed = None
            hours_to_evolution = None
            
            if evolution_key:
                evolution_data = EVOLUTION_DATA[evolution_key]
                required_friendship = evolution_data["friendship_required"]
                evolves_to = evolution_data["evolves_to"]
                
                if current_friendship >= required_friendship:
                    can_evolve_now = True
                    next_evolution = evolves_to if isinstance(evolves_to, str) else evolves_to[0]
                else:
                    next_evolution = evolves_to if isinstance(evolves_to, str) else evolves_to[0]
                    friendship_needed = required_friendship - current_friendship
                    if total_rate > 0:
                        hours_to_evolution = friendship_needed / total_rate
            
            # Draw border
            border_width = 4
            draw.rectangle([0, 0, width-1, height-1], outline=primary_color, width=border_width)
            
            # Pokemon name and level
            pokemon_name = pokemon.get('nickname') or pokemon['pokemon_name']
            shiny_text = "✨ " if pokemon.get("shiny", False) else ""
            draw.text((30, 30), f"{shiny_text}{pokemon_name}", fill=text_color, font=title_font)
            draw.text((30, 70), f"Level {pokemon['level']}", fill=gray_color, font=text_font)
            
            # Friendship header
            draw.text((30, 120), "💖 Friendship Progress", fill=secondary_color, font=header_font)
            
            # Progress bar
            bar_x, bar_y = 30, 160
            bar_width, bar_height = 500, 30
            
            # Background bar
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], 
                         fill=(60, 60, 60), outline=gray_color, width=2)
            
            # Progress bar
            progress = current_friendship / max_friendship
            progress_width = int(bar_width * progress)
            if progress_width > 0:
                # Gradient effect (simplified)
                color = primary_color if not can_evolve_now else secondary_color
                draw.rectangle([bar_x, bar_y, bar_x + progress_width, bar_y + bar_height], fill=color)
            
            # Friendship text
            friendship_text = f"{current_friendship}/{max_friendship}"
            draw.text((bar_x + bar_width//2, bar_y + bar_height + 10), friendship_text, 
                     fill=text_color, font=text_font, anchor="mt")
            
            # Generation rate section
            draw.text((30, 230), "⚡ Generation Rate", fill=secondary_color, font=header_font)
            draw.text((30, 270), f"{total_rate} friendship/hour", fill=text_color, font=text_font)
            
            if multipliers:
                y_offset = 300
                for multiplier in multipliers:
                    draw.text((30, y_offset), f"• {multiplier}", fill=primary_color, font=small_font)
                    y_offset += 25
            else:
                draw.text((30, 300), "• No active multipliers", fill=gray_color, font=small_font)
                draw.text((30, 325), "  (Select, favorite, or nickname your Pokémon!)", fill=gray_color, font=small_font)
            
            # Evolution section
            evolution_y = 380
            if next_evolution:
                if can_evolve_now:
                    draw.text((30, evolution_y), "🌟 Ready to Evolve!", fill=secondary_color, font=header_font)
                    draw.text((30, evolution_y + 35), f"Can evolve into {next_evolution}!", fill=text_color, font=text_font)
                else:
                    draw.text((30, evolution_y), "🕒 Next Evolution", fill=secondary_color, font=header_font)
                    draw.text((30, evolution_y + 35), f"Evolves into {next_evolution}", fill=text_color, font=text_font)
                    if hours_to_evolution is not None:
                        if hours_to_evolution < 1:
                            time_text = f"in {int(hours_to_evolution * 60)} minutes"
                        elif hours_to_evolution < 24:
                            time_text = f"in {hours_to_evolution:.1f} hours"
                        else:
                            days = hours_to_evolution / 24
                            time_text = f"in {days:.1f} days"
                        draw.text((30, evolution_y + 60), f"Needs {friendship_needed} more friendship ({time_text})", 
                                fill=gray_color, font=small_font)
            else:
                draw.text((30, evolution_y), "🏆 Final Evolution", fill=secondary_color, font=header_font)
                draw.text((30, evolution_y + 35), "This Pokémon cannot evolve further", fill=gray_color, font=text_font)
            
            # Try to add Pokemon sprite
            pokemon_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == pokemon["pokemon_name"].lower()), None)
            if pokemon_data and 'id' in pokemon_data:
                sprite_path = f"full/{pokemon_data['id']}.png"
                if os.path.exists(sprite_path):
                    try:
                        sprite = Image.open(sprite_path).convert("RGBA")
                        # Resize sprite
                        sprite.thumbnail((150, 150), Image.Resampling.LANCZOS)
                        # Position sprite on the right side
                        sprite_x = width - 180
                        sprite_y = 50
                        img.paste(sprite, (sprite_x, sprite_y), sprite)
                    except Exception as e:
                        print(f"Error loading Pokemon sprite: {e}")
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
        except Exception as e:
            print(f"Error creating friendship card: {e}")
            return None

    @commands.command(name="friendship", aliases=["friend"])
    async def prefix_friendship(self, ctx):
        """View friendship progress for your selected Pokémon"""
        try:
            # Get selected Pokemon
            pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})
            
            if not pokemon:
                prefix = ctx.bot.get_primary_prefix()
                return await ctx.reply(f"❌ You don't have a selected Pokémon! Use `{prefix}select <number>` first.")
            
            # Create friendship card image
            friendship_image = await self.create_friendship_card(pokemon, ctx.author)
            
            if friendship_image:
                file = discord.File(friendship_image, filename="friendship.png")
                embed = discord.Embed(
                    title="💖 Friendship Status",
                    description=f"Friendship progress for **{pokemon.get('nickname') or pokemon['pokemon_name']}**",
                    color=0x58a64e
                )
                embed.set_image(url="attachment://friendship.png")
                await ctx.reply(embed=embed, file=file)
            else:
                await ctx.reply("❌ Failed to generate friendship card. Please try again later.")
                
        except Exception as e:
            await ctx.reply("❌ Something went wrong checking friendship. Please try again later.")






    





    @commands.command(name="evolve", aliases=["evo"])
    async def prefix_evolve(self, ctx, number = None):
        """Evolve your selected Pokemon or specify a Pokemon number"""
        try:
            # Get the Pokemon to evolve
            if number and str(number).isdigit():
                pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": int(number)})
            else:
                pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})

            if not pokemon:
                return await ctx.reply("❌ Pokemon not found! Make sure you've selected a Pokemon or provided a valid number.")

            can_evolve, evolves_to, required_friendship = await self.can_evolve(pokemon)
            
            if not can_evolve:
                current_friendship = pokemon.get("friendship", 0)
                if evolves_to:
                    return await ctx.reply(f"❌ Your {pokemon['pokemon_name']} cannot evolve yet!\nCurrent friendship: {current_friendship}/{required_friendship}")
                else:
                    return await ctx.reply(f"❌ Your {pokemon['pokemon_name']} cannot evolve!")
            
            # Check if there are multiple evolution options
            if isinstance(evolves_to, list) and len(evolves_to) > 1:
                # Multiple evolution paths - show dropdown
                class EvolutionSelect(Select):
                    def __init__(self, evolutions, pokemon_data, parent_ctx):
                        self.pokemon = pokemon_data
                        self.ctx = parent_ctx
                        options = [discord.SelectOption(label=evo, value=evo) for evo in evolutions]
                        super().__init__(placeholder="Choose evolution path...", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        if interaction.user.id != self.ctx.author.id:
                            return await interaction.response.send_message("❌ Only the command user can select evolution!", ephemeral=True)
                        
                        chosen_evolution = self.values[0]
                        success, message = await ctx.cog.evolve_pokemon(self.pokemon, chosen_evolution)
                        
                        if success:
                            await interaction.response.edit_message(content=message, view=None)
                        else:
                            await interaction.response.edit_message(content=f"❌ Evolution failed: {message}", view=None)

                class EvolutionView(View):
                    def __init__(self, evolutions, pokemon_data, parent_ctx):
                        super().__init__(timeout=60)
                        self.add_item(EvolutionSelect(evolutions, pokemon_data, parent_ctx))

                view = EvolutionView(evolves_to, pokemon, ctx)
                embed = discord.Embed(
                    title="🌟 Choose Evolution Path",
                    description=f"**{pokemon['pokemon_name']}** can evolve into multiple Pokemon!\nSelect your preferred evolution:",
                    color=0x58a64e
                )
                await ctx.reply(embed=embed, view=view)
            else:
                # Single evolution path
                success, message = await self.evolve_pokemon(pokemon)
                await ctx.reply(message)
                
        except Exception as e:
            print(f"Error in prefix_evolve: {e}")
            await ctx.reply("❌ An error occurred during evolution.")

    @commands.command(name="reindex")
    async def prefix_reindex(self, ctx):
        """Reindex all Pokemon numbers to remove gaps and duplicates"""
        try:
            # Get all Pokemon for the user sorted by current pokemon_number
            user_pokemon = await self.collection.find({"user_id": ctx.author.id}).sort("pokemon_number", 1).to_list(length=None)
            
            if not user_pokemon:
                return await ctx.reply("❌ You don't have any Pokemon to reindex!")
            
            # Create confirmation embed
            embed = discord.Embed(
                title="🔄 Confirm Pokemon Reindex",
                description=f"This will renumber all your Pokemon from 1 to {len(user_pokemon)} sequentially.\n"
                           f"**Total Pokemon:** {len(user_pokemon)}\n\n"
                           f"⚠️ **Warning:** This will change all Pokemon numbers!\n"
                           f"Any bookmarked Pokemon numbers will need to be updated.",
                color=0xffa500
            )
            embed.add_field(
                name="What this does:",
                value="• Removes duplicate numbers\n"
                      "• Fills gaps in numbering\n"
                      "• Makes numbers sequential (1, 2, 3, ...)\n"
                      "• Preserves all Pokemon data",
                inline=False
            )
            embed.set_footer(text="This action cannot be undone!")
            
            class ReindexView(View):
                def __init__(self, pokemon_list, cog_instance):
                    super().__init__(timeout=60)
                    self.pokemon_list = pokemon_list
                    self.cog = cog_instance
                
                @discord.ui.button(label="✅ Confirm Reindex", style=discord.ButtonStyle.green)
                async def confirm_reindex(self, interaction: discord.Interaction, button: Button):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("❌ Only the command user can confirm!", ephemeral=True)
                    
                    # Perform the reindexing
                    reindexed_count = 0
                    
                    for index, pokemon in enumerate(self.pokemon_list, start=1):
                        if pokemon["pokemon_number"] != index:
                            await self.cog.collection.update_one(
                                {"_id": pokemon["_id"]},
                                {"$set": {"pokemon_number": index}}
                            )
                            reindexed_count += 1
                    
                    success_embed = discord.Embed(
                        title="✅ Reindex Complete!",
                        description=f"Successfully reindexed {len(self.pokemon_list)} Pokemon!\n"
                                   f"**Pokemon renumbered:** {reindexed_count}\n"
                                   f"**Numbers now:** 1 to {len(self.pokemon_list)}",
                        color=0x00ff00
                    )
                    success_embed.set_footer(text="All Pokemon numbers are now sequential with no gaps!")
                    
                    await interaction.response.edit_message(embed=success_embed, view=None)
                
                @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
                async def cancel_reindex(self, interaction: discord.Interaction, button: Button):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("❌ Only the command user can cancel!", ephemeral=True)
                    
                    cancel_embed = discord.Embed(
                        title="❌ Reindex Cancelled",
                        description="Your Pokemon numbers were not changed.",
                        color=0xff0000
                    )
                    await interaction.response.edit_message(embed=cancel_embed, view=None)
            
            view = ReindexView(user_pokemon, self)
            await ctx.reply(embed=embed, view=view)
            
        except Exception as e:
            print(f"Error in prefix_reindex: {e}")
            await ctx.reply("❌ An error occurred while reindexing Pokemon.")



    @commands.command(name="pokedex", aliases=["d", "dex"])
    async def prefix_pokedex(self, ctx, *, pokemon_name=None):
        """View Pokédex information"""
        user_id = ctx.author.id
        
        if not pokemon_name:
            # Show caught/uncaught overview with Pokemon emojis
            all_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
            caught_species = set(p["pokemon_name"].lower() for p in all_pokemon)
            
            # Calculate progress
            total_pokemon = len(POKEMON_DATA)
            caught_count = len(caught_species)
            
            # Create pages for pagination (show 10 Pokemon per page to avoid Discord's 1024 char limit)
            pokemon_per_page = 10
            pages = []
            
            # Sort Pokemon by ID
            sorted_pokemon = sorted(POKEMON_DATA.items(), key=lambda x: int(x[0]))
            
            for i in range(0, len(sorted_pokemon), pokemon_per_page):
                page_pokemon = sorted_pokemon[i:i + pokemon_per_page]
                
                embed = discord.Embed(
                    title="Your pokédex",
                    description=f"You've caught **{caught_count}** out of **{total_pokemon}** pokémon!",
                    color=0x2f3136
                )
                
                # Create Pokemon list for this page
                pokemon_list = ""
                for pokemon_id, data in page_pokemon:
                    pokemon_name_item = data["name"]
                    is_caught = pokemon_name_item.lower() in caught_species
                    
                    # Use same emoji system as b!pokemon command
                    emoji = self.bot.pokemon_emojis.get(str(data["id"]), "") if data else ""
                    
                    if is_caught:
                        # Caught Pokemon - show with emoji and name
                        pokemon_list += f"{emoji} **{pokemon_name_item.title()}** #{pokemon_id}\n"
                    else:
                        # Not caught - show grayed out
                        pokemon_list += f"{emoji} ~~{pokemon_name_item.title()}~~ #{pokemon_id} - **Not caught yet!**\n"
                
                embed.add_field(
                    name=f"Pokémon {i+1}-{min(i+pokemon_per_page, len(sorted_pokemon))}",
                    value=pokemon_list,
                    inline=False
                )
                
                embed.set_footer(text=f"Showing {i+1}-{min(i+pokemon_per_page, len(sorted_pokemon))} out of {len(sorted_pokemon)}")
                pages.append(embed)
            
            # Create pagination view
            class PokedexPaginationView(View):
                def __init__(self, embeds, author):
                    super().__init__(timeout=300)
                    self.embeds = embeds
                    self.current_page = 0
                    self.author = author
                
                @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
                async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.author.id:
                        return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
                    
                    if self.current_page > 0:
                        self.current_page -= 1
                        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
                    else:
                        await interaction.response.defer()
                
                @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
                async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.author.id:
                        return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
                    
                    if self.current_page < len(self.embeds) - 1:
                        self.current_page += 1
                        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
                    else:
                        await interaction.response.defer()
            
            if len(pages) > 1:
                view = PokedexPaginationView(pages, ctx.author)
                await ctx.reply(embed=pages[0], view=view)
            else:
                await ctx.reply(embed=pages[0])
            
        else:
            # Show specific Pokémon info with navigation
            pokemon_name = pokemon_name.lower().strip()
            
            # Find the Pokémon in pokedex data
            found_pokemon = None
            pokemon_list = []
            for pokemon_id, data in POKEMON_DATA.items():
                if isinstance(data, dict):
                    pokemon_list.append((pokemon_id, data))
                    if data.get("name", "").lower() == pokemon_name:
                    found_pokemon = data
                        current_index = len(pokemon_list) - 1
            
            if not found_pokemon:
                return await ctx.reply(f"❌ Pokémon **{pokemon_name}** not found in the Pokédex!")
            
            # Sort by ID for navigation
            pokemon_list.sort(key=lambda x: int(x[0]))
            current_index = next(i for i, (pid, data) in enumerate(pokemon_list) if data.get("name", "").lower() == pokemon_name)
            
            # Create detailed embed
            embed = await self.create_pokedex_embed(found_pokemon, user_id, False)
            
            # Create navigation view
            view = self.PokedexDetailView(self, pokemon_list, current_index, user_id, ctx.author.id)
            
            # Set image to Pokémon sprite if available (large image at bottom)
            image_path = f"full/{found_pokemon['id']}.png"
            if os.path.exists(image_path):
                file = discord.File(image_path, filename=f"{found_pokemon['id']}.png")
                embed.set_image(url=f"attachment://{found_pokemon['id']}.png")
                await ctx.reply(embed=embed, file=file, view=view)
            else:
                await ctx.reply(embed=embed, view=view)

    async def create_pokedex_embed(self, pokemon_data, user_id, is_shiny=False):
        """Create a pokedex embed for a specific Pokemon"""
        user_pokemon = await self.collection.find_one({"user_id": user_id, "pokemon_name": {"$regex": f"^{pokemon_data['name']}$", "$options": "i"}})
        caught = bool(user_pokemon)
        
            embed = discord.Embed(
            title=f"#{pokemon_data['id']:03d} — {pokemon_data['name'].title()}",
                color=0x3b82f6 if caught else 0x6b7280
            )
            
            # Status
            status = "✅ Caught" if caught else "❌ Not caught"
            embed.add_field(name="Status", value=status, inline=True)
            
            # Types
        types_text = " ".join([f"🔹 {t.title()}" for t in pokemon_data["types"]])
            embed.add_field(name="Types", value=types_text, inline=True)
            
            # Physical info
        height_m = pokemon_data["height"] / 10
        weight_kg = pokemon_data["weight"] / 10
            embed.add_field(name="Height", value=f"{height_m}m", inline=True)
            embed.add_field(name="Weight", value=f"{weight_kg}kg", inline=True)
            
        # Base stats with new format
        stats = pokemon_data["stats"]
            stats_text = ""
        stat_configs = [
            ("hp", "HP", "🟢"),
            ("attack", "Attack", "🔴"),
            ("defense", "Defense", "⚪"),
            ("special-attack", "Sp. Atk", "🔴"),
            ("special-defense", "Sp. Def", "⚪"),
            ("speed", "Speed", "🟢")
        ]
            
            total_stats = 0
        for stat_key, stat_name, emoji in stat_configs:
                stat_value = stats[stat_key]
                total_stats += stat_value
            # Create bar with ▰▱ characters (12 segments total)
            bar_length = min(12, int((stat_value / 255) * 12))  # 255 is max stat
            bar = "▰" * bar_length + "▱" * (12 - bar_length)
            stats_text += f"{emoji} {stat_name}: {stat_value} {bar}\n"
        
        stats_text += f"📊 Total: {total_stats}"
            embed.add_field(name="Base Stats", value=stats_text, inline=False)
            
            # Abilities
            abilities_text = ""
        for ability in pokemon_data["abilities"]:
                ability_name = ability["name"].replace("-", " ").title()
                if ability["is_hidden"]:
                    abilities_text += f"🔸 {ability_name} (Hidden)\n"
                else:
                    abilities_text += f"🔹 {ability_name}\n"
            embed.add_field(name="Abilities", value=abilities_text, inline=True)
            
            # If caught, show user's best specimen
            if caught:
                # Find user's best version (highest total IVs)
            all_user_pokemon = await self.collection.find({"user_id": user_id, "pokemon_name": {"$regex": f"^{pokemon_data['name']}$", "$options": "i"}}).to_list(length=None)
                
                if all_user_pokemon:
                    best_pokemon = max(all_user_pokemon, key=lambda p: sum([
                        p.get("hp_iv", 0), p.get("attack_iv", 0), p.get("defense_iv", 0),
                        p.get("sp_attack_iv", 0), p.get("sp_defense_iv", 0), p.get("speed_iv", 0)
                    ]))
                    
                    total_iv = sum([
                        best_pokemon.get("hp_iv", 0), best_pokemon.get("attack_iv", 0), 
                        best_pokemon.get("defense_iv", 0), best_pokemon.get("sp_attack_iv", 0),
                        best_pokemon.get("sp_defense_iv", 0), best_pokemon.get("speed_iv", 0)
                    ])
                    iv_percentage = (total_iv / 186) * 100
                    
                    shiny_text = "✨ " if best_pokemon.get("shiny", False) else ""
                    best_text = f"{shiny_text}Level {best_pokemon['level']}\n"
                    best_text += f"IV: {iv_percentage:.1f}% ({total_iv}/186)\n"
                    best_text += f"Caught: {len(all_user_pokemon)} time{'s' if len(all_user_pokemon) != 1 else ''}"
                    
                    embed.add_field(name="Your Best", value=best_text, inline=True)
            
            # Add custom/event Pokemon indicator
        if pokemon_data.get("custom", False):
            event_emoji = self.get_event_emoji(pokemon_data.get("event_tag", ""))
                embed.add_field(
                    name=f"{event_emoji} Special Pokemon",
                value=f"**Event:** {pokemon_data.get('event_tag', 'Custom Pokemon')}\n{pokemon_data.get('description', 'A unique Pokemon!')}", 
                    inline=False
                )
            
        return embed

    class PokedexDetailView(discord.ui.View):
        def __init__(self, cog, pokemon_list, current_index, user_id, author_id):
            super().__init__(timeout=300)
            self.cog = cog
            self.pokemon_list = pokemon_list
            self.current_index = current_index
            self.user_id = user_id
            self.author_id = author_id
            self.is_shiny = False
        
        @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
        async def previous_pokemon(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
            
            if self.current_index > 0:
                self.current_index -= 1
                await self.update_display(interaction)
            else:
                await interaction.response.defer()
        
        @discord.ui.button(label="✨", style=discord.ButtonStyle.primary)
        async def toggle_shiny(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
            
            self.is_shiny = not self.is_shiny
            button.label = "✨" if self.is_shiny else "⭐"
            button.style = discord.ButtonStyle.success if self.is_shiny else discord.ButtonStyle.primary
            await self.update_display(interaction)
        
        @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
        async def next_pokemon(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
            
            if self.current_index < len(self.pokemon_list) - 1:
                self.current_index += 1
                await self.update_display(interaction)
            else:
                await interaction.response.defer()
        
        async def update_display(self, interaction: discord.Interaction):
            pokemon_id, pokemon_data = self.pokemon_list[self.current_index]
            embed = await self.cog.create_pokedex_embed(pokemon_data, self.user_id, self.is_shiny)
            
            # Determine image path based on shiny toggle
            if self.is_shiny:
                image_path = f"full_shiny/{pokemon_id}_full.png"
            else:
                image_path = f"full/{pokemon_id}.png"
            
            try:
                if os.path.exists(image_path):
                    file = discord.File(image_path, filename=f"{pokemon_id}.png")
                    embed.set_image(url=f"attachment://{pokemon_id}.png")
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"Error updating pokedex display: {e}")
                await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    @commands.command(name="moveset", aliases=["ms"])
    async def prefix_moveset(self, ctx, *, pokemon_name=None):
        """Show all moves a Pokemon can learn by leveling up"""
        if not pokemon_name:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Please specify a Pokemon name! Example: `{prefix}moveset pikachu`")
        
        pokemon_name = pokemon_name.lower().strip()
        
        # Find the Pokemon in pokedex data
        found_pokemon = None
        for pokemon_id, data in POKEMON_DATA.items():
            if isinstance(data, dict) and data.get("name", "").lower() == pokemon_name:
                found_pokemon = data
                break
        
        if not found_pokemon:
            return await ctx.reply(f"❌ Pokemon **{pokemon_name}** not found in the Pokedex!")
        
        # Get level-up moves
        level_moves = []
        for move in found_pokemon.get("moves", []):
            if move["learn_method"] == "level-up":
                level_moves.append({
                    "name": move["name"].replace("-", " ").title(),
                    "level": move["level_learned"]
                })
        
        if not level_moves:
            return await ctx.reply(f"❌ {found_pokemon['name'].title()} has no level-up moves in the database!")
        
        # Sort by level
        level_moves.sort(key=lambda x: x["level"])
        
        # Create embed
        embed = discord.Embed(
            title=f"📚 {found_pokemon['name'].title()} - Level-up Moveset",
            color=0x3498db
        )
        
        # Group moves by level ranges for better display
        move_text = ""
        for move in level_moves:
            level = move["level"]
            name = move["name"]
            move_text += f"**Lv.{level:2d}** - {name}\n"
        
        # Split into multiple fields if too long
        if len(move_text) > 1024:
            # Split moves into chunks
            moves_per_field = len(level_moves) // 3 + 1
            for i in range(0, len(level_moves), moves_per_field):
                chunk = level_moves[i:i + moves_per_field]
                chunk_text = ""
                for move in chunk:
                    chunk_text += f"**Lv.{move['level']:2d}** - {move['name']}\n"
                
                field_name = f"Moves {i+1}-{min(i+moves_per_field, len(level_moves))}"
                embed.add_field(name=field_name, value=chunk_text, inline=True)
        else:
            embed.add_field(name="All Level-up Moves", value=move_text, inline=False)
        
        embed.set_footer(text=f"Total moves: {len(level_moves)} | Use !learn to teach moves to your Pokemon")
        await ctx.reply(embed=embed)

    @commands.command(name="learn")
    async def prefix_learn(self, ctx, number=None, *, move_name=None):
        """Teach a move to your Pokemon"""
        if not number or not move_name:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}learn <pokemon_number> <move_name>`\nExample: `{prefix}learn 1 tackle`")
        
        if not str(number).isdigit():
            return await ctx.reply("❌ Please provide a valid Pokemon number!")
        
        number = int(number)
        move_name = move_name.lower().strip().replace(" ", "-")
        
        # Find the Pokemon
        pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        if not pokemon:
            return await ctx.reply(f"❌ You don't have a Pokemon with number {number}!")
        
        # Get Pokemon data from pokedex
        poke_data = None
        for pokemon_id, data in POKEMON_DATA.items():
            if data["name"].lower() == pokemon["pokemon_name"].lower():
                poke_data = data
                break
        
        if not poke_data:
            return await ctx.reply("❌ Pokemon data not found!")
        
        # Check if Pokemon can learn this move by level-up
        learnable_move = None
        for move in poke_data.get("moves", []):
            if move["learn_method"] == "level-up" and move["name"].lower() == move_name.lower():
                learnable_move = move
                break
        
        if not learnable_move:
            return await ctx.reply(f"❌ **{pokemon['pokemon_name']}** cannot learn **{move_name.replace('-', ' ').title()}** by leveling up!")
        
        # Check if Pokemon is high enough level
        required_level = learnable_move["level_learned"]
        if pokemon["level"] < required_level:
            return await ctx.reply(f"❌ **{pokemon['pokemon_name']}** needs to be level **{required_level}** to learn **{learnable_move['name'].replace('-', ' ').title()}**!\nCurrent level: {pokemon['level']}")
        
        # Check if Pokemon already knows this move
        current_moves = [
            pokemon.get("move1"), pokemon.get("move2"), 
            pokemon.get("move3"), pokemon.get("move4")
        ]
        move_display_name = learnable_move['name'].replace('-', ' ').title()
        
        if move_display_name in current_moves:
            return await ctx.reply(f"❌ **{pokemon['pokemon_name']}** already knows **{move_display_name}**!")
        
        # Find an empty move slot or ask to replace
        empty_slot = None
        for i, move in enumerate(current_moves, 1):
            if not move or move == "None":
                empty_slot = f"move{i}"
                break
        
        if empty_slot:
            # Learn move in empty slot
            await self.collection.update_one(
                {"user_id": ctx.author.id, "pokemon_number": number},
                {"$set": {empty_slot: move_display_name}}
            )
            await ctx.reply(f"✅ **{pokemon['pokemon_name']}** learned **{move_display_name}**!")
        else:
            # All slots full - need to replace
            moves_text = "\n".join([f"{i+1}. {move}" for i, move in enumerate(current_moves) if move and move != "None"])
            embed = discord.Embed(
                title="❓ Replace a Move?",
                description=f"**{pokemon['pokemon_name']}** wants to learn **{move_display_name}** but already knows 4 moves!\n\n**Current moves:**\n{moves_text}\n\nWhich move should be forgotten? (Reply with 1-4 or 'cancel')",
                color=0xffa500
            )
            await ctx.reply(embed=embed)
            
            # Wait for user response
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and (m.content.lower() in ['1', '2', '3', '4', 'cancel'])
            
            try:
                response = await self.bot.wait_for('message', check=check, timeout=30.0)
                if response.content.lower() == 'cancel':
                    return await ctx.reply("❌ Move learning cancelled.")
                
                slot_num = int(response.content)
                slot_name = f"move{slot_num}"
                old_move = current_moves[slot_num - 1]
                
                await self.collection.update_one(
                    {"user_id": ctx.author.id, "pokemon_number": number},
                    {"$set": {slot_name: move_display_name}}
                )
                await ctx.reply(f"✅ **{pokemon['pokemon_name']}** forgot **{old_move}** and learned **{move_display_name}**!")
                
            except asyncio.TimeoutError:
                await ctx.reply("⏰ Move learning timed out.")

    @commands.command(name="moves")
    async def prefix_moves(self, ctx, number=None):
        """Show moves a Pokemon knows and can learn"""
        if number and str(number).lower() == "latest":
            pokemon = await self.collection.find_one(
                {"user_id": ctx.author.id}, 
                sort=[("pokemon_number", -1)]
            )
        elif number and str(number).isdigit():
            pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": int(number)})
        else:
            pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})
        
        if not pokemon:
            if number and str(number).isdigit():
                return await ctx.reply(f"❌ You don't have a Pokemon with number {number}!")
            else:
                prefix = ctx.bot.get_primary_prefix()
                return await ctx.reply(f"❌ You haven't selected a Pokemon yet. Use `{prefix}select <number>` to select one.")
        
        # Get Pokemon data from pokedex
        poke_data = None
        for pokemon_id, data in POKEMON_DATA.items():
            if data["name"].lower() == pokemon["pokemon_name"].lower():
                poke_data = data
                break
        
        if not poke_data:
            return await ctx.reply("❌ Pokemon data not found!")
        
        # Get current moves
        current_moves = []
        for i in range(1, 5):
            move = pokemon.get(f"move{i}")
            if move and move != "None":
                current_moves.append(move)
        
        # Get learnable moves by current level
        learnable_moves = []
        for move in poke_data.get("moves", []):
            if move["learn_method"] == "level-up" and move["level_learned"] <= pokemon["level"]:
                move_name = move["name"].replace("-", " ").title()
                if move_name not in current_moves:
                    learnable_moves.append({
                        "name": move_name,
                        "level": move["level_learned"]
                    })
        
        # Get future moves (can learn at higher levels)
        future_moves = []
        for move in poke_data.get("moves", []):
            if move["learn_method"] == "level-up" and move["level_learned"] > pokemon["level"]:
                future_moves.append({
                    "name": move["name"].replace("-", " ").title(),
                    "level": move["level_learned"]
                })
        
        # Sort moves by level
        learnable_moves.sort(key=lambda x: x["level"])
        future_moves.sort(key=lambda x: x["level"])
        
        # Create embeds for pagination
        display_name = pokemon.get('nickname') or pokemon['pokemon_name']
        embeds = []
        
        # Page 1: Current Moves + Can Learn Now (first 15)
        embed1 = discord.Embed(
            title=f"⚔️ {display_name} - Move Information",
            description=f"Level {pokemon['level']} {pokemon['pokemon_name']} (Page 1/3)",
            color=0x3498db
        )
        
        # Current moves
        if current_moves:
            moves_text = "\n".join([f"{i+1}. {move}" for i, move in enumerate(current_moves)])
            embed1.add_field(name="🎯 Current Moves", value=moves_text, inline=False)
        else:
            embed1.add_field(name="🎯 Current Moves", value="No moves learned yet!", inline=False)
        
        # Can learn now (first 15)
        if learnable_moves:
            can_learn_text = "\n".join([f"**Lv.{move['level']}** - {move['name']}" for move in learnable_moves[:15]])
            if len(learnable_moves) > 15:
                can_learn_text += f"\n\n*({len(learnable_moves) - 15} more moves on next page)*"
            embed1.add_field(name="📚 Can Learn Now", value=can_learn_text or "None available", inline=False)
        else:
            embed1.add_field(name="📚 Can Learn Now", value="None available", inline=False)
        
        prefix = ctx.bot.get_primary_prefix()
        embed1.set_footer(text=f"Use {prefix}learn {pokemon['pokemon_number']} <move_name> to teach a move")
        embeds.append(embed1)
        
        # Page 2: Remaining Can Learn Now moves
        if len(learnable_moves) > 15:
            embed2 = discord.Embed(
                title=f"⚔️ {display_name} - Move Information",
                description=f"Level {pokemon['level']} {pokemon['pokemon_name']} (Page 2/3)",
                color=0x3498db
            )
            
            remaining_learnable = learnable_moves[15:]
            can_learn_text2 = "\n".join([f"**Lv.{move['level']}** - {move['name']}" for move in remaining_learnable])
            embed2.add_field(name="📚 Can Learn Now (continued)", value=can_learn_text2, inline=False)
            embed2.set_footer(text=f"Use {prefix}learn {pokemon['pokemon_number']} <move_name> to teach a move")
            embeds.append(embed2)
        
        # Page 3: Future Moves
        embed3 = discord.Embed(
            title=f"⚔️ {display_name} - Move Information",
            description=f"Level {pokemon['level']} {pokemon['pokemon_name']} (Page {len(embeds) + 1}/3)",
            color=0x3498db
        )
        
        if future_moves:
            # Split future moves into chunks of 20
            chunks = [future_moves[i:i+20] for i in range(0, len(future_moves), 20)]
            for i, chunk in enumerate(chunks):
                future_text = "\n".join([f"**Lv.{move['level']}** - {move['name']}" for move in chunk])
                field_name = "🔮 Future Moves" if i == 0 else f"🔮 Future Moves (continued {i+1})"
                embed3.add_field(name=field_name, value=future_text, inline=False)
        else:
            embed3.add_field(name="🔮 Future Moves", value="No future moves available", inline=False)
        
        embed3.set_footer(text=f"Level up to learn these moves | {prefix}moveset {pokemon['pokemon_name']} for full list")
        embeds.append(embed3)
        
        # If only one embed, send it directly
        if len(embeds) == 1:
            await ctx.reply(embed=embeds[0])
        else:
            # Create pagination view
            class MovesPaginationView(View):
                def __init__(self, embeds, author):
                    super().__init__(timeout=300)
                    self.embeds = embeds
                    self.author = author
                    self.current_page = 0
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple)
                async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.author.id:
                        return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
                    
                    self.current_page = (self.current_page - 1) % len(self.embeds)
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
                async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.author.id:
                        return await interaction.response.send_message("❌ Only the command user can navigate!", ephemeral=True)
                    
                    self.current_page = (self.current_page + 1) % len(self.embeds)
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            
            view = MovesPaginationView(embeds, ctx.author)
            await ctx.reply(embed=embeds[0], view=view)

    @commands.command(name="moveinfo", aliases=["mi"])
    async def prefix_moveinfo(self, ctx, *, move_name=None):
        """Show detailed information about a move"""
        if not move_name:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Please specify a move name! Example: `{prefix}moveinfo tackle`")
        
        move_name = move_name.lower().strip().replace(" ", "-")
        
        # First, try to find the move in our moves database
        move_data = None
        for move_id, data in MOVES_DATA.items():
            if data["name"].lower() == move_name.lower():
                move_data = data
                break
        
        if not move_data:
            return await ctx.reply(f"❌ Move **{move_name.replace('-', ' ').title()}** not found in the moves database!")
        
        move_display_name = move_data["name"].replace("-", " ").title()
        
        # Get type color for embed
        type_colors = {
            "normal": 0xA8A878, "fire": 0xF08030, "water": 0x6890F0, "electric": 0xF8D030,
            "grass": 0x78C850, "ice": 0x98D8D8, "fighting": 0xC03028, "poison": 0xA040A0,
            "ground": 0xE0C068, "flying": 0xA890F0, "psychic": 0xF85888, "bug": 0xA8B820,
            "rock": 0xB8A038, "ghost": 0x705898, "dragon": 0x7038F8, "dark": 0x705848,
            "steel": 0xB8B8D0, "fairy": 0xEE99AC
        }
        
        color = type_colors.get(move_data["type"], 0x3498db)
        
        # Create a clean card-style description
        effect_desc = move_data.get("short_effect", "No description available.")
        if move_data.get("effect_chance"):
            effect_desc = f"Has a {move_data['effect_chance']}% chance to {effect_desc.lower()}"
        
        # Create embed with clean card layout
        embed = discord.Embed(
            title=move_display_name,
            description=effect_desc,
            color=color
        )
        
        # Target section
        if move_data.get("target"):
            target_names = {
                "selected-pokemon": "One other Pokémon on the field, selected by the trainer.",
                "all-opponents": "All opponents", 
                "user": "The user",
                "users-field": "User's side of the field",
                "opponents-field": "Opponent's side of the field",
                "all-pokemon": "All Pokémon on the field",
                "random-opponent": "One opponent at random",
                "all-other-pokemon": "All other Pokémon on the field"
            }
            target = target_names.get(move_data["target"], move_data["target"].replace("-", " "))
            embed.add_field(name="**Target**", value=target, inline=False)
        
        # Stats section using individual fields for perfect alignment
        power = move_data["power"] if move_data["power"] else "—"
        accuracy = move_data["accuracy"] if move_data["accuracy"] else "—"
        pp = move_data["pp"] if move_data["pp"] else "—"
        
        embed.add_field(name="**Power**", value=str(power), inline=True)
        embed.add_field(name="**Accuracy**", value=str(accuracy), inline=True)
        embed.add_field(name="**PP**", value=str(pp), inline=True)
        
        # Second row
        priority = move_data["priority"] if move_data["priority"] else 0
        move_type = move_data["type"].title() if move_data["type"] else "Normal"
        category = move_data["damage_class"].title() if move_data["damage_class"] else "Status"
        
        embed.add_field(name="**Priority**", value=str(priority), inline=True)
        embed.add_field(name="**Type**", value=f"🟢 {move_type}", inline=True)
        embed.add_field(name="**Class**", value=f"🟠 {category}", inline=True)
        
        await ctx.reply(embed=embed)

    @commands.command(name="release")
    async def prefix_release(self, ctx, number=None):
        """Release a Pokemon from your collection"""
        if not number:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Please specify a Pokemon number!\nUsage: `{prefix}release <number>`")
        
        if not str(number).isdigit():
            return await ctx.reply("❌ Please provide a valid Pokemon number!")
        
        number = int(number)
        
        # Find the Pokemon
        pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        
        if not pokemon:
            return await ctx.reply(f"❌ You don't have a Pokemon with number {number}!")
        
        # Check if Pokemon is selected
        if pokemon.get('selected', False):
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You cannot release your selected Pokemon! Use `{prefix}select <number>` to select a different Pokemon first.")
        
        # Check if Pokemon is favorited
        if pokemon.get('favorite', False):
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You cannot release a favorited Pokemon! Use `{prefix}favorite {number}` to remove it from favorites first.")
        
        # Check if user has more than one Pokemon (can't release their only Pokemon)
        user_pokemon_count = await self.collection.count_documents({"user_id": ctx.author.id})
        if user_pokemon_count <= 1:
            return await ctx.reply("❌ You cannot release your only Pokémon! You must always have at least one Pokémon in your collection.")
        
        # Create confirmation embed
        display_name = pokemon.get('nickname') or pokemon['pokemon_name']
        shiny_text = "✨ **SHINY** ✨" if pokemon.get('shiny', False) else ""
        
        embed = discord.Embed(
            title="🚨 Release Pokemon Confirmation",
            description=f"Are you sure you want to release this Pokemon?\n\n{shiny_text}\n**{display_name}** (#{number})\nLevel {pokemon['level']} • {pokemon['nature']} Nature",
            color=0xff6b6b
        )
        
        # Calculate IVs for display
        hp_iv = pokemon.get('hpiv', pokemon.get('hp_iv', 0))
        atk_iv = pokemon.get('atkiv', pokemon.get('atk_iv', 0))
        def_iv = pokemon.get('defiv', pokemon.get('def_iv', 0))
        spatk_iv = pokemon.get('spatkiv', pokemon.get('sp_atk_iv', 0))
        spdef_iv = pokemon.get('spdefiv', pokemon.get('sp_def_iv', 0))
        spd_iv = pokemon.get('spdiv', pokemon.get('spd_iv', 0))
        
        total_iv = hp_iv + atk_iv + def_iv + spatk_iv + spdef_iv + spd_iv
        iv_percentage = round((total_iv / 186) * 100, 1)
        
        embed.add_field(
            name="Pokemon Stats",
            value=f"**IVs**: {total_iv}/186 ({iv_percentage}%)\n**Friendship**: {pokemon.get('friendship', 0)}/255",
            inline=True
        )
        
        embed.add_field(
            name="Reward",
            value="💰 **5 coins**",
            inline=True
        )
        
        embed.set_footer(text="⚠️ This action cannot be undone!")
        
        # Create confirmation view
        class ReleaseConfirmView(View):
            def __init__(self, pokemon_data, cog_instance):
                super().__init__(timeout=30.0)
                self.pokemon_data = pokemon_data
                self.cog = cog_instance
                self.author = ctx.author
            
            @discord.ui.button(label="✅ Confirm Release", style=discord.ButtonStyle.danger)
            async def confirm_release(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can confirm this action!", ephemeral=True)
                
                # Delete the Pokemon
                await self.cog.collection.delete_one({"_id": self.pokemon_data["_id"]})
                
                # Update quest progress for release
                try:
                    quest_cog = self.cog.bot.get_cog("QuestSystem")
                    if quest_cog:
                        await quest_cog.on_pokemon_release(self.author.id)
                except Exception as e:
                    print(f"Error updating quest progress: {e}")
                
                # Give coins
                await self.cog.update_user_balance(self.author.id, coins_change=5)
                
                # Create success embed
                success_embed = discord.Embed(
                    title="✅ Pokemon Released",
                    description=f"**{display_name}** has been released successfully!\n💰 You earned **5 coins**!",
                    color=0x00ff00
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_release(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can cancel this action!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Release Cancelled",
                    description=f"**{display_name}** was not released.",
                    color=0x808080
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
            
            async def on_timeout(self):
                timeout_embed = discord.Embed(
                    title="⏰ Release Timed Out",
                    description=f"Release confirmation for **{display_name}** has expired.",
                    color=0x808080
                )
                try:
                    await self.message.edit(embed=timeout_embed, view=None)
                except:
                    pass
        
        view = ReleaseConfirmView(pokemon, self)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    @commands.command(name="releaseall", aliases=["ra"])
    async def prefix_releaseall(self, ctx):
        """Release all non-selected, non-favorited Pokemon"""
        # Get all user's Pokemon
        all_pokemon = await self.collection.find({"user_id": ctx.author.id}).to_list(length=None)
        
        if not all_pokemon:
            return await ctx.reply("❌ You don't have any Pokémon!")
        
        # Find releasable Pokemon (not selected, not favorited)
        releasable_pokemon = []
        for pokemon in all_pokemon:
            if not pokemon.get('selected', False) and not pokemon.get('favorite', False):
                releasable_pokemon.append(pokemon)
        
        # Check if user would have at least 1 Pokemon left
        if len(all_pokemon) - len(releasable_pokemon) < 1:
            return await ctx.reply("❌ You cannot release all your Pokémon! You must always have at least one Pokémon in your collection.")
        
        if not releasable_pokemon:
            return await ctx.reply("❌ No Pokémon available to release! (Selected and favorited Pokémon cannot be released)")
        
        # Calculate rewards and warnings
        total_coins = len(releasable_pokemon) * 5  # 5 coins per Pokemon
        shiny_count = sum(1 for p in releasable_pokemon if p.get('shiny', False))
        
        # Count high IV Pokemon (80%+)
        high_iv_pokemon = []
        for pokemon in releasable_pokemon:
            hp_iv = pokemon.get('hp_iv', 0)
            atk_iv = pokemon.get('atk_iv', 0)
            def_iv = pokemon.get('def_iv', 0)
            spatk_iv = pokemon.get('sp_atk_iv', 0)
            spdef_iv = pokemon.get('sp_def_iv', 0)
            spd_iv = pokemon.get('spd_iv', 0)
            
            total_iv = hp_iv + atk_iv + def_iv + spatk_iv + spdef_iv + spd_iv
            iv_percentage = round((total_iv / 186) * 100, 1)
            
            if iv_percentage >= 80.0:
                high_iv_pokemon.append(pokemon)
        
        # Create confirmation embed
        embed = discord.Embed(
            title="🚨 Release All Pokémon Confirmation",
            description=f"Are you sure you want to release **{len(releasable_pokemon)}** Pokémon?",
            color=0xff6b6b
        )
        
        # Summary field
        summary_text = f"**Pokémon to release**: {len(releasable_pokemon)}\n"
        summary_text += f"**Pokémon keeping**: {len(all_pokemon) - len(releasable_pokemon)}\n"
        summary_text += f"**Total reward**: 💰 **{total_coins} coins**"
        
        embed.add_field(
            name="📊 Summary",
            value=summary_text,
            inline=False
        )
        
        # Warnings
        warnings = []
        if shiny_count > 0:
            warnings.append(f"✨ **{shiny_count}** shiny Pokémon will be released!")
        
        if len(high_iv_pokemon) > 0:
            warnings.append(f"🏆 **{len(high_iv_pokemon)}** high IV Pokémon (80%+) will be released!")
        
        if warnings:
            embed.add_field(
                name="⚠️ Warnings",
                value="\n".join(warnings),
                inline=False
            )
        
        # Protection info
        protection_text = "✅ **Selected** and **favorite** Pokémon are protected\n"
        protection_text += "✅ You will keep at least 1 Pokémon"
        
        embed.add_field(
            name="🛡️ Protected",
            value=protection_text,
            inline=False
        )
        
        embed.set_footer(text="⚠️ This action cannot be undone!")
        
        # Create confirmation view
        class ReleaseAllConfirmView(View):
            def __init__(self, releasable_pokemon_list, total_coin_reward, cog_instance):
                super().__init__(timeout=60.0)
                self.releasable_pokemon = releasable_pokemon_list
                self.total_coins = total_coin_reward
                self.cog = cog_instance
                self.author = ctx.author
            
            @discord.ui.button(label="✅ Confirm Release All", style=discord.ButtonStyle.danger)
            async def confirm_release_all(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can confirm this action!", ephemeral=True)
                
                # Delete all releasable Pokemon
                pokemon_ids = [pokemon["_id"] for pokemon in self.releasable_pokemon]
                result = await self.cog.collection.delete_many({"_id": {"$in": pokemon_ids}})
                
                # Update quest progress for each released Pokemon
                try:
                    quest_cog = self.cog.bot.get_cog("QuestSystem")
                    if quest_cog:
                        for _ in range(result.deleted_count):
                            await quest_cog.on_pokemon_release(self.author.id)
                except Exception as e:
                    print(f"Error updating quest progress: {e}")
                
                # Give coins
                await self.cog.update_user_balance(self.author.id, coins_change=self.total_coins)
                
                # Create success embed
                success_embed = discord.Embed(
                    title="✅ Pokémon Released",
                    description=f"Successfully released **{result.deleted_count}** Pokémon!\n💰 You earned **{self.total_coins} coins**!",
                    color=0x00ff00
                )
                
                success_embed.add_field(
                    name="📊 Released",
                    value=f"**Count**: {result.deleted_count} Pokémon\n**Coins earned**: {self.total_coins}",
                    inline=True
                )
                
                # Check what's left
                remaining_count = len(all_pokemon) - result.deleted_count
                success_embed.add_field(
                    name="📋 Remaining",
                    value=f"**Count**: {remaining_count} Pokémon\n(Selected & favorites kept safe)",
                    inline=True
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_release_all(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("❌ Only the command user can cancel this action!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Release Cancelled",
                    description="No Pokémon were released.",
                    color=0x808080
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
            
            async def on_timeout(self):
                timeout_embed = discord.Embed(
                    title="⏰ Release Timed Out",
                    description="Release confirmation has expired. No Pokémon were released.",
                    color=0x808080
                )
                try:
                    await self.message.edit(embed=timeout_embed, view=None)
                except:
                    pass
        
        view = ReleaseAllConfirmView(releasable_pokemon, total_coins, self)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    @commands.command(name="ownerspawn", aliases=["ospawn"])
    async def prefix_ownerspawn(self, ctx, pokemon_name=None, *, args=None):
        """Owner-only command to spawn Pokemon with custom stats"""
        # Check if user is bot owner
        if ctx.author.id != 1202397329370386523:  # Your owner ID
            return await ctx.reply("❌ This command is only available to the bot owner!")
        
        if not pokemon_name:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Please specify a Pokemon name!\nUsage: `{prefix}ownerspawn <pokemon> [--shiny] [--iv <stat>=<value>]`\nExample: `{prefix}ownerspawn pikachu --shiny --iv hp=31 --iv attack=31`")
        
        # Find Pokemon in data (check both regular and custom Pokemon)
        pokemon_data = None
        pokemon_id = None
        is_custom = False
        
        # First check regular Pokemon
        for poke_id, data in POKEMON_DATA.items():
            if data["name"].lower() == pokemon_name.lower():
                pokemon_data = data
                pokemon_id = poke_id
                break
        
        # If not found, check custom Pokemon
        if not pokemon_data:
            for poke_id, data in CUSTOM_POKEMON.items():
                if data["name"].lower() == pokemon_name.lower():
                    pokemon_data = data
                    pokemon_id = poke_id
                    is_custom = True
                    break
        
        if not pokemon_data:
            return await ctx.reply(f"❌ Pokemon '{pokemon_name}' not found! (Searched both regular and custom Pokemon)")
        
        # Parse arguments
        is_shiny = False
        custom_ivs = {}
        
        if args:
            parts = args.split()
            i = 0
            while i < len(parts):
                if parts[i] == "--shiny":
                    is_shiny = True
                    i += 1
                elif parts[i] == "--iv" and i + 1 < len(parts):
                    iv_part = parts[i + 1]
                    if "=" in iv_part:
                        stat, value = iv_part.split("=", 1)
                        try:
                            iv_value = int(value)
                            if 0 <= iv_value <= 31:
                                custom_ivs[stat.lower()] = iv_value
                            else:
                                return await ctx.reply(f"❌ IV values must be between 0-31! Got {value}")
                        except ValueError:
                            return await ctx.reply(f"❌ Invalid IV value: {value}")
                    i += 2
                else:
                    i += 1
        
        # Generate IVs (use custom if provided, random otherwise)
        # Map new names to old field names for consistency with database
        stat_mapping = {
            "hp": "hp_iv",
            "attack": "atk_iv", 
            "defense": "def_iv",
            "spatk": "sp_atk_iv",
            "spdef": "sp_def_iv",
            "speed": "spd_iv"
        }
        
        ivs = {}
        for new_name, old_field in stat_mapping.items():
            if new_name in custom_ivs:
                ivs[old_field] = custom_ivs[new_name]
            else:
                ivs[old_field] = random.randint(0, 31)
        
        # Get next pokemon number
        existing_pokemon = await self.collection.find({"user_id": ctx.author.id}).to_list(length=None)
        next_number = max([p.get("pokemon_number", 0) for p in existing_pokemon], default=0) + 1
        
        # Create Pokemon
        level = random.randint(1, 50)  # Random level between 1-50
        nature = random.choice(list(NATURES.keys()))
        
        new_pokemon = {
            "user_id": ctx.author.id,
            "pokemon_name": pokemon_data["name"],
            "pokemon_number": next_number,
            "level": level,
            "xp": self.calculate_xp_for_level(level),
            "nature": nature,
            "shiny": is_shiny,
            "friendship": 0,
            "selected": len(existing_pokemon) == 0,  # Auto-select if first Pokemon
            "timestamp": datetime.utcnow(),
            "caught_at": datetime.utcnow(),
            "favorite": False,  # Standard field for compatibility
            # IVs using old field names
            "hp_iv": ivs["hp_iv"],
            "atk_iv": ivs["atk_iv"], 
            "def_iv": ivs["def_iv"],
            "sp_atk_iv": ivs["sp_atk_iv"],
            "sp_def_iv": ivs["sp_def_iv"],
            "spd_iv": ivs["spd_iv"],
            # EVs (start at 0)
            "hp_ev": 0,
            "atk_ev": 0,
            "def_ev": 0,
            "sp_atk_ev": 0,
            "sp_def_ev": 0,
            "spd_ev": 0,
            # Moves (no moves initially)
            "move1": "None",
            "move2": "None", 
            "move3": "None",
            "move4": "None"
        }
        
        # Add pokemon_id for custom Pokemon (required for battle system)
        if is_custom:
            new_pokemon["pokemon_id"] = int(pokemon_id)
        
        # Insert Pokemon
        await self.collection.insert_one(new_pokemon)
        
        # Create spawn embed
        title = "🌟 Owner Spawn Successful!"
        if is_custom:
            title = "🌟 Custom Pokemon Spawned!"
        
        embed = discord.Embed(
            title=title,
            color=0xFFD700 if is_shiny else (0x8B0000 if is_custom else 0x3498db)
        )
        
        # Calculate total IV
        total_iv = sum(ivs.values())
        iv_percentage = round((total_iv / 186) * 100, 1)
        
        # Pokemon info
        shiny_text = "✨ **SHINY** ✨" if is_shiny else ""
        custom_text = "🌑 **CUSTOM POKEMON** 🌑" if is_custom else ""
        
        pokemon_info = f"{shiny_text}\n{custom_text}\n**{pokemon_data['name']}** #{next_number}\nLevel {level} • {nature} Nature"
        if is_custom:
            pokemon_info += f"\nPokemon ID: {pokemon_id}"
        
        embed.add_field(
            name="Pokemon Spawned",
            value=pokemon_info,
            inline=False
        )
        
        # IV breakdown
        iv_display = {
            "HP": ivs["hp_iv"],
            "ATTACK": ivs["atk_iv"],
            "DEFENSE": ivs["def_iv"],
            "SP.ATK": ivs["sp_atk_iv"],
            "SP.DEF": ivs["sp_def_iv"],
            "SPEED": ivs["spd_iv"]
        }
        
        iv_text = ""
        for stat_name, iv_value in iv_display.items():
            iv_text += f"**{stat_name}**: {iv_value}/31\n"
        iv_text += f"\n**Total**: {total_iv}/186 ({iv_percentage}%)"
        
        embed.add_field(name="IVs", value=iv_text, inline=True)
        
        # Custom settings used
        custom_text = []
        if is_shiny:
            custom_text.append("✨ Forced Shiny")
        if custom_ivs:
            custom_text.append(f"🎯 Custom IVs: {', '.join(f'{k}={v}' for k, v in custom_ivs.items())}")
        
        if custom_text:
            embed.add_field(name="Custom Settings", value="\n".join(custom_text), inline=True)
        
        prefix = ctx.bot.get_primary_prefix()
        embed.set_footer(text=f"Use {prefix}select {next_number} to select this Pokemon")
        
        await ctx.reply(embed=embed)

    @commands.command(name="pve", aliases=["battle"])
    async def prefix_pve(self, ctx):
        """Challenge PvE bosses!"""
        user_id = ctx.author.id
        
        # Check if user is already in a battle
        battle_cog = self.bot.get_cog("Battle")
        if battle_cog and user_id in battle_cog.active_battles:
            await ctx.send("❌ You're already in a battle!")
            return

        # Get user's Pokemon
        user_pokemon = await self.collection.find({"user_id": user_id}).to_list(length=None)
        
        if not user_pokemon:
            prefix = ctx.bot.get_primary_prefix()
            await ctx.send(f"❌ You don't have any Pokémon! Use `{prefix}start` to begin your journey.")
            return
        
        if len(user_pokemon) < 3:
            await ctx.send("❌ You need at least 3 Pokémon to battle! Catch more Pokémon first.")
            return

        # Check if user has a party
        user_profile = await self.user_profiles.find_one({"user_id": user_id})
        if not user_profile:
            await self.ensure_user_profile(user_id)
            user_profile = await self.user_profiles.find_one({"user_id": user_id})
        
        party_pokemon_ids = user_profile.get("party", [])
        
        # Get party Pokemon details if they exist
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
            prefix = ctx.bot.get_primary_prefix()
            embed = discord.Embed(
                title="❌ Party Not Ready",
                description=f"You need at least 3 Pokémon in your party to battle!",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🎯 Current Party",
                value=f"{len(party_pokemon)}/3 Pokémon" if party_pokemon else "Empty",
                inline=False
            )
            embed.add_field(
                name="📋 How to Set Up Your Party",
                value=f"`{prefix}party` - View your current party\n"
                      f"`{prefix}party add <number>` - Add Pokémon to party\n"
                      f"`{prefix}party remove <number>` - Remove Pokémon from party",
                inline=False
            )
            return await ctx.send(embed=embed)

        # Use first 3 Pokemon from party for battle
        battle_team = party_pokemon[:3]
        
        embed = discord.Embed(
            title="⚔️ PvE Battle Setup",
            description="Using your party for battle!",
            color=0x3498DB
        )
        
        team_text = ""
        for i, pokemon in enumerate(battle_team):
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            pokemon_number = pokemon.get('pokemon_number', i + 1)
            shiny_text = "✨ " if pokemon.get('shiny', False) else ""
            team_text += f"{i+1}. {shiny_text}**{display_name}** (#{pokemon_number}) - Level {pokemon.get('level', 1)}\n"
        
        embed.add_field(name="🎯 Your Battle Team", value=team_text, inline=False)
        embed.add_field(
            name="📋 Battle Rules",
            value="• 3v3 battles\n• Level 100 stats for all Pokémon\n• Uses your Pokémon's learned moves\n• Win coins, no XP",
            inline=False
        )
        
        # Create simple view with just boss selection
        view = self.PartyBattleView(self, battle_cog, user_id, battle_team)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="party")
    async def prefix_party(self, ctx, action=None, number=None):
        """Manage your battle party"""
        user_id = ctx.author.id
        prefix = ctx.bot.get_primary_prefix()
        
        if action is None:
            # Show current party
            user_profile = await self.user_profiles.find_one({"user_id": user_id})
            if not user_profile:
                await self.ensure_user_profile(user_id)
                user_profile = await self.user_profiles.find_one({"user_id": user_id})
            
            party_pokemon_ids = user_profile.get("party", [])
            
            if not party_pokemon_ids:
                embed = discord.Embed(
                    title="🎯 Your Battle Party",
                    description=f"Your party is empty! Add Pokémon with `{prefix}party add <number>`",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="📋 Party Commands",
                    value=f"`{prefix}party` - View your party\n"
                          f"`{prefix}party add <number>` - Add Pokémon to party\n"
                          f"`{prefix}party remove <number>` - Remove Pokémon from party\n"
                          f"`{prefix}party clear` - Clear entire party",
                    inline=False
                )
                return await ctx.reply(embed=embed)
            
            # Get party Pokemon details
            party_pokemon = []
            for pokemon_id in party_pokemon_ids:
                try:
                    from bson import ObjectId
                    pokemon = await self.collection.find_one({"_id": ObjectId(pokemon_id), "user_id": user_id})
                    if pokemon:
                        party_pokemon.append(pokemon)
                except:
                    continue
            
            embed = discord.Embed(
                title="🎯 Your Battle Party",
                description=f"Party size: {len(party_pokemon)}/6 Pokémon",
                color=discord.Color.green() if len(party_pokemon) >= 3 else discord.Color.orange()
            )
            
            if party_pokemon:
                party_text = ""
                for i, pokemon in enumerate(party_pokemon):
                    display_name = pokemon.get('nickname') or pokemon['pokemon_name']
                    pokemon_number = pokemon.get('pokemon_number', i + 1)
                    shiny_text = "✨ " if pokemon.get('shiny', False) else ""
                    level = pokemon.get('level', 1)
                    party_text += f"{i+1}. {shiny_text}**{display_name}** (#{pokemon_number}) - Level {level}\n"
                
                embed.add_field(name="🎮 Party Members", value=party_text, inline=False)
            
            if len(party_pokemon) < 3:
                embed.add_field(
                    name="⚠️ Notice",
                    value="You need at least 3 Pokémon in your party for PvE battles!",
                    inline=False
                )
            
            embed.add_field(
                name="📋 Party Commands",
                value=f"`{prefix}party add <number>` - Add Pokémon to party\n"
                      f"`{prefix}party remove <number>` - Remove Pokémon from party\n"
                      f"`{prefix}party clear` - Clear entire party",
                inline=False
            )
            
            await ctx.reply(embed=embed)
        
        elif action.lower() == "add":
            if number is None:
                return await ctx.reply(f"❌ Please specify a Pokémon number! Usage: `{prefix}party add <number>`")
            
                # Handle 'latest' keyword
            if str(number).lower() == "latest":
                    pokemon = await self.collection.find_one(
                        {"user_id": user_id}, 
                        sort=[("pokemon_number", -1)]
                    )
            elif str(number).isdigit():
                pokemon = await self.collection.find_one({"user_id": user_id, "pokemon_number": int(number)})
                else:
                return await ctx.reply("❌ Please provide a valid Pokémon number or 'latest'!")
                
                if not pokemon:
                return await ctx.reply("❌ You don't have a Pokémon with that number!")
            
            # Get current party
            user_profile = await self.user_profiles.find_one({"user_id": user_id})
            if not user_profile:
                await self.ensure_user_profile(user_id)
                user_profile = await self.user_profiles.find_one({"user_id": user_id})
            
            party = user_profile.get("party", [])
                pokemon_id_str = str(pokemon["_id"])
                
                # Check if already in party
                if pokemon_id_str in party:
                    display_name = pokemon.get('nickname') or pokemon['pokemon_name']
                return await ctx.reply(f"❌ **{display_name}** is already in your party!")
            
            # Check party size limit
            if len(party) >= 6:
                return await ctx.reply("❌ Your party is full! (Maximum 6 Pokémon)")
                
                # Add to party
                party.append(pokemon_id_str)
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {"$set": {"party": party}}
            )
            
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            await ctx.reply(f"✅ **{display_name}** (#{pokemon.get('pokemon_number', 'N/A')}) has been added to your party!")
        
        elif action.lower() == "remove":
            if number is None:
                return await ctx.reply(f"❌ Please specify a Pokémon number! Usage: `{prefix}party remove <number>`")
            
            # Handle 'latest' keyword
            if str(number).lower() == "latest":
                pokemon = await self.collection.find_one(
                    {"user_id": user_id}, 
                    sort=[("pokemon_number", -1)]
                )
            elif str(number).isdigit():
                pokemon = await self.collection.find_one({"user_id": user_id, "pokemon_number": int(number)})
            else:
                return await ctx.reply("❌ Please provide a valid Pokémon number or 'latest'!")
            
            if not pokemon:
                return await ctx.reply("❌ You don't have a Pokémon with that number!")
            
            # Get current party
            user_profile = await self.user_profiles.find_one({"user_id": user_id})
            if not user_profile:
                await self.ensure_user_profile(user_id)
                user_profile = await self.user_profiles.find_one({"user_id": user_id})
            
            party = user_profile.get("party", [])
            pokemon_id_str = str(pokemon["_id"])
            
            # Check if in party
            if pokemon_id_str not in party:
                display_name = pokemon.get('nickname') or pokemon['pokemon_name']
                return await ctx.reply(f"❌ **{display_name}** is not in your party!")
            
            # Remove from party
            party.remove(pokemon_id_str)
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {"$set": {"party": party}}
            )
            
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            await ctx.reply(f"✅ **{display_name}** (#{pokemon.get('pokemon_number', 'N/A')}) has been removed from your party!")
        
        elif action.lower() == "clear":
            # Clear entire party
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {"$set": {"party": []}}
            )
            await ctx.reply("✅ Your party has been cleared!")
        
        else:
            await ctx.reply(f"❌ Invalid action! Use `{prefix}party`, `{prefix}party add <number>`, `{prefix}party remove <number>`, or `{prefix}party clear`")

    @commands.command(name="finish")
    async def prefix_finish(self, ctx):
        """Manually finish/clear a stuck battle state"""
        user_id = ctx.author.id
        
        # Get battle and event cogs
        battle_cog = self.bot.get_cog("Battle")
        event_cog = self.bot.get_cog("EventSystem")
        
        battles_cleared = []
        
        # Check PVE battles
        if battle_cog and user_id in battle_cog.active_battles:
            del battle_cog.active_battles[user_id]
            battles_cleared.append("PVE")
        
        # Check event/gauntlet battles  
        if event_cog and user_id in event_cog.active_battles:
            del event_cog.active_battles[user_id]
            battles_cleared.append("Gauntlet")
        
        # Check if any battles were found
        if not battles_cleared:
            return await ctx.reply("❌ You're not currently in any battle!")
        
        # Create success message
        battle_types = " & ".join(battles_cleared)
        embed = discord.Embed(
            title="✅ Battle Cleared",
            description=f"Your **{battle_types}** battle state has been manually cleared! You can now start new battles.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="ℹ️ About This Command",
            value="This is a temporary fix for stuck battle states. If you need to use this command frequently, please report the issue!",
            inline=False
        )
        
        await ctx.reply(embed=embed)

class PartyBattleView(discord.ui.View):
    def __init__(self, prefix_cog, battle_cog, user_id: int, battle_team: list):
        super().__init__(timeout=300)
        self.prefix_cog = prefix_cog
        self.battle_cog = battle_cog
        self.user_id = user_id
        self.battle_team = battle_team
        
        # Add boss selection button
        boss_button = discord.ui.Button(label="⚔️ Choose Boss & Start Battle!", style=discord.ButtonStyle.success)
        boss_button.callback = self.start_boss_selection
        self.add_item(boss_button)
        
        # Add party management button
        party_button = discord.ui.Button(label="🎯 Manage Party", style=discord.ButtonStyle.secondary)
        party_button.callback = self.manage_party
        self.add_item(party_button)
    
    async def start_boss_selection(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your battle setup!", ephemeral=True)
            return
        
        # Create boss selection embed
        embed = discord.Embed(
            title="🏆 Choose Your Opponent",
            description="Select a boss to battle against!",
            color=0xFF6B6B
        )
        
        # Add team summary
        team_text = ""
        for i, pokemon in enumerate(self.battle_team):
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            pokemon_number = pokemon.get('pokemon_number', i + 1)
            shiny_text = "✨ " if pokemon.get('shiny', False) else ""
            team_text += f"{i+1}. {shiny_text}**{display_name}** (#{pokemon_number})\n"
        
        embed.add_field(name="🎯 Your Team", value=team_text, inline=True)
        
        # Create view for boss selection (reuse the existing boss selection logic)
            view = self.prefix_cog.PokemonSelectionView(self.prefix_cog, self.battle_cog, self.user_id, [])
        # Override the selected pokemon with our party team
        view.selected_pokemon = self.battle_team
        
        # Skip to boss confirmation directly
        await view.confirm_selection(interaction)
    
    async def manage_party(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your battle setup!", ephemeral=True)
            return
        
        prefix = self.prefix_cog.bot.get_primary_prefix()
        embed = discord.Embed(
            title="🎯 Party Management",
            description="Use these commands to manage your party:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Party Commands",
            value=f"`{prefix}party` - View your current party\n"
                  f"`{prefix}party add <number>` - Add Pokémon to party\n"
                  f"`{prefix}party remove <number>` - Remove Pokémon from party\n"
                  f"`{prefix}party clear` - Clear entire party",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PokemonSelectionView(discord.ui.View):
    def __init__(self, prefix_cog, battle_cog, user_id: int, user_pokemon: list):
        super().__init__(timeout=300)
        self.prefix_cog = prefix_cog
        self.battle_cog = battle_cog
        self.user_id = user_id
        self.user_pokemon = user_pokemon
        self.selected_pokemon = []
        self.current_page = 0
        self.per_page = 10
        
        self.update_pokemon_select()

    def update_pokemon_select(self):
        self.clear_items()
        
        # Calculate pagination
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.user_pokemon))
        current_pokemon = self.user_pokemon[start_idx:end_idx]
        
        # Create options for current page
        options = []
        for i, pokemon in enumerate(current_pokemon):
            actual_idx = start_idx + i
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            pokemon_number = pokemon.get('pokemon_number', actual_idx + 1)
            
            # Check if already selected
            is_selected = any(p.get('_id') == pokemon.get('_id') for p in self.selected_pokemon)
            status = " ✅" if is_selected else ""
            
            description = f"Level {pokemon.get('level', 1)} • #{pokemon_number}{status}"
            
            options.append(discord.SelectOption(
                label=f"{display_name}",
                description=description,
                value=str(actual_idx),
                emoji="✨" if pokemon.get('shiny', False) else "🔘"
            ))
        
        if options:
            select = discord.ui.Select(
                placeholder=f"Choose Pokémon ({len(self.selected_pokemon)}/3 selected)",
                options=options,
                disabled=len(self.selected_pokemon) >= 3
            )
            select.callback = self.pokemon_callback
            self.add_item(select)
        
        # Add pagination buttons if needed
        if len(self.user_pokemon) > self.per_page:
            if self.current_page > 0:
                prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
                prev_button.callback = self.previous_page
                self.add_item(prev_button)
            
            if end_idx < len(self.user_pokemon):
                next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
                next_button.callback = self.next_page
                self.add_item(next_button)
        
        # Add action buttons
        if len(self.selected_pokemon) > 0:
            clear_button = discord.ui.Button(label="🗑️ Clear Selection", style=discord.ButtonStyle.secondary)
            clear_button.callback = self.clear_selection
            self.add_item(clear_button)
        
        if len(self.selected_pokemon) == 3:
            confirm_button = discord.ui.Button(label="⚔️ Start Battle!", style=discord.ButtonStyle.success)
            confirm_button.callback = self.confirm_selection
            self.add_item(confirm_button)

    async def pokemon_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return

        # Get the select component that triggered this callback
        select = [item for item in self.children if isinstance(item, discord.ui.Select)][0]
        pokemon_idx = int(select.values[0])
        selected_pokemon = self.user_pokemon[pokemon_idx]
        
        # Check if already selected
        already_selected = any(p.get('_id') == selected_pokemon.get('_id') for p in self.selected_pokemon)
        
        if already_selected:
            # Remove from selection
            self.selected_pokemon = [p for p in self.selected_pokemon if p.get('_id') != selected_pokemon.get('_id')]
        elif len(self.selected_pokemon) < 3:
            # Add to selection
            self.selected_pokemon.append(selected_pokemon)
        
        self.update_pokemon_select()
        
        # Create updated embed
        embed = discord.Embed(
            title="⚔️ PvE Battle Setup",
            description="Choose 3 Pokémon for your battle team!\nSelect them in the order you want them to battle.",
            color=0x3498DB
        )
        
        if self.selected_pokemon:
            team_text = ""
            for i, pokemon in enumerate(self.selected_pokemon):
                display_name = pokemon.get('nickname') or pokemon['pokemon_name']
                pokemon_number = pokemon.get('pokemon_number', i + 1)
                shiny_text = "✨ " if pokemon.get('shiny', False) else ""
                team_text += f"{i+1}. {shiny_text}**{display_name}** (#{pokemon_number}) - Level {pokemon.get('level', 1)}\n"
            
            embed.add_field(name="🎯 Selected Team", value=team_text, inline=False)
        
        embed.add_field(
            name="📋 Battle Rules",
            value="• 3v3 battles\n• Level 100 stats for all Pokémon\n• Uses your Pokémon's learned moves\n• Win coins, no XP",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.current_page -= 1
        self.update_pokemon_select()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.current_page += 1
        self.update_pokemon_select()
        await interaction.response.edit_message(view=self)

    async def clear_selection(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.selected_pokemon = []
        self.update_pokemon_select()
        
        embed = discord.Embed(
            title="⚔️ PvE Battle Setup",
            description="Choose 3 Pokémon for your battle team!\nSelect them in the order you want them to battle.",
            color=0x3498DB
        )
        embed.add_field(
            name="📋 Battle Rules",
            value="• 3v3 battles\n• Level 100 stats for all Pokémon\n• Uses your Pokémon's learned moves\n• Win coins, no XP",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_selection(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        
        if len(self.selected_pokemon) != 3:
            await interaction.response.send_message("❌ Please select exactly 3 Pokémon!", ephemeral=True)
            return
        
        # Import here to avoid circular imports
        from .battle import BossSelectionView
        
        # Create boss selection embed
        embed = discord.Embed(
            title="⚔️ Choose Your Opponent",
            description="Select which boss you want to battle!",
            color=0xFF6B6B
        )
        
        # Add PVE image if it exists
        import os
        pve_image_exists = os.path.exists("pve.png")
        if pve_image_exists:
            embed.set_image(url="attachment://pve.png")
        
        # Show selected team
        team_text = ""
        for i, pokemon in enumerate(self.selected_pokemon):
            display_name = pokemon.get('nickname') or pokemon['pokemon_name']
            pokemon_number = pokemon.get('pokemon_number', i + 1)
            shiny_text = "✨ " if pokemon.get('shiny', False) else ""
            team_text += f"{i+1}. {shiny_text}**{display_name}** (#{pokemon_number})\n"
        
        embed.add_field(name="🎯 Your Battle Team", value=team_text, inline=False)
        
        # Boss selection view with selected team
        view = BossSelectionView(self.battle_cog, self.user_id, self.selected_pokemon)
        
        # Send with file attachment if image exists
        if pve_image_exists:
            file = discord.File("pve.png", filename="pve.png")
            await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
        else:
            await interaction.response.edit_message(embed=embed, view=view)

async def setup(bot):
    pokemon_db = bot.pokemon_collection
    user_profiles_db = bot.db["user_profiles"]
    await bot.add_cog(PrefixCommands(bot, pokemon_db, user_profiles_db)) 