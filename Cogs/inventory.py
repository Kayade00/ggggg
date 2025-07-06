import discord
from discord.ext import commands
import json
import asyncio
import random
from datetime import datetime

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collection = bot.pokemon_collection
        self.user_collection = bot.user_collection
        
        # Load mega stone data
        try:
            with open("mega_pokemon.json", "r", encoding="utf-8") as f:
                self.mega_data = json.load(f)
        except FileNotFoundError:
            self.mega_data = {}
        
        # Define special items
        self.special_items = {
            "vote_box": {
                "name": "Vote Box",
                "description": "A special box containing rewards for voting. Use 'b!use vote box' to open it!",
                "emoji": "📦",
                "type": "consumable"
            },
            "rare_candy": {
                "name": "Rare Candy",
                "description": "A candy that raises a Pokémon's level by 1.",
                "emoji": "🍬",
                "type": "consumable"
            },
            "shiny_charm": {
                "name": "Shiny Charm",
                "description": "A charm that increases the chance of finding shiny Pokémon.",
                "emoji": "✨",
                "type": "consumable"
            }
        }
        
        # Define available items (mega stones for now)
        self.available_items = {
            "venusaurite": {
                "name": "Venusaurite",
                "description": "Allows Venusaur to Mega Evolve into Mega Venusaur",
                "emoji": "🌿",
                "mega_evolution": "1016"
            },
            "charizardite-x": {
                "name": "Charizardite X", 
                "description": "Allows Charizard to Mega Evolve into Mega Charizard X",
                "emoji": "🔥",
                "mega_evolution": "1017"
            },
            "charizardite-y": {
                "name": "Charizardite Y",
                "description": "Allows Charizard to Mega Evolve into Mega Charizard Y", 
                "emoji": "🌪️",
                "mega_evolution": "1018"
            },
            "blastoisinite": {
                "name": "Blastoisinite",
                "description": "Allows Blastoise to Mega Evolve into Mega Blastoise",
                "emoji": "💧",
                "mega_evolution": "1019"
            },
            "alakazite": {
                "name": "Alakazite",
                "description": "Allows Alakazam to Mega Evolve into Mega Alakazam",
                "emoji": "🧠",
                "mega_evolution": "1020"
            },
            "gengarite": {
                "name": "Gengarite",
                "description": "Allows Gengar to Mega Evolve into Mega Gengar",
                "emoji": "👻",
                "mega_evolution": "1021"
            },
            "kangaskhanite": {
                "name": "Kangaskhanite",
                "description": "Allows Kangaskhan to Mega Evolve into Mega Kangaskhan",
                "emoji": "🦘",
                "mega_evolution": "1022"
            },
            "pinsirite": {
                "name": "Pinsirite",
                "description": "Allows Pinsir to Mega Evolve into Mega Pinsir",
                "emoji": "🦗",
                "mega_evolution": "1023"
            },
            "gyaradosite": {
                "name": "Gyaradosite",
                "description": "Allows Gyarados to Mega Evolve into Mega Gyarados",
                "emoji": "🐉",
                "mega_evolution": "1024"
            },
            "aerodactylite": {
                "name": "Aerodactylite",
                "description": "Allows Aerodactyl to Mega Evolve into Mega Aerodactyl",
                "emoji": "🦕",
                "mega_evolution": "1025"
            },
            "mewtwonite-x": {
                "name": "Mewtwonite X",
                "description": "Allows Mewtwo to Mega Evolve into Mega Mewtwo X",
                "emoji": "🧬",
                "mega_evolution": "1026"
            },
            "mewtwonite-y": {
                "name": "Mewtwonite Y",
                "description": "Allows Mewtwo to Mega Evolve into Mega Mewtwo Y",
                "emoji": "🧬",
                "mega_evolution": "1027"
            },
            "ampharosite": {
                "name": "Ampharosite",
                "description": "Allows Ampharos to Mega Evolve into Mega Ampharos",
                "emoji": "⚡",
                "mega_evolution": "1028"
            },
            "steelixite": {
                "name": "Steelixite",
                "description": "Allows Steelix to Mega Evolve into Mega Steelix",
                "emoji": "🔩",
                "mega_evolution": "1029"
            },
            "scizorite": {
                "name": "Scizorite",
                "description": "Allows Scizor to Mega Evolve into Mega Scizor",
                "emoji": "✂️",
                "mega_evolution": "1030"
            },
            "heracronite": {
                "name": "Heracronite",
                "description": "Allows Heracross to Mega Evolve into Mega Heracross",
                "emoji": "🦗",
                "mega_evolution": "1031"
            },
            "houndoominite": {
                "name": "Houndoominite",
                "description": "Allows Houndoom to Mega Evolve into Mega Houndoom",
                "emoji": "🔥",
                "mega_evolution": "1032"
            },
            "tyranitarite": {
                "name": "Tyranitarite",
                "description": "Allows Tyranitar to Mega Evolve into Mega Tyranitar",
                "emoji": "🦖",
                "mega_evolution": "1033"
            },
            "sceptilite": {
                "name": "Sceptilite",
                "description": "Allows Sceptile to Mega Evolve into Mega Sceptile",
                "emoji": "🌿",
                "mega_evolution": "1034"
            },
            "blazikenite": {
                "name": "Blazikenite",
                "description": "Allows Blaziken to Mega Evolve into Mega Blaziken",
                "emoji": "🔥",
                "mega_evolution": "1035"
            },
            "swampertite": {
                "name": "Swampertite",
                "description": "Allows Swampert to Mega Evolve into Mega Swampert",
                "emoji": "💧",
                "mega_evolution": "1036"
            },
            "gardevoirite": {
                "name": "Gardevoirite",
                "description": "Allows Gardevoir to Mega Evolve into Mega Gardevoir",
                "emoji": "👗",
                "mega_evolution": "1037"
            },
            "sablenite": {
                "name": "Sablenite",
                "description": "Allows Sableye to Mega Evolve into Mega Sableye",
                "emoji": "💎",
                "mega_evolution": "1038"
            },
            "mawilite": {
                "name": "Mawilite",
                "description": "Allows Mawile to Mega Evolve into Mega Mawile",
                "emoji": "🦷",
                "mega_evolution": "1039"
            },
            "aggronite": {
                "name": "Aggronite",
                "description": "Allows Aggron to Mega Evolve into Mega Aggron",
                "emoji": "🛡️",
                "mega_evolution": "1040"
            },
            "medichamite": {
                "name": "Medichamite",
                "description": "Allows Medicham to Mega Evolve into Mega Medicham",
                "emoji": "🧘",
                "mega_evolution": "1041"
            },
            "manectite": {
                "name": "Manectite",
                "description": "Allows Manectric to Mega Evolve into Mega Manectric",
                "emoji": "⚡",
                "mega_evolution": "1042"
            },
            "sharpedonite": {
                "name": "Sharpedonite",
                "description": "Allows Sharpedo to Mega Evolve into Mega Sharpedo",
                "emoji": "🦈",
                "mega_evolution": "1043"
            },
            "cameruptite": {
                "name": "Cameruptite",
                "description": "Allows Camerupt to Mega Evolve into Mega Camerupt",
                "emoji": "🌋",
                "mega_evolution": "1044"
            },
            "altarianite": {
                "name": "Altarianite",
                "description": "Allows Altaria to Mega Evolve into Mega Altaria",
                "emoji": "☁️",
                "mega_evolution": "1045"
            },
            "banettite": {
                "name": "Banettite",
                "description": "Allows Banette to Mega Evolve into Mega Banette",
                "emoji": "🪆",
                "mega_evolution": "1046"
            },
            "absolite": {
                "name": "Absolite",
                "description": "Allows Absol to Mega Evolve into Mega Absol",
                "emoji": "⚔️",
                "mega_evolution": "1047"
            },
            "glalitite": {
                "name": "Glalitite",
                "description": "Allows Glalie to Mega Evolve into Mega Glalie",
                "emoji": "❄️",
                "mega_evolution": "1048"
            },
            "salamencite": {
                "name": "Salamencite",
                "description": "Allows Salamence to Mega Evolve into Mega Salamence",
                "emoji": "🐉",
                "mega_evolution": "1049"
            },
            "metagrossite": {
                "name": "Metagrossite",
                "description": "Allows Metagross to Mega Evolve into Mega Metagross",
                "emoji": "🤖",
                "mega_evolution": "1050"
            },
            "latiasite": {
                "name": "Latiasite",
                "description": "Allows Latias to Mega Evolve into Mega Latias",
                "emoji": "❤️",
                "mega_evolution": "1051"
            },
            "latiosite": {
                "name": "Latiosite",
                "description": "Allows Latios to Mega Evolve into Mega Latios",
                "emoji": "💙",
                "mega_evolution": "1052"
            },
            "rayquazite": {
                "name": "Rayquazite",
                "description": "Allows Rayquaza to Mega Evolve into Mega Rayquaza",
                "emoji": "🌪️",
                "mega_evolution": "1053"
            },
            "lopunnite": {
                "name": "Lopunnite",
                "description": "Allows Lopunny to Mega Evolve into Mega Lopunny",
                "emoji": "🐰",
                "mega_evolution": "1054"
            },
            "lucarionite": {
                "name": "Lucarionite",
                "description": "Allows Lucario to Mega Evolve into Mega Lucario",
                "emoji": "🥋",
                "mega_evolution": "1055"
            },
            "abomasite": {
                "name": "Abomasite",
                "description": "Allows Abomasnow to Mega Evolve into Mega Abomasnow",
                "emoji": "🌲",
                "mega_evolution": "1056"
            },
            "galladite": {
                "name": "Galladite",
                "description": "Allows Gallade to Mega Evolve into Mega Gallade",
                "emoji": "⚔️",
                "mega_evolution": "1057"
            },
            "audinite": {
                "name": "Audinite",
                "description": "Allows Audino to Mega Evolve into Mega Audino",
                "emoji": "👂",
                "mega_evolution": "1058"
            },
            "diancite": {
                "name": "Diancite",
                "description": "Allows Diancie to Mega Evolve into Mega Diancie",
                "emoji": "💎",
                "mega_evolution": "1059"
            }
        }

    @commands.command(name="inventory", aliases=["in"])
    async def inventory(self, ctx):
        """Display user's item inventory"""
        # Get user data
        user_data = await self.user_collection.find_one({"user_id": ctx.author.id})
        if not user_data:
            return await ctx.reply("❌ You haven't started your Pokemon journey yet! Use `b!start` first.")
        
        # Get inventory from user data (create if doesn't exist)
        inventory = user_data.get("inventory", {})
        
        if not inventory:
            embed = discord.Embed(
                title="📦 Your Inventory",
                description="Your inventory is empty! You don't have any items yet.",
                color=0x3498db
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            return await ctx.reply(embed=embed)
        
        # Create embed
        embed = discord.Embed(
            title="📦 Your Inventory", 
            color=0x3498db
        )
        
        # Display special items first
        special_items_text = ""
        mega_stones_text = ""
        total_items = 0
        
        for item_key, quantity in inventory.items():
            if quantity > 0:
                # Check if it's a special item
                if item_key in self.special_items:
                    item_data = self.special_items[item_key]
                    special_items_text += f"{item_data['emoji']} **{item_data['name']}** × {quantity}\n"
                    total_items += quantity
                # Check if it's a mega stone
                elif item_key in self.available_items:
                    item_data = self.available_items[item_key]
                    mega_stones_text += f"{item_data['emoji']} **{item_data['name']}** × {quantity}\n"
                    total_items += quantity
                # Unknown item
                else:
                    mega_stones_text += f"📦 **{item_key.replace('_', ' ').title()}** × {quantity}\n"
                    total_items += quantity
        
        # Add special items field if any
        if special_items_text:
            embed.add_field(
                name="🎁 Special Items",
                value=special_items_text,
                inline=False
            )
        
        # Add mega stones field if any
        if mega_stones_text:
            embed.add_field(
                name="💎 Mega Stones",
                value=mega_stones_text,
                inline=False
            )
        
        # If no items
        if not special_items_text and not mega_stones_text:
            embed.description = "Your inventory is empty! You don't have any items yet."
        
        # Add summary field
        embed.add_field(
            name="📊 Summary",
            value=f"**Total Items:** {total_items}",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.reply(embed=embed)

    @commands.group(name="item", invoke_without_command=True)
    async def item(self, ctx):
        """Item management commands"""
        embed = discord.Embed(
            title="🎒 Item Commands",
            description="Manage your Pokemon's held items!",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="📥 Give Item",
            value="`b!item give <item_name>` - Give an item to your selected Pokemon",
            inline=False
        )
        
        embed.add_field(
            name="🔄 Move Item", 
            value="`b!item move <pokemon_number>` - Move held item to another Pokemon",
            inline=False
        )
        
        embed.add_field(
            name="📤 Remove Item",
            value="`b!item remove` - Remove item from selected Pokemon back to inventory",
            inline=False
        )
        
        await ctx.reply(embed=embed)

    @item.command(name="give")
    async def give_item(self, ctx, *, item_name: str):
        """Give an item to the selected Pokemon"""
        # Find the selected Pokemon
        selected_pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            return await ctx.reply("❌ You don't have a selected Pokemon! Use `b!select <number>` first.")
        
        # Check if Pokemon already has an item
        if selected_pokemon.get("held_item"):
            current_item = self.available_items.get(selected_pokemon["held_item"], {})
            current_name = current_item.get("name", selected_pokemon["held_item"])
            return await ctx.reply(f"❌ Your {selected_pokemon['pokemon_name']} is already holding **{current_name}**! Remove it first with `b!item remove`.")
        
        # Find matching item
        item_key = None
        for key, item_data in self.available_items.items():
            if item_name.lower() in [key.lower(), item_data["name"].lower()]:
                item_key = key
                break
        
        if not item_key:
            available_items = ", ".join([item["name"] for item in self.available_items.values()])
            return await ctx.reply(f"❌ Item not found! Available items: {available_items}")
        
        # Check if user has the item in inventory
        user_data = await self.user_collection.find_one({"user_id": ctx.author.id})
        inventory = user_data.get("inventory", {})
        
        if inventory.get(item_key, 0) <= 0:
            item_data = self.available_items[item_key]
            return await ctx.reply(f"❌ You don't have any **{item_data['name']}** in your inventory!")
        
        # Give item to Pokemon and remove from inventory
        await self.collection.update_one(
            {"_id": selected_pokemon["_id"]},
            {"$set": {"held_item": item_key}}
        )
        
        # Update inventory
        new_quantity = inventory.get(item_key, 0) - 1
        if new_quantity <= 0:
            inventory.pop(item_key, None)
        else:
            inventory[item_key] = new_quantity
            
        await self.user_collection.update_one(
            {"user_id": ctx.author.id},
            {"$set": {"inventory": inventory}}
        )
        
        item_data = self.available_items[item_key]
        embed = discord.Embed(
            title="✅ Item Given!",
            description=f"**{selected_pokemon['pokemon_name']}** is now holding **{item_data['name']}**!",
            color=0x2ecc71
        )
        
        embed.add_field(
            name="📦 Item Info",
            value=f"{item_data['emoji']} {item_data['description']}",
            inline=False
        )
        
        await ctx.reply(embed=embed)

    @item.command(name="move")
    async def move_item(self, ctx, pokemon_number: int):
        """Move held item from selected Pokemon to another Pokemon"""
        # Find selected Pokemon
        selected_pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            return await ctx.reply("❌ You don't have a selected Pokemon!")
        
        # Check if selected Pokemon has an item
        if not selected_pokemon.get("held_item"):
            return await ctx.reply("❌ Your selected Pokemon isn't holding any item!")
        
        # Find target Pokemon
        target_pokemon = await self.collection.find_one({"user_id": ctx.author.id, "pokemon_number": pokemon_number})
        if not target_pokemon:
            return await ctx.reply(f"❌ You don't have a Pokemon with number {pokemon_number}!")
        
        # Check if target Pokemon already has an item
        if target_pokemon.get("held_item"):
            current_item = self.available_items.get(target_pokemon["held_item"], {})
            current_name = current_item.get("name", target_pokemon["held_item"])
            return await ctx.reply(f"❌ Pokemon #{pokemon_number} ({target_pokemon['pokemon_name']}) is already holding **{current_name}**!")
        
        # Move the item
        held_item = selected_pokemon["held_item"]
        
        await self.collection.update_one(
            {"_id": selected_pokemon["_id"]},
            {"$unset": {"held_item": ""}}
        )
        
        await self.collection.update_one(
            {"_id": target_pokemon["_id"]},
            {"$set": {"held_item": held_item}}
        )
        
        item_data = self.available_items.get(held_item, {"name": held_item, "emoji": "📦"})
        
        embed = discord.Embed(
            title="🔄 Item Moved!",
            description=f"**{item_data['name']}** moved from **{selected_pokemon['pokemon_name']}** to **{target_pokemon['pokemon_name']}** (#{pokemon_number})!",
            color=0xf39c12
        )
        
        await ctx.reply(embed=embed)

    @item.command(name="remove")
    async def remove_item(self, ctx):
        """Remove held item from selected Pokemon back to inventory"""
        # Find selected Pokemon
        selected_pokemon = await self.collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            return await ctx.reply("❌ You don't have a selected Pokemon!")
        
        # Check if Pokemon has an item
        if not selected_pokemon.get("held_item"):
            return await ctx.reply("❌ Your selected Pokemon isn't holding any item!")
        
        held_item = selected_pokemon["held_item"]
        
        # Remove item from Pokemon
        await self.collection.update_one(
            {"_id": selected_pokemon["_id"]},
            {"$unset": {"held_item": ""}}
        )
        
        # Add item back to inventory
        user_data = await self.user_collection.find_one({"user_id": ctx.author.id})
        inventory = user_data.get("inventory", {})
        inventory[held_item] = inventory.get(held_item, 0) + 1
        
        await self.user_collection.update_one(
            {"user_id": ctx.author.id},
            {"$set": {"inventory": inventory}}
        )
        
        item_data = self.available_items.get(held_item, {"name": held_item, "emoji": "📦"})
        
        embed = discord.Embed(
            title="📤 Item Removed!",
            description=f"**{item_data['name']}** removed from **{selected_pokemon['pokemon_name']}** and added back to your inventory!",
            color=0xe67e22
        )
        
        await ctx.reply(embed=embed)

    async def add_item_to_inventory(self, user_id: int, item_name: str, amount: int = 1):
        """Add an item to user's inventory"""
        # Check if user has an inventory
        user_data = await self.user_collection.find_one({"user_id": user_id})
        
        if not user_data:
            # Create user profile if it doesn't exist
            user_data = {
                "user_id": user_id,
                "coins": 0,
                "diamonds": 0,
                "inventory": {}
            }
            await self.user_collection.insert_one(user_data)
        
        # Make sure inventory exists
        if "inventory" not in user_data:
            await self.user_collection.update_one(
                {"user_id": user_id},
                {"$set": {"inventory": {}}}
            )
        
        # Add item to inventory
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$inc": {f"inventory.{item_name}": amount}}
        )
        print(f"📦 Added {amount}x {item_name} to user {user_id}'s inventory")
    
    @commands.command(name="use", aliases=["open"])
    async def use_item(self, ctx, *, item_name: str):
        """Use or open an item from your inventory"""
        user_id = ctx.author.id
        user_data = await self.user_collection.find_one({"user_id": user_id})
        
        if not user_data or "inventory" not in user_data:
            await ctx.send("❌ You don't have any items in your inventory!")
            return
        
        # Normalize item name
        item_name = item_name.lower().strip()
        
        # Handle special cases for item names
        if item_name in ["vote box", "votebox"]:
            item_name = "vote_box"
        
        # Check if user has the item
        inventory = user_data.get("inventory", {})
        if item_name not in inventory or inventory[item_name] <= 0:
            await ctx.send(f"❌ You don't have any **{item_name.replace('_', ' ')}** in your inventory!")
            return
        
        # Process the item use
        if item_name == "vote_box":
            await self.open_vote_box(ctx, user_id)
        else:
            await ctx.send(f"❓ I don't know how to use **{item_name.replace('_', ' ')}**!")
    
    async def open_vote_box(self, ctx, user_id: int):
        """Open a vote box to get random rewards"""
        import random
        
        # Remove one vote box from inventory
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"inventory.vote_box": -1}}
        )
        
        # Define possible rewards
        rewards = [
            {"type": "coins", "amount": 500, "weight": 30, "emoji": "🪙"},
            {"type": "coins", "amount": 1000, "weight": 15, "emoji": "🪙"},
            {"type": "coins", "amount": 2000, "weight": 5, "emoji": "🪙"},
            {"type": "diamonds", "amount": 1, "weight": 10, "emoji": "💎"},
            {"type": "diamonds", "amount": 2, "weight": 5, "emoji": "💎"},
            {"type": "diamonds", "amount": 5, "weight": 1, "emoji": "💎"},
            {"type": "pokemon", "weight": 15, "emoji": "🎁"},
            {"type": "shiny_charm", "amount": 1, "weight": 3, "emoji": "✨"}
        ]
        
        # Calculate total weight
        total_weight = sum(reward["weight"] for reward in rewards)
        
        # Select random rewards (1-3 different rewards)
        num_rewards = random.choices([1, 2, 3], weights=[50, 30, 20])[0]
        selected_rewards = []
        
        for _ in range(num_rewards):
            # Select a random reward based on weight
            rand_val = random.uniform(0, total_weight)
            current_weight = 0
            
            for reward in rewards:
                current_weight += reward["weight"]
                if rand_val <= current_weight:
                    # Add to selected rewards
                    selected_rewards.append(reward)
                    break
        
        # Process rewards
        reward_text = []
        
        for reward in selected_rewards:
            reward_type = reward["type"]
            emoji = reward["emoji"]
            
            if reward_type == "coins":
                amount = reward["amount"]
                await self.update_user_balance(user_id, coins_change=amount)
                reward_text.append(f"{emoji} **{amount}** coins")
            
            elif reward_type == "diamonds":
                amount = reward["amount"]
                await self.update_user_balance(user_id, diamonds_change=amount)
                reward_text.append(f"{emoji} **{amount}** diamonds")
            
            elif reward_type == "pokemon":
                # Generate a random high IV Pokémon
                pokemon = await self.generate_high_iv_pokemon(user_id)
                if pokemon:
                    pokemon_name = pokemon.get("pokemon_name", "Unknown Pokémon")
                    pokemon_number = pokemon.get("pokemon_number")
                    ivs_total = sum(pokemon.get("ivs", [0, 0, 0, 0, 0, 0]))
                    reward_text.append(f"{emoji} **{pokemon_name}** (#{pokemon_number}) with **{ivs_total}** total IVs")
            
            else:
                # Item reward
                amount = reward["amount"]
                await self.add_item_to_inventory(user_id, reward_type, amount)
                item_name = reward_type.replace("_", " ").title()
                reward_text.append(f"{emoji} **{amount}x** {item_name}")
        
        # Create embed
        embed = discord.Embed(
            title="📦 Vote Box Opened!",
            description=f"You opened a Vote Box and received:\n\n" + "\n".join(reward_text),
            color=0xf1c40f
        )
        
        await ctx.send(embed=embed)
    
    async def generate_high_iv_pokemon(self, user_id):
        """Generate a random Pokémon with high IVs (70+)"""
        import random
        import json
        
        try:
            # Load Pokémon data
            with open("pokedex.json", "r", encoding="utf-8") as f:
                pokedex = json.load(f)
            
            # Get a random Pokémon
            pokemon_id = random.choice(list(pokedex.keys()))
            pokemon_data = pokedex[pokemon_id]
            
            # Generate high IVs (minimum 70% total, each IV at least 10)
            min_total = 180  # 70% of max 255
            ivs = []
            
            for _ in range(6):
                ivs.append(random.randint(10, 31))
            
            # Ensure total is at least min_total
            while sum(ivs) < min_total:
                # Find the lowest IV and increase it
                min_index = ivs.index(min(ivs))
                if ivs[min_index] < 31:
                    ivs[min_index] += 1
            
            # Create Pokémon data
            pokemon = {
                "user_id": user_id,
                "pokemon_id": pokemon_id,
                "pokemon_name": pokemon_data["name"],
                "pokemon_number": len(await self.collection.distinct("pokemon_number", {"user_id": user_id})) + 1,
                "level": random.randint(5, 25),
                "xp": 0,
                "ivs": ivs,
                "nature": random.choice(["Adamant", "Brave", "Bold", "Calm", "Careful", "Gentle", "Hasty", 
                                        "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive", 
                                        "Naughty", "Quiet", "Quirky", "Rash", "Relaxed", "Sassy", "Serious", 
                                        "Timid", "Hardy"]),
                "caught_at": datetime.utcnow().isoformat(),
                "shiny": random.random() < 0.05,  # 5% chance for shiny
                "friendship": 0
            }
            
            # Save to database
            result = await self.collection.insert_one(pokemon)
            pokemon["_id"] = result.inserted_id
            
            print(f"🎁 Generated high IV Pokémon {pokemon['pokemon_name']} (#{pokemon['pokemon_number']}) with IVs {ivs} for user {user_id}")
            return pokemon
            
        except Exception as e:
            print(f"❌ Error generating high IV Pokémon: {e}")
            return None

    async def update_user_balance(self, user_id: int, coins_change=0, diamonds_change=0):
        """Update user's balance"""
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"coins": coins_change, "diamonds": diamonds_change}},
            upsert=True
        )
        print(f"🪙 Inventory: Updated balance for user {user_id}: +{coins_change} coins, +{diamonds_change} diamonds")

async def setup(bot):
    await bot.add_cog(Inventory(bot)) 