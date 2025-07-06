import discord
from discord.ext import commands
import motor.motor_asyncio
import json
import os
import asyncio
from aiohttp import web

# Load configuration
def load_config():
    """Load bot configuration from config.json"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found! Please create a config file.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing config.json: {e}")
        exit(1)

# Load config
config = load_config()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Custom prefix function to handle both configured prefix and bot mentions
def get_prefix(bot, message):
    """Return both the configured prefix and bot mentions as valid prefixes"""
    base_prefix = config["prefix"]
    prefixes = [base_prefix]
    
    # Add case variations of the prefix
    if base_prefix.islower():
        prefixes.append(base_prefix.upper())
    elif base_prefix.isupper():
        prefixes.append(base_prefix.lower())
    else:
        # If mixed case, add both upper and lower variations
        prefixes.extend([base_prefix.upper(), base_prefix.lower()])
    
    # Add bot mentions as valid prefixes
    if bot.user:
        prefixes.extend([f'<@{bot.user.id}> ', f'<@!{bot.user.id}> '])
    
    return prefixes

# Create bot with custom prefix function
bot = commands.Bot(
    command_prefix=get_prefix, 
    intents=intents, 
    help_command=None, 
    owner_id=config["owner_id"],
    case_insensitive=True
)

# MongoDB setup
mongo_client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["pokemon"]
pokemon_collection = db["pokemon_data"]
spawn_collection = db["serverspawns"]
user_collection = db["user_data"]

# Attach to bot (type: ignore for dynamic attributes)
bot.db = db  # type: ignore
bot.pokemon_collection = pokemon_collection 
bot.spawn_collection = spawn_collection # type: ignore
bot.user_collection = user_collection # type: ignore
bot.config = config  # type: ignore

# Helper function to get the primary prefix (for display purposes)
def get_primary_prefix():
    """Get the primary prefix for display in help messages"""
    return config["prefix"]

bot.get_primary_prefix = get_primary_prefix  # type: ignore

# Load Pokemon emojis
with open("emojis.json", "r", encoding="utf-8") as f:
    bot.pokemon_emojis = json.load(f)

# Setup webhook server for Top.gg
async def setup_webhook_server():
    app = web.Application()
    
    # Add routes for each webhook-enabled cog
    for cog_name in bot.cogs:
        cog = bot.get_cog(cog_name)
        if hasattr(cog, 'setup_webhook_server'):
            await cog.setup_webhook_server(app)
    
    # Start the webhook server
    runner = web.AppRunner(app)
    await runner.setup()
    webhook_port = config.get("webhook_port", 8017)  # Default to port 8017 if not specified
    site = web.TCPSite(runner, '0.0.0.0', webhook_port)
    await site.start()
    print(f"✅ Webhook server started on port {webhook_port}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"📋 Prefixes: {config['prefix']} or @{bot.user.name}")
    print(f"👑 Owner ID: {config['owner_id']}")
    
    # Start webhook server
    asyncio.create_task(setup_webhook_server())

@bot.event
async def setup_hook():
    # Load all cogs
    cogs = [
        "Cogs.pokemon",
        "Cogs.prefix_commands", 
        "Cogs.spawn",
        "Cogs.admin",
        "Cogs.trade",
        "Cogs.market",
        "Cogs.shop",
        "Cogs.d",
        "Cogs.battle",
        "Cogs.event",
        "Cogs.quest",
        "Cogs.inventory",
        "Cogs.incense",
        "Cogs.shiny",
        "Cogs.forest",
        "Cogs.vote"
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")
    
    await bot.tree.sync()
    print("✅ Slash commands synced.")

# Get bot token from environment variable or config
bot_token = os.getenv("BOT_TOKEN") or ""

if __name__ == "__main__":
    bot.run(bot_token)
