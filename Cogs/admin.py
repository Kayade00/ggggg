import discord
from discord.ext import commands
from discord import app_commands

ALLOWED_USER_IDS = [165167315732791296] 

def is_owner_or_allowed():
    async def predicate(ctx):
        return ctx.author.id in ALLOWED_USER_IDS or await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)

class AdminCommands(commands.Cog):
    def __init__(self, bot, collection):
        self.bot = bot
        self.collection = collection

    @commands.command(name="sync")
    @is_owner_or_allowed()
    async def sync_commands(self, ctx):
        """Sync unique global slash commands (no duplicates)."""
        tree = self.bot.tree
        unique = {}
        for cmd in reversed(tree.get_commands()):  # reversed to keep the last one defined
            unique[cmd.name] = cmd

        # Replace the internal list with deduplicated commands
        tree._commands = list(unique.values())

        synced = await tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} unique slash commands globally.")

    @commands.command(name="check")
    @commands.is_owner()
    async def check_stats(self, ctx):
        """Show bot statistics (owner only)"""
        try:
            # Get server count
            server_count = len(self.bot.guilds)
            
            # Get total member count across all servers
            total_members = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
            
            # Get unique user count from database (users who have caught Pokemon)
            unique_users = await self.collection.distinct("user_id")
            unique_user_count = len(unique_users)
            
            # Get total Pokemon caught
            total_pokemon = await self.collection.count_documents({})
            
            embed = discord.Embed(
                title="🤖 Bot Statistics",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="🏠 Servers", value=f"{server_count:,}", inline=True)
            embed.add_field(name="👥 Total Members", value=f"{total_members:,}", inline=True)
            embed.add_field(name="🎮 Active Users", value=f"{unique_user_count:,}", inline=True)
            embed.add_field(name="⚡ Total Pokémon", value=f"{total_pokemon:,}", inline=True)
            embed.add_field(name="📊 Avg per User", value=f"{total_pokemon // max(unique_user_count, 1):,}", inline=True)
            embed.add_field(name="🔗 Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            
            embed.set_footer(text=f"Bot running as {self.bot.user.name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error retrieving stats: {e}")

    @app_commands.command(name="check", description="Show bot statistics (owner only)")
    async def slash_check_stats(self, interaction: discord.Interaction):
        """Show bot statistics (owner only)"""
        # Check if user is bot owner
        app_info = await self.bot.application_info()
        if interaction.user.id != app_info.owner.id:
            return await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
        
        try:
            # Get server count
            server_count = len(self.bot.guilds)
            
            # Get total member count across all servers
            total_members = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
            
            # Get unique user count from database (users who have caught Pokemon)
            unique_users = await self.collection.distinct("user_id")
            unique_user_count = len(unique_users)
            
            # Get total Pokemon caught
            total_pokemon = await self.collection.count_documents({})
            
            embed = discord.Embed(
                title="🤖 Bot Statistics",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="🏠 Servers", value=f"{server_count:,}", inline=True)
            embed.add_field(name="👥 Total Members", value=f"{total_members:,}", inline=True)
            embed.add_field(name="🎮 Active Users", value=f"{unique_user_count:,}", inline=True)
            embed.add_field(name="⚡ Total Pokémon", value=f"{total_pokemon:,}", inline=True)
            embed.add_field(name="📊 Avg per User", value=f"{total_pokemon // max(unique_user_count, 1):,}", inline=True)
            embed.add_field(name="🔗 Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            
            embed.set_footer(text=f"Bot running as {self.bot.user.name}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving stats: {e}", ephemeral=True)

async def setup(bot):
    collection = bot.get_cog('Start').collection  # Get collection from pokemon cog
    await bot.add_cog(AdminCommands(bot, collection)) 