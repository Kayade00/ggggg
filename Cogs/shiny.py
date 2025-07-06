import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os

# Load Pokemon data for validation
with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEMON_DATA = json.load(f)

# Custom Pokemon data is now in the main POKEMON_DATA

class ShinyHunt(commands.Cog):
    def __init__(self, bot, user_profiles):
        self.bot = bot
        self.user_profiles = user_profiles

    async def ensure_user_profile(self, user_id):
        """Ensure user has a profile in the database"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        if not profile:
            new_profile = {
                "user_id": user_id,
                "coins": 0,
                "created_at": datetime.utcnow(),
                "shiny_hunt": {
                    "target_pokemon": None,
                    "catches_since_hunt_start": 0,
                    "bonus_shiny_chance": 0.0
                }
            }
            await self.user_profiles.insert_one(new_profile)
            return new_profile
        return profile

    def find_pokemon_by_name(self, pokemon_name):
        """Find Pokemon in both regular and custom data"""
        pokemon_name_lower = pokemon_name.lower()
        
        # Check regular Pokemon first
        for pokemon_id, data in POKEMON_DATA.items():
            if isinstance(data, dict) and data.get("name", "").lower() == pokemon_name_lower:
                return data["name"], False  # (name, is_custom)
        
        # Custom Pokemon are now in the main POKEMON_DATA
        
        return None, False

    def get_pokemon_id(self, pokemon_name):
        """Get Pokemon ID for sprite lookup"""
        pokemon_name_lower = pokemon_name.lower()
        
        # Check regular Pokemon first
        for pokemon_id, data in POKEMON_DATA.items():
            if isinstance(data, dict) and data.get("name", "").lower() == pokemon_name_lower:
                return pokemon_id
        
        # Custom Pokemon are now in the main POKEMON_DATA
        
        return None

    @commands.command(name="shinyhunt", aliases=["shhunt"])
    async def set_shiny_hunt(self, ctx, *, pokemon_name=None):
        """Set a Pokemon as your shiny hunt target"""
        if not pokemon_name:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Please specify a Pokemon name!\nUsage: `{prefix}shinyhunt <pokemon>`\nExample: `{prefix}shinyhunt pikachu`")

        # Find the Pokemon
        found_name, is_custom = self.find_pokemon_by_name(pokemon_name)
        if not found_name:
            return await ctx.reply(f"❌ Pokemon **{pokemon_name}** not found! Make sure you spelled it correctly.")

        # Ensure user profile exists
        await self.ensure_user_profile(ctx.author.id)

        # Update shiny hunt target (reset progress when changing target)
        await self.user_profiles.update_one(
            {"user_id": ctx.author.id},
            {
                "$set": {
                    "shiny_hunt.target_pokemon": found_name,
                    "shiny_hunt.catches_since_hunt_start": 0,
                    "shiny_hunt.bonus_shiny_chance": 0.0
                }
            }
        )

        # Create success embed
        embed = discord.Embed(
            title="✨ Shiny Hunt Started!",
            description=f"You are now hunting for a shiny **{found_name}**!",
            color=0xFFD700
        )
        
        embed.add_field(
            name="📊 How it works",
            value="• Each time you catch **this specific Pokemon** increases your shiny chance by **0.0015%**\n"
                  "• Catching other Pokemon won't increase your hunt progress\n"
                  "• Your progress resets if you change targets",
            inline=False
        )

        if is_custom:
            embed.add_field(
                name="⭐ Special Pokemon",
                value="You're hunting a special event Pokemon!",
                inline=False
            )

        embed.set_footer(text=f"Use {ctx.bot.get_primary_prefix()}sh to check your progress!")
        await ctx.reply(embed=embed)

    @commands.command(name="sh", aliases=["shinyhuntstatus"])
    async def shiny_hunt_status(self, ctx):
        """Show current shiny hunt status"""
        profile = await self.user_profiles.find_one({"user_id": ctx.author.id})
        
        if not profile or not profile.get("shiny_hunt", {}).get("target_pokemon"):
            prefix = ctx.bot.get_primary_prefix()
            embed = discord.Embed(
                title="❌ No Active Shiny Hunt",
                description=f"You're not currently hunting for any Pokemon.\nStart hunting with `{prefix}shinyhunt <pokemon>`",
                color=0x6b7280
            )
            return await ctx.reply(embed=embed)

        hunt_data = profile["shiny_hunt"]
        target_pokemon = hunt_data["target_pokemon"]
        catches = hunt_data.get("catches_since_hunt_start", 0)
        bonus_chance = hunt_data.get("bonus_shiny_chance", 0.0)

        # Shiny charm logic
        shiny_charm = profile.get("shiny_charm", {})
        shiny_charm_bonus = 0.0
        shiny_charm_time = None
        shiny_charm_active = False
        if shiny_charm and shiny_charm.get("active") and shiny_charm.get("expires_at"):
            try:
                expires_at = shiny_charm["expires_at"]
                if isinstance(expires_at, str):
                    expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                else:
                    expires_at_dt = expires_at
                now = datetime.utcnow().replace(tzinfo=expires_at_dt.tzinfo)
                if expires_at_dt > now:
                    shiny_charm_active = True
                    shiny_charm_time = int(expires_at_dt.timestamp())
                    shiny_charm_bonus = shiny_charm.get("shiny_boost", 2.0)
            except Exception as e:
                print(f"Error parsing shiny charm expiry: {e}")

        # Calculate current total shiny chance for target
        base_chance = 1/4096  # 0.0244%
        total_chance_percent = (base_chance + (bonus_chance / 100) + (shiny_charm_bonus / 100 if shiny_charm_active else 0)) * 100
        
        embed = discord.Embed(
            title="✨ Shiny Hunt Status",
            description=f"**Target:** {target_pokemon}",
            color=0xFFD700
        )
        
        embed.add_field(
            name="📊 Progress",
            value=f"**Catches since hunt start:** {catches:,}\n"
                  f"**Bonus shiny chance:** +{bonus_chance:.3f}%\n"
                  f"**Shiny Charm bonus:** +{shiny_charm_bonus:.2f}%\n"
                  f"**Total shiny chance:** {total_chance_percent:.4f}%",
            inline=False
        )

        # Show improvement over base rate
        if bonus_chance > 0 or shiny_charm_bonus > 0:
            multiplier = total_chance_percent / (base_chance * 100)
            embed.add_field(
                name="📈 Improvement",
                value=f"Your odds are **{multiplier:.2f}x** better than the base rate!",
                inline=False
            )

        if shiny_charm_active:
            embed.add_field(
                name="✨ Shiny Charm",
                value=f"Active! Expires <t:{shiny_charm_time}:R>",
                inline=False
            )
        else:
            embed.add_field(
                name="✨ Shiny Charm",
                value="Not active. Buy one in the shop for a +2% shiny boost!",
                inline=False
            )

        embed.add_field(
            name="💡 Tip",
            value=f"Keep catching **{target_pokemon}** to increase your shiny chance!",
            inline=False
        )

        # Try to add Pokemon thumbnail
        pokemon_id = self.get_pokemon_id(target_pokemon)
        file = None
        if pokemon_id:
            try:
                sprite_path = f"full/{pokemon_id}.png"
                if os.path.exists(sprite_path):
                    file = discord.File(sprite_path, filename=f"{pokemon_id}.png")
                    embed.set_thumbnail(url=f"attachment://{pokemon_id}.png")
            except Exception as e:
                print(f"Error loading Pokemon sprite: {e}")

        if file:
            await ctx.reply(embed=embed, file=file)
        else:
            await ctx.reply(embed=embed)

    async def update_shiny_hunt_progress(self, user_id, caught_pokemon_name):
        """Update user's shiny hunt progress when they catch their target Pokemon"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        
        if not profile or not profile.get("shiny_hunt", {}).get("target_pokemon"):
            return  # No active hunt
        
        hunt_data = profile["shiny_hunt"]
        target_pokemon = hunt_data["target_pokemon"]
        
        # Only increment if caught Pokemon matches the hunt target (case insensitive)
        if caught_pokemon_name.lower() != target_pokemon.lower():
            return  # Not the target Pokemon, no progress
        
        # Increment catches and bonus chance
        new_catches = hunt_data.get("catches_since_hunt_start", 0) + 1
        new_bonus_chance = new_catches * 0.004  # 0.004% per target catch
        
        await self.user_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "shiny_hunt.catches_since_hunt_start": new_catches,
                    "shiny_hunt.bonus_shiny_chance": new_bonus_chance
                }
            }
        )

    async def get_shiny_hunt_bonus(self, user_id, pokemon_name):
        """Get the bonus shiny chance for a specific Pokemon if it matches the hunt target"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        
        if not profile or not profile.get("shiny_hunt", {}).get("target_pokemon"):
            return 0.0
        
        hunt_data = profile["shiny_hunt"]
        target_pokemon = hunt_data["target_pokemon"]
        
        # Check if this Pokemon matches the hunt target (case insensitive)
        if pokemon_name.lower() == target_pokemon.lower():
            return hunt_data.get("bonus_shiny_chance", 0.0)
        
        return 0.0

async def setup(bot):
    user_profiles_db = bot.db["user_profiles"]
    await bot.add_cog(ShinyHunt(bot, user_profiles_db)) 