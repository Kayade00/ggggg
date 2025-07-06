import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from datetime import datetime
import asyncio
from theme_loader import theme

class Shop(commands.Cog):
    def __init__(self, bot, pokemon_collection, user_profiles):
        self.bot = bot
        self.pokemon_collection = pokemon_collection
        self.user_profiles = user_profiles

    async def ensure_user_profile(self, user_id):
        """Ensure user has a profile in the database"""
        profile = await self.user_profiles.find_one({"user_id": user_id})
        if not profile:
            profile = {
                "user_id": user_id,
                "coins": 1000,  # Starting coins
                "diamonds": 0,
                "created_at": datetime.utcnow()
            }
            await self.user_profiles.insert_one(profile)
        return profile

    async def get_user_balance(self, user_id):
        """Get user's coin and diamond balance"""
        profile = await self.ensure_user_profile(user_id)
        return profile.get("coins", 0), profile.get("diamonds", 0)

    async def update_user_balance(self, user_id, coins_change=0, diamonds_change=0):
        """Update user's balance"""
        await self.ensure_user_profile(user_id)
        await self.user_profiles.update_one(
            {"user_id": user_id},
            {"$inc": {"coins": coins_change, "diamonds": diamonds_change}}
        )

    def calculate_xp_for_level(self, level):
        """Calculate XP needed for a specific level"""
        return int(level ** 3)

    def get_nature_stat_changes(self, nature_modifiers):
        """Get stat change description from nature modifiers"""
        stat_names = ["HP", "Atk", "Def", "SpAtk", "SpDef", "Speed"]
        increased_stat = None
        decreased_stat = None
        
        for i, modifier in enumerate(nature_modifiers):
            if modifier > 1.0:
                increased_stat = stat_names[i]
            elif modifier < 1.0:
                decreased_stat = stat_names[i]
        
        if increased_stat and decreased_stat:
            return f"(+{increased_stat} -{decreased_stat})"
        elif increased_stat:
            return f"(+{increased_stat})"
        elif decreased_stat:
            return f"(-{decreased_stat})"
        else:
            return "(Neutral)"

    def get_shop_items(self):
        """Define all shop items organized by category"""
        # Load natures for mints
        import json
        try:
            with open("nature.json", "r", encoding="utf-8") as f:
                nature_data = json.load(f)
                natures = nature_data["natures"]
        except FileNotFoundError:
            natures = {"Hardy": [1, 1, 1, 1, 1, 1], "Adamant": [1, 1.1, 1, 0.9, 1, 1], "Modest": [1, 0.9, 1, 1.1, 1, 1], "Timid": [1, 0.9, 1, 1, 1, 1.1], "Jolly": [1, 1, 1, 0.9, 1, 1.1], "Bold": [1, 0.9, 1.1, 1, 1, 1], "Impish": [1, 1, 1.1, 0.9, 1, 1], "Calm": [1, 0.9, 1, 1, 1.1, 1], "Careful": [1, 1, 1, 0.9, 1.1, 1], "Brave": [1, 1.1, 1, 1, 1, 0.9]}
        
        # Create mint items
        mint_items = {}
        for nature, modifiers in natures.items():
            mint_key = f"{nature.lower()}_mint"
            stat_changes = self.get_nature_stat_changes(modifiers)
            mint_items[mint_key] = {
                "name": f"{nature} Mint {stat_changes}",
                "description": f"Changes your selected Pokémon's nature to {nature}!",
                "price": 20,
                "currency": "coins",
                "emoji": theme.emoji("shop", "mint"),
                "nature": nature
            }
        
        return {
            "exp_stuff": {
                "name": f"{theme.emoji('shop', 'exp_items')} EXP Items",
                "description": "Items to boost your Pokémon's experience!",
                "items": {
                    "rare_candy": {
                        "name": f"{theme.emoji('shop', 'rare_candy')} Rare Candy",
                        "description": "Instantly levels up your selected Pokémon by 1 level!",
                        "price": 100,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "rare_candy")
                    }
                }
            },
            "mints": {
                "name": f"{theme.emoji('shop', 'nature_mints')} Nature Mints",
                "description": "Change your Pokémon's nature with these special mints!",
                "items": mint_items
            },
            "friendship": {
                "name": f"{theme.emoji('shop', 'friendship_berries')} Friendship Berries",
                "description": "Berries to boost your Pokémon's friendship!",
                "items": {
                    "grepa_berry": {
                        "name": f"{theme.emoji('shop', 'grepa_berry')} Grepa Berry (PERMANENT)",
                        "description": "Permanently increases friendship gain by +5/hour for ALL Pokémon! (One-time purchase)",
                        "price": 100000,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "grepa_berry"),
                        "type": "permanent",
                        "friendship_bonus": 5
                    },
                    "hondew_berry": {
                        "name": f"{theme.emoji('shop', 'hondew_berry')} Hondew Berry (PERMANENT)",
                        "description": "Permanently increases friendship gain by +2/hour for ALL Pokémon! (One-time purchase)",
                        "price": 50000,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "hondew_berry"),
                        "type": "permanent",
                        "friendship_bonus": 2
                    },
                    "kelpsy_berry": {
                        "name": f"{theme.emoji('shop', 'kelpsy_berry')} Kelpsy Berry",
                        "description": "Instantly adds +50 friendship to your selected Pokémon!",
                        "price": 500,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "kelpsy_berry"),
                        "type": "consumable",
                        "friendship_points": 50
                    },
                    "pomeg_berry": {
                        "name": f"{theme.emoji('shop', 'pomeg_berry')} Pomeg Berry",
                        "description": "Instantly adds +50 friendship to your selected Pokémon!",
                        "price": 500,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "pomeg_berry"),
                        "type": "consumable",
                        "friendship_points": 50
                    },
                    "qualot_berry": {
                        "name": f"{theme.emoji('shop', 'qualot_berry')} Qualot Berry",
                        "description": "Instantly adds +10 friendship to your selected Pokémon!",
                        "price": 100,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "qualot_berry"),
                        "type": "consumable",
                        "friendship_points": 10
                    },
                    "tamato_berry": {
                        "name": f"{theme.emoji('shop', 'tamato_berry')} Tamato Berry",
                        "description": "Instantly adds +10 friendship to your selected Pokémon!",
                        "price": 100,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "tamato_berry"),
                        "type": "consumable",
                        "friendship_points": 10
                    }
                }
            },
            "diamond_stuff": {
                "name": f"{theme.emoji('shop', 'diamond_items')} Diamond Items", 
                "description": "Premium items bought with diamonds!",
                "items": {
                    # No items yet, will show "nothing here yet"
                }
            },
            "multipliers": {
                "name": f"{theme.emoji('shop', 'multipliers')} Multipliers",
                "description": "Items that provide temporary boosts and bonuses!",
                "items": {
                    "shiny_charm": {
                        "name": f"{theme.emoji('shop', 'shiny_charm')} Shiny Charm",
                        "description": "Increases shiny chance by 2% for 1 week! (Time stacks if bought multiple times)",
                        "price": 7500,
                        "currency": "coins",
                        "emoji": theme.emoji("shop", "shiny_charm"),
                        "type": "temporary",
                        "duration_days": 7,
                        "shiny_boost": 2.0
                    }
                }
            }
        }

    @commands.group(name="shop", aliases=["store"], invoke_without_command=True)
    async def shop(self, ctx):
        """Browse the Pokémon shop"""
        # Get user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        
        # Build the full description using theme system
        description = "Browse categories and purchase items with your coins and diamonds!"
        
        # Add categories info using theme formatting
        shop_items = self.get_shop_items()
        categories_text = f"\n\n{theme.format_text('bold', 'Shop Categories:')}\n"
        
        for category_key, category_data in shop_items.items():
            item_count = len(category_data["items"])
            if item_count > 0:
                categories_text += f"{theme.get_separator('bullet')} {theme.format_text('bold', category_data['name'])} - {item_count} items available\n"
            else:
                categories_text += f"{theme.get_separator('bullet')} {theme.format_text('bold', category_data['name'])} - Coming soon!\n"
        
        # Add balance info using theme
        balance_text = f"\n{theme.format_text('bold', 'Your Balance:')}\n{theme.format_balance(coins, diamonds)}"
        
        # Add usage info
        prefix = ctx.bot.get_primary_prefix()
        usage_text = f"\nUse the dropdown below to browse categories or {theme.format_text('code', f'{prefix}buy <item> [amount]')} to purchase directly!"
        
        full_description = description + categories_text + balance_text + usage_text
        
        # Create themed embed
        embed = theme.create_embed(
            title="Pokémon Shop",
            description=full_description,
            color_name="shop"
        )
        
        view = ShopView(self, ctx.author.id)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="buy")
    async def buy_item(self, ctx, *, args=None):
        """Buy items from the shop"""
        if not args:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}buy <item> [amount]`\nExample: `{prefix}buy candy 5` or `{prefix}buy adamant mint`")
        
        # Split args to get item name and potential amount
        parts = args.strip().split()
        
        # Check if last part is a number (amount)
        amount = None
        if len(parts) > 1 and parts[-1].isdigit():
            amount = int(parts[-1])
            item_name = " ".join(parts[:-1])
        else:
            item_name = " ".join(parts)
            amount = 1  # Default to 1
        
        # Check for mint purchases first (no amount needed)
        if "mint" in item_name.lower():
            await self.buy_mint(ctx, item_name)
            return
        
        # Validate amount for non-mint items
        if amount <= 0:
            return await ctx.reply("❌ Amount must be greater than 0!")
        
        # Handle rare candy purchase
        if item_name.lower() in ["candy", "rare_candy", "rarecandy"]:
            await self.buy_rare_candy(ctx, amount)
        # Handle berry purchases
        elif any(berry in item_name.lower() for berry in ["grepa", "hondew", "kelpsy", "pomeg", "qualot", "tamato"]):
            await self.buy_berry(ctx, item_name, amount)
        # Handle multiplier purchases
        elif item_name.lower() in ["shiny_charm", "shinycharm", "shiny charm"]:
            await self.buy_shiny_charm(ctx)
        else:
            return await ctx.reply(f"❌ Item '{item_name}' not found in shop!")

    
    async def buy_rare_candy(self, ctx, amount):
        """Handle rare candy purchase and application"""
        # Get shop items
        shop_items = self.get_shop_items()
        candy_item = shop_items["exp_stuff"]["items"]["rare_candy"]
        
        total_cost = candy_item["price"] * amount
        
        # Check user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        if coins < total_cost:
            return await ctx.reply(f"❌ You don't have enough coins! You need **{total_cost:,}** coins but only have **{coins:,}**.")
        
        # Check if user has a selected Pokémon
        selected_pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You don't have a selected Pokémon! Use `{prefix}select <number>` to select one first.")
        
        pokemon_name = selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']
        current_level = selected_pokemon['level']
        
        # Check if Pokemon is already at level cap
        if current_level >= 100:
            return await ctx.reply(f"❌ **{pokemon_name}** is already at the maximum level (100)! Rare Candies cannot be used.")
        
        # Calculate actual level increase (capped at 100)
        max_possible_increase = 100 - current_level
        actual_increase = min(amount, max_possible_increase)
        new_level = current_level + actual_increase
        
        # Adjust cost if we're using fewer candies than requested
        if actual_increase < amount:
            total_cost = candy_item["price"] * actual_increase
            amount = actual_increase  # Update amount for display
        
        # Create confirmation embed
        embed = discord.Embed(
            title="🍬 Rare Candy Purchase",
            description=f"Are you sure you want to buy **{amount}** Rare Candy for **{total_cost:,}** coins?",
            color=0x58a64e
        )
        
        embed.add_field(
            name="💰 Purchase Details",
            value=(
                f"Item: {candy_item['emoji']} **{candy_item['name']}**\n"
                f"Quantity: {amount}\n"
                f"Cost: {total_cost:,} coins\n"
                f"Your balance: {coins:,} coins\n"
                f"After purchase: {coins - total_cost:,} coins"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📈 Level Up Preview",
            value=(
                f"Pokémon: **{pokemon_name}**\n"
                f"Current Level: {current_level}\n"
                f"New Level: {new_level}\n"
                f"Level increase: +{amount}"
            ),
            inline=True
        )
        
        # Add warning if hitting level cap
        if new_level == 100:
            embed.add_field(
                name="⚠️ Level Cap Notice",
                value="This will bring your Pokémon to the maximum level (100)!",
                inline=False
            )
        
        embed.set_footer(text="⚠️ This will immediately level up your selected Pokémon!")
        
        class PurchaseView(View):
            def __init__(self, shop_cog, author_id, pokemon_data, candy_amount, total_price):
                super().__init__(timeout=60)
                self.shop_cog = shop_cog
                self.author_id = author_id
                self.pokemon = pokemon_data
                self.amount = candy_amount
                self.cost = total_price
            
            @discord.ui.button(label="✅ Confirm Purchase", style=discord.ButtonStyle.green)
            async def confirm_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can confirm this purchase!", ephemeral=True)
                
                # Double-check balance (in case user spent coins elsewhere)
                current_coins, _ = await self.shop_cog.get_user_balance(self.author_id)
                if current_coins < self.cost:
                    return await interaction.response.send_message("❌ You no longer have enough coins for this purchase!", ephemeral=True)
                
                # Double-check level cap (in case Pokemon leveled up elsewhere)
                current_pokemon = await self.shop_cog.pokemon_collection.find_one({"_id": self.pokemon["_id"]})
                if current_pokemon['level'] >= 100:
                    return await interaction.response.send_message("❌ This Pokémon is already at maximum level!", ephemeral=True)
                
                # Deduct coins
                await self.shop_cog.update_user_balance(self.author_id, coins_change=-self.cost)
                
                # Level up the Pokémon (ensure we don't exceed level 100)
                new_level = min(current_pokemon['level'] + self.amount, 100)
                # Set XP to 0 for the new level (no progress toward next level)
                # Exception: Level 100 Pokemon should have max XP (3750)
                new_xp = 3750 if new_level == 100 else 0
                
                await self.shop_cog.pokemon_collection.update_one(
                    {"_id": self.pokemon["_id"]},
                    {"$set": {"level": new_level, "xp": new_xp}}
                )
                
                # Create success embed
                pokemon_name = self.pokemon.get('nickname') or self.pokemon['pokemon_name']
                actual_level_gain = new_level - current_pokemon['level']
                
                success_embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=(
                        f"**{pokemon_name}** leveled up from **{current_pokemon['level']}** to **{new_level}**!"
                    ),
                    color=0x00ff00
                )
                
                success_embed.add_field(
                    name="📦 Items Used",
                    value=(
                        f"🍬 **{self.amount}** Rare Candy\n"
                        f"📈 **+{actual_level_gain}** levels gained"
                    ),
                    inline=True
                )
                
                success_embed.add_field(
                    name="💰 Transaction",
                    value=(
                        f"Spent: {self.cost:,} coins\n"
                        f"Remaining: {current_coins - self.cost:,} coins"
                    ),
                    inline=True
                )
                
                if new_level == 100:
                    success_embed.add_field(
                        name="🏆 Maximum Level Reached!",
                        value="Your Pokémon has reached the level cap of 100!",
                        inline=False
                    )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def cancel_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can cancel this purchase!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Purchase Cancelled",
                    description="Your Rare Candy purchase was cancelled.",
                    color=0x808080
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = PurchaseView(self, ctx.author.id, selected_pokemon, amount, total_cost)
        await ctx.reply(embed=embed, view=view)

    async def buy_mint(self, ctx, item_name):
        """Handle mint purchase and application"""
        # Get shop items
        shop_items = self.get_shop_items()
        mint_items = shop_items["mints"]["items"]
        
        # Find the requested mint
        mint_item = None
        mint_key = None
        
        # Check various mint name formats
        item_lower = item_name.lower().replace(" ", "_")
        if not item_lower.endswith("_mint"):
            item_lower += "_mint"
        
        # Try to find the mint by key
        if item_lower in mint_items:
            mint_key = item_lower
            mint_item = mint_items[item_lower]
        else:
            # Try to find by nature name
            for key, item in mint_items.items():
                if item["nature"].lower() in item_name.lower():
                    mint_key = key
                    mint_item = item
                    break
        
        if not mint_item:
            return await ctx.reply(f"❌ Mint '{item_name}' not found! Available mints: adamant mint, modest mint, timid mint, etc.")
        
        total_cost = mint_item["price"]
        
        # Check user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        if coins < total_cost:
            return await ctx.reply(f"❌ You don't have enough coins! You need **{total_cost:,}** coins but only have **{coins:,}**.")
        
        # Check if user has a selected Pokémon
        selected_pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You don't have a selected Pokémon! Use `{prefix}select <number>` to select one first.")
        
        pokemon_name = selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']
        current_nature = selected_pokemon.get('nature', 'Hardy')
        new_nature = mint_item["nature"]
        
        # Check if Pokemon already has this nature
        if current_nature == new_nature:
            return await ctx.reply(f"❌ **{pokemon_name}** already has the {new_nature} nature!")
        
        # Automatically purchase and apply the mint
        # Deduct coins
        await self.update_user_balance(ctx.author.id, coins_change=-total_cost)
        
        # Change the Pokémon's nature
        await self.pokemon_collection.update_one(
            {"_id": selected_pokemon["_id"]},
            {"$set": {"nature": new_nature}}
        )
        
        # Create success embed
        embed = discord.Embed(
            title="✅ Nature Changed!",
            description=(
                f"**{pokemon_name}**'s nature has been changed from **{current_nature}** to **{new_nature}**!"
            ),
            color=0x00ff00
        )
        
        embed.add_field(
            name="📦 Item Used",
            value=f"🌿 **{mint_item['name']}**",
            inline=True
        )
        
        embed.add_field(
            name="💰 Transaction",
            value=(
                f"Spent: {total_cost:,} coins\n"
                f"Remaining: {coins - total_cost:,} coins"
            ),
            inline=True
        )
        
        await ctx.reply(embed=embed)

    async def buy_shiny_charm(self, ctx):
        """Buy a shiny charm multiplier"""
        user_id = ctx.author.id
        coins, diamonds = await self.get_user_balance(user_id)
        
        shop_items = self.get_shop_items()
        item_data = shop_items["multipliers"]["items"]["shiny_charm"]
        price = item_data["price"]
        
        if coins < price:
            return await ctx.reply(f"❌ You don't have enough coins! You need {price} coins but only have {coins}.")
        
        # Check if user already has a shiny charm
        profile = await self.user_profiles.find_one({"user_id": user_id})
        current_charm = profile.get("shiny_charm", {}) if profile else {}
        
        # Calculate new expiration time
        from datetime import timedelta
        current_time = datetime.utcnow()
        
        if current_charm and current_charm.get("expires_at"):
            # Extend existing charm
            current_expiry = current_charm["expires_at"]
            if isinstance(current_expiry, str):
                current_expiry = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
            new_expiry = current_expiry + timedelta(days=7)
        else:
            # New charm
            new_expiry = current_time + timedelta(days=7)
        
        # Update user profile
        await self.user_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "shiny_charm": {
                        "active": True,
                        "expires_at": new_expiry.isoformat(),
                        "shiny_boost": 2.0
                    }
                },
                "$inc": {"coins": -price}
            },
            upsert=True
        )
        
        # Create success message
        embed = discord.Embed(
            title="✨ Shiny Charm Purchased!",
            description=f"You now have a **Shiny Charm** active!",
            color=0xFFD700
        )
        
        embed.add_field(
            name="📊 Effect",
            value="• **+2%** to all shiny chances\n• Duration: **1 week**",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Expires",
            value=f"<t:{int(new_expiry.timestamp())}:R>",
            inline=False
        )
        
        embed.add_field(
            name="💰 Cost",
            value=f"**{price} coins**",
            inline=True
        )
        
        embed.add_field(
            name="💎 New Balance",
            value=f"**{coins - price} coins**",
            inline=True
        )
        
        embed.set_footer(text="Use b!sh to check your shiny hunt status!")
        
        await ctx.reply(embed=embed)

    async def buy_berry(self, ctx, item_name, amount):
        """Handle berry purchase and application"""
        # Get shop items
        shop_items = self.get_shop_items()
        friendship_items = shop_items["friendship"]["items"]
        
        # Find the berry item
        berry_item = None
        berry_key = None
        
        # Map berry names to keys
        berry_mappings = {
            "grepa": "grepa_berry",
            "hondew": "hondew_berry", 
            "kelpsy": "kelpsy_berry",
            "pomeg": "pomeg_berry",
            "qualot": "qualot_berry",
            "tamato": "tamato_berry"
        }
        
        for berry_name, key in berry_mappings.items():
            if berry_name in item_name.lower():
                berry_item = friendship_items.get(key)
                berry_key = key
                break
        
        if not berry_item:
            return await ctx.reply(f"❌ Berry '{item_name}' not found in shop!")
        
        # Check if it's a permanent berry and user already owns it
        if berry_item.get("type") == "permanent":
            profile = await self.ensure_user_profile(ctx.author.id)
            permanent_berries = profile.get("permanent_friendship_berries", [])
            
            if berry_key in permanent_berries:
                return await ctx.reply(f"❌ You already own {berry_item['name']}! This is a one-time purchase.")
            
            # For permanent berries, amount should be 1
            if amount != 1:
                return await ctx.reply(f"❌ {berry_item['name']} is a permanent upgrade - you can only buy 1!")
        
        # Calculate total cost
        total_cost = berry_item["price"] * amount
        
        # Check user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        if coins < total_cost:
            return await ctx.reply(f"❌ You don't have enough coins! You need **{total_cost:,}** coins but only have **{coins:,}**.")
        
        # For consumable berries, check if user has a selected Pokémon
        if berry_item.get("type") == "consumable":
            selected_pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "selected": True})
            if not selected_pokemon:
                return await ctx.reply("❌ You need to have a selected Pokémon to use consumable berries!")
        
        # Handle permanent berry purchase
        if berry_item.get("type") == "permanent":
            # Deduct coins
            await self.update_user_balance(ctx.author.id, coins_change=-total_cost)
            
            # Add to permanent berries list
            await self.user_profiles.update_one(
                {"user_id": ctx.author.id},
                {"$addToSet": {"permanent_friendship_berries": berry_key}}
            )
            
            # Create success embed
            embed = discord.Embed(
                title="🍇 Permanent Berry Purchased!",
                description=f"Successfully purchased {berry_item['name']}!",
                color=0x00FF00
            )
            
            embed.add_field(
                name="📈 Permanent Effect",
                value=(
                    f"All your Pokémon now gain +{berry_item['friendship_bonus']} friendship per hour!"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💰 Transaction",
                value=(
                    f"Spent: {total_cost:,} coins\n"
                    f"Remaining: {coins - total_cost:,} coins"
                ),
                inline=True
            )
            
            await ctx.reply(embed=embed)
        
        # Handle consumable berry purchase
        else:
            # Deduct coins
            await self.update_user_balance(ctx.author.id, coins_change=-total_cost)
            
            # Apply friendship to selected Pokémon
            friendship_gained = berry_item["friendship_points"] * amount
            selected_pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "selected": True})
            
            current_friendship = selected_pokemon.get("friendship", 0)
            new_friendship = min(255, current_friendship + friendship_gained)  # Cap at 255
            
            await self.pokemon_collection.update_one(
                {"user_id": ctx.author.id, "selected": True},
                {"$set": {"friendship": new_friendship}}
            )
            
            # Create success embed
            embed = discord.Embed(
                title="🍓 Berry Used Successfully!",
                description=(
                    f"Fed {amount} {berry_item['name']}(s) to **{selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']}**!"
                ),
                color=0x00FF00
            )
            
            embed.add_field(
                name="💖 Friendship Change",
                value=(
                    f"**{current_friendship}** → **{new_friendship}** (+{new_friendship - current_friendship})"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💰 Transaction",
                value=(
                    f"Spent: {total_cost:,} coins\n"
                    f"Remaining: {coins - total_cost:,} coins"
                ),
                inline=True
            )
            
            await ctx.reply(embed=embed)

class ShopView(View):
    def __init__(self, shop_cog, user_id):
        super().__init__(timeout=300)
        self.shop_cog = shop_cog
        self.user_id = user_id
        
        # Add category dropdown
        self.add_item(CategorySelect(shop_cog, user_id))

class CategorySelect(Select):
    def __init__(self, shop_cog, user_id):
        self.shop_cog = shop_cog
        self.user_id = user_id
        
        # Create options for each category
        shop_items = shop_cog.get_shop_items()
        options = []
        
        for category_key, category_data in shop_items.items():
            item_count = len(category_data["items"])
            options.append(discord.SelectOption(
                label=category_data["name"],
                description=f"{category_data['description']} ({item_count} items)",
                value=category_key
            ))
        
        super().__init__(
            placeholder="🛒 Select a category to browse...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This shop interface is not for you!", ephemeral=True)
        
        category_key = self.values[0]
        shop_items = self.shop_cog.get_shop_items()
        category = shop_items[category_key]
        
        # Add user's balance
        coins, diamonds = await self.shop_cog.get_user_balance(self.user_id)
        
        # Check if category has many items (needs pagination)
        if category["items"] and len(category["items"]) > 15:
            # Create paginated view for large categories
            embeds = []
            items_list = list(category["items"].items())
            items_per_page = 15
            
            for page in range(0, len(items_list), items_per_page):
                page_items = items_list[page:page + items_per_page]
                page_num = (page // items_per_page) + 1
                total_pages = (len(items_list) + items_per_page - 1) // items_per_page
                
                embed = discord.Embed(
                    title=f"🏪 {category['name']} (Page {page_num}/{total_pages})",
                    description=category['description'],
                    color=0x58a64e
                )
                
                embed.add_field(
                    name="💰 Your Balance",
                    value=f"🪙 **{coins:,}** coins\n💎 **{diamonds:,}** diamonds",
                    inline=False
                )
                
                items_text = ""
                for item_key, item_data in page_items:
                    currency_emoji = "🪙" if item_data["currency"] == "coins" else "💎"
                    items_text += f"{item_data['emoji']} **{item_data['name']}** - {currency_emoji} {item_data['price']:,}\n"
                
                embed.add_field(
                    name="📦 Available Items",
                    value=items_text,
                    inline=False
                )
                
                prefix = self.shop_cog.bot.get_primary_prefix()
                embed.set_footer(text=f"Use {prefix}buy <item> for mints or {prefix}buy <item> <amount> for other items")
                embeds.append(embed)
            
            # Create pagination view for categories with many items
            class CategoryPaginationView(View):
                def __init__(self, embeds, shop_cog, user_id):
                    super().__init__(timeout=300)
                    self.embeds = embeds
                    self.shop_cog = shop_cog
                    self.user_id = user_id
                    self.current_page = 0
                    
                    # Add back button to return to main shop
                    self.add_item(BackToShopButton(shop_cog, user_id))
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple, row=1)
                async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.user_id:
                        return await interaction.response.send_message("❌ Only the original user can navigate!", ephemeral=True)
                    
                    self.current_page = (self.current_page - 1) % len(self.embeds)
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple, row=1)
                async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.user_id:
                        return await interaction.response.send_message("❌ Only the original user can navigate!", ephemeral=True)
                    
                    self.current_page = (self.current_page + 1) % len(self.embeds)
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            
            view = CategoryPaginationView(embeds, self.shop_cog, self.user_id)
            await interaction.response.edit_message(embed=embeds[0], view=view)
        
        else:
            # Single-page view with modern clean styling
            # Build the full description
            description = category['description'] or ""
            
            # Add balance info in description
            balance_text = f"\n**Your Balance:**\n🪙 **{coins:,}** coins | 💎 **{diamonds:,}** diamonds\n"
            
            # Add items or "nothing here yet" message
            if category["items"]:
                items_text = "\n**Available Items:**\n"
                for item_key, item_data in category["items"].items():
                    currency_emoji = "🪙" if item_data["currency"] == "coins" else "💎"
                    items_text += f"{item_data['emoji']} **{item_data['name']}** - {currency_emoji} {item_data['price']:,}\n"
                    items_text += f"└ {item_data['description']}\n\n"
            else:
                items_text = "\n**Available Items:**\nNothing here yet, stay tuned! ✨\n"
            
            # Add usage instructions
            prefix = self.shop_cog.bot.get_primary_prefix()
            usage_text = f"\nUse `{prefix}buy <item> [amount]` to purchase items!"
            
            full_description = description + balance_text + items_text + usage_text
            
            embed = discord.Embed(
                title=f"{category['name']}",
                description=full_description,
                color=0x2b2d31  # Dark theme color
            )
            
            # Create new view with the dropdown and back button
            new_view = ShopCategoryView(self.shop_cog, self.user_id)
            await interaction.response.edit_message(embed=embed, view=new_view)

# New button class for returning to main shop
class BackToShopButton(discord.ui.Button):
    def __init__(self, shop_cog, user_id):
        super().__init__(label="🏪 Back to Shop", style=discord.ButtonStyle.secondary, row=0)
        self.shop_cog = shop_cog
        self.user_id = user_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This shop interface is not for you!", ephemeral=True)
        
        # Return to main shop view
        embed = discord.Embed(
            title="🏪 Pokémon Shop",
            description="Welcome to the Pokémon Shop! Select a category to browse items.",
            color=0x58a64e
        )
        
        # Add user's balance
        coins, diamonds = await self.shop_cog.get_user_balance(self.user_id)
        embed.add_field(
            name="💰 Your Balance",
            value=f"🪙 **{coins:,}** coins\n💎 **{diamonds:,}** diamonds",
            inline=False
        )
        
        # Add category info
        shop_items = self.shop_cog.get_shop_items()
        category_info = ""
        for category_key, category_data in shop_items.items():
            item_count = len(category_data["items"])
            category_info += f"{category_data['name']} - {item_count} items\n"
        
        embed.add_field(
            name="📦 Categories",
            value=category_info,
            inline=False
        )
        
        prefix = self.shop_cog.bot.get_primary_prefix()
        embed.set_footer(text=f"Use the dropdown below to browse categories • {prefix}buy <mint> or {prefix}buy <item> <amount>")
        
        view = ShopView(self.shop_cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

# New view class that includes back button for single-page categories
class ShopCategoryView(View):
    def __init__(self, shop_cog, user_id):
        super().__init__(timeout=300)
        self.shop_cog = shop_cog
        self.user_id = user_id
        
        # Add back button and category dropdown
        self.add_item(BackToShopButton(shop_cog, user_id))
        self.add_item(CategorySelect(shop_cog, user_id))

async def setup(bot):
    collection = bot.pokemon_collection
    user_profiles = bot.db["user_profiles"]
    await bot.add_cog(Shop(bot, collection, user_profiles)) 