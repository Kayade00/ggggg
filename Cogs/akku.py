import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from datetime import datetime
import asyncio
import json

class Shop(commands.Cog):
    def __init__(self, bot, pokemon_collection, user_profiles):
        self.bot = bot
        self.pokemon_collection = pokemon_collection
        self.user_profiles = user_profiles

    async def ensure_user_profile(self, user_id):
        """Ensure user has a profile in the database"""
        try:
            profile = await self.user_profiles.find_one({"user_id": user_id})
            if not profile:
                profile = {
                    "user_id": user_id,
                    "coins": 1000,  # Starting coins
                    "diamonds": 0,
                    "daily_claimed": None,
                    "created_at": datetime.utcnow()
                }
                await self.user_profiles.insert_one(profile)
            return profile
        except Exception as e:
            print(f"Error ensuring user profile: {e}")
            raise

    async def get_user_balance(self, user_id):
        """Get user's coin and diamond balance"""
        try:
            profile = await self.ensure_user_profile(user_id)
            return profile.get("coins", 0), profile.get("diamonds", 0)
        except Exception as e:
            print(f"Error getting user balance: {e}")
            return 0, 0

    async def update_user_balance(self, user_id, coins_change=0, diamonds_change=0):
        """Update user's balance with atomic operations"""
        try:
            await self.ensure_user_profile(user_id)
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {"$inc": {"coins": coins_change, "diamonds": diamonds_change}},
                upsert=True
            )
        except Exception as e:
            print(f"Error updating user balance: {e}")
            raise

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
            return f"(+{increased_stat}, -{decreased_stat})"
        elif increased_stat or decreased_stat:
            return f"({'+' + increased_stat if increased_stat else '-' + decreased_stat})"
        else:
            return "(Neutral)"

    def get_shop_items(self):
        """Define all shop items organized by category"""
        # Load natures for mints
        try:
            with open("data/natures.json", "r", encoding="utf-8") as f:
                nature_data = json.load(f)
                natures = nature_data["natures"]
        except FileNotFoundError:
            # Fallback natures if file not found
            natures = {
                "Hardy": [1, 1, 1, 1, 1, 1], 
                "Adamant": [1, 1.1, 1, 0.9, 1, 1], 
                "Modest": [1, 0.9, 1, 1.1, 1, 1], 
                "Timid": [1, 0.9, 1, 1, 1, 1.1], 
                "Jolly": [1, 1, 1, 0.9, 1, 1.1], 
                "Bold": [1, 0.9, 1.1, 1, 1, 1], 
                "Impish": [1, 1, 1.1, 0.9, 1, 1], 
                "Calm": [1, 0.9, 1, 1, 1.1, 1], 
                "Careful": [1, 1, 1, 0.9, 1.1, 1], 
                "Brave": [1, 1.1, 1, 1, 1, 0.9]
            }
        
        # Create mint items
        mint_items = {}
        for nature, modifiers in natures.items():
            mint_key = f"{nature.lower()}_mint"
            stat_changes = self.get_nature_stat_changes(modifiers)
            mint_items[mint_key] = {
                "name": f"{nature} Mint {stat_changes}",
                "description": f"Changes your Pokémon's nature to {nature}, affecting its stat growth: {stat_changes}",
                "price": 25,  # Increased price for balance
                "currency": "coins",
                "emoji": "🌿",
                "nature": nature,
                "type": "mint"
            }
        
        return {
            "exp_stuff": {
                "name": "🎯 EXP & Level Items",
                "description": "Items to boost your Pokémon's experience and levels!",
                "items": {
                    "rare_candy": {
                        "name": "🍬 Rare Candy",
                        "description": "Instantly levels up your selected Pokémon by 1 level! (Cannot exceed level 100)",
                        "price": 150,  # Increased price for balance
                        "currency": "coins",
                        "emoji": "🍬",
                        "type": "consumable"
                    },
                    "exp_boost": {
                        "name": "⚡ EXP Boost",
                        "description": "Doubles EXP gain for your next 5 battles!",
                        "price": 200,
                        "currency": "coins",
                        "emoji": "⚡",
                        "type": "consumable"
                    }
                }
            },
            "mints": {
                "name": "🌿 Nature Mints",
                "description": "Change your Pokémon's nature with these special mints!",
                "items": mint_items
            },
            "pokeballs": {
                "name": "🔴 Poké Balls",
                "description": "Various types of Poké Balls with different catch rates!",
                "items": {
                    "pokeball": {
                        "name": "🔴 Poké Ball",
                        "description": "Standard Poké Ball with normal catch rate",
                        "price": 50,
                        "currency": "coins",
                        "emoji": "🔴",
                        "type": "consumable",
                        "catch_rate": 1.0
                    },
                    "greatball": {
                        "name": "🔵 Great Ball",
                        "description": "Better than a Poké Ball (1.5× catch rate)",
                        "price": 100,
                        "currency": "coins",
                        "emoji": "🔵",
                        "type": "consumable",
                        "catch_rate": 1.5
                    },
                    "ultraball": {
                        "name": "🟡 Ultra Ball",
                        "description": "Better than a Great Ball (2× catch rate)",
                        "price": 200,
                        "currency": "coins",
                        "emoji": "🟡",
                        "type": "consumable",
                        "catch_rate": 2.0
                    }
                }
            },
            "premium": {
                "name": "💎 Premium Items", 
                "description": "Exclusive items available only for diamonds!",
                "items": {
                    "shiny_charm": {
                        "name": "✨ Shiny Charm",
                        "description": "Permanently increases shiny encounter rate by 50%!",
                        "price": 100,
                        "currency": "diamonds",
                        "emoji": "✨",
                        "type": "permanent"
                    },
                    "master_ball": {
                        "name": "🟣 Master Ball",
                        "description": "Catches any Pokémon without fail! (5× catch rate)",
                        "price": 50,
                        "currency": "diamonds",
                        "emoji": "🟣",
                        "type": "consumable",
                        "catch_rate": 5.0
                    }
                }
            }
        }

    @commands.group(name="shop", aliases=["store"], invoke_without_command=True)
    async def shop(self, ctx):
        """Browse the Pokémon shop"""
        try:
            embed = discord.Embed(
                title="🏪 Pokémon Shop",
                description="Welcome to the Pokémon Shop! Select a category to browse items.",
                color=0x58a64e
            )
            
            # Add user's balance
            coins, diamonds = await self.get_user_balance(ctx.author.id)
            embed.add_field(
                name="💰 Your Balance",
                value=f"🪙 **{coins:,}** coins\n💎 **{diamonds:,}** diamonds",
                inline=False
            )
            
            # Add category info
            shop_items = self.get_shop_items()
            category_info = ""
            for category_key, category_data in shop_items.items():
                item_count = len(category_data["items"])
                category_info += f"• {category_data['emoji']} **{category_data['name']}** - {item_count} items\n"
            
            embed.add_field(
                name="📦 Shop Categories",
                value=category_info,
                inline=False
            )
            
            prefix = ctx.bot.get_primary_prefix()
            embed.set_footer(text=f"Use the dropdown below to browse • {prefix}buy <item> [amount]")
            
            view = ShopView(self, ctx.author.id)
            await ctx.reply(embed=embed, view=view)
        except Exception as e:
            await ctx.reply(f"❌ An error occurred while loading the shop: {e}")

    @commands.command(name="buy", aliases=["purchase"])
    async def buy_item(self, ctx, *, args=None):
        """Buy items from the shop"""
        if not args:
            prefix = ctx.bot.get_primary_prefix()
            examples = (
                f"`{prefix}buy candy 5` - Buy 5 Rare Candies\n"
                f"`{prefix}buy adamant mint` - Buy an Adamant Mint\n"
                f"`{prefix}buy ultraball 10` - Buy 10 Ultra Balls"
            )
            embed = discord.Embed(
                title="🛒 How to Buy Items",
                description=f"Usage: `{prefix}buy <item> [amount]`\n\n**Examples:**\n{examples}",
                color=0xff9900
            )
            return await ctx.reply(embed=embed)
        
        try:
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
            
            # Validate amount
            if amount <= 0:
                return await ctx.reply("❌ Amount must be greater than 0!")
            if amount > 100:  # Prevent excessive purchases
                return await ctx.reply("❌ You can't buy more than 100 items at once!")
            
            # Find the item in shop categories
            shop_items = self.get_shop_items()
            item_data = None
            item_category = None
            
            for category_key, category_data in shop_items.items():
                for item_key, data in category_data["items"].items():
                    # Check if item matches by key or name
                    if (item_name.lower() in [item_key, data["name"].lower()] or 
                        item_name.lower().replace(" ", "_") == item_key):
                        item_data = data
                        item_category = category_key
                        break
                if item_data:
                    break
            
            if not item_data:
                return await ctx.reply(f"❌ Item '{item_name}' not found in shop! Use `{ctx.prefix}shop` to browse available items.")
            
            # Handle different item types
            if item_data.get("type") == "mint":
                await self.buy_mint(ctx, item_data)
            else:
                await self.buy_consumable(ctx, item_data, amount)
                
        except Exception as e:
            await ctx.reply(f"❌ An error occurred while processing your purchase: {e}")

    async def buy_consumable(self, ctx, item_data, amount):
        """Handle consumable item purchase"""
        total_cost = item_data["price"] * amount
        currency = item_data["currency"]
        
        # Check user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        user_balance = coins if currency == "coins" else diamonds
        
        if user_balance < total_cost:
            currency_name = "coins" if currency == "coins" else "diamonds"
            return await ctx.reply(
                f"❌ You don't have enough {currency_name}! "
                f"You need **{total_cost:,}** {currency_name} but only have **{user_balance:,}**."
            )
        
        # Create confirmation embed
        embed = discord.Embed(
            title=f"🛒 Purchase Confirmation",
            description=f"Are you sure you want to buy **{amount}** {item_data['emoji']} **{item_data['name']}**?",
            color=0x58a64e
        )
        
        currency_emoji = "🪙" if currency == "coins" else "💎"
        embed.add_field(
            name="💰 Purchase Details",
            value=f"Item: {item_data['emoji']} {item_data['name']}\n"
                  f"Quantity: {amount}\n"
                  f"Price Each: {currency_emoji} {item_data['price']:,}\n"
                  f"Total Cost: {currency_emoji} {total_cost:,}\n"
                  f"Your Balance: {currency_emoji} {user_balance:,}\n"
                  f"After Purchase: {currency_emoji} {user_balance - total_cost:,}",
            inline=False
        )
        
        embed.add_field(
            name="📝 Description",
            value=item_data["description"],
            inline=False
        )
        
        embed.set_footer(text="You'll receive these items immediately after confirmation")

        class PurchaseView(View):
            def __init__(self, shop_cog, author_id, item_data, amount, total_cost):
                super().__init__(timeout=60)
                self.shop_cog = shop_cog
                self.author_id = author_id
                self.item_data = item_data
                self.amount = amount
                self.total_cost = total_cost
                self.currency = item_data["currency"]
            
            @discord.ui.button(label="✅ Confirm Purchase", style=discord.ButtonStyle.green)
            async def confirm_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can confirm this purchase!", ephemeral=True)
                
                # Double-check balance
                coins, diamonds = await self.shop_cog.get_user_balance(self.author_id)
                user_balance = coins if self.currency == "coins" else diamonds
                
                if user_balance < self.total_cost:
                    currency_name = "coins" if self.currency == "coins" else "diamonds"
                    return await interaction.response.send_message(
                        f"❌ You no longer have enough {currency_name} for this purchase!",
                        ephemeral=True
                    )
                
                # Process purchase
                if self.currency == "coins":
                    await self.shop_cog.update_user_balance(self.author_id, coins_change=-self.total_cost)
                else:
                    await self.shop_cog.update_user_balance(self.author_id, diamonds_change=-self.total_cost)
                
                # TODO: Add items to user's inventory (implementation depends on your system)
                
                # Create success embed
                currency_emoji = "🪙" if self.currency == "coins" else "💎"
                success_embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"You've successfully purchased **{self.amount}** {self.item_data['emoji']} **{self.item_data['name']}**!",
                    color=0x00ff00
                )
                
                success_embed.add_field(
                    name="📦 Items Purchased",
                    value=f"{self.item_data['emoji']} **{self.item_data['name']}** × {self.amount}",
                    inline=True
                )
                
                success_embed.add_field(
                    name="💰 Transaction",
                    value=f"Spent: {currency_emoji} {self.total_cost:,}\n"
                          f"Remaining: {currency_emoji} {user_balance - self.total_cost:,}",
                    inline=True
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def cancel_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can cancel this purchase!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Purchase Cancelled",
                    description="Your purchase has been cancelled.",
                    color=0xff3333
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = PurchaseView(self, ctx.author.id, item_data, amount, total_cost)
        await ctx.reply(embed=embed, view=view)

    async def buy_mint(self, ctx, item_data):
        """Handle mint purchase and application"""
        total_cost = item_data["price"]
        new_nature = item_data["nature"]
        
        # Check user's balance
        coins, diamonds = await self.get_user_balance(ctx.author.id)
        if coins < total_cost:
            return await ctx.reply(
                f"❌ You don't have enough coins! "
                f"You need **{total_cost:,}** coins but only have **{coins:,}**."
            )
        
        # Check if user has a selected Pokémon
        selected_pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "selected": True})
        if not selected_pokemon:
            return await ctx.reply(
                f"❌ You don't have a selected Pokémon! "
                f"Use `{ctx.prefix}select <number>` to select one first."
            )
        
        pokemon_name = selected_pokemon.get('nickname') or selected_pokemon['pokemon_name']
        current_nature = selected_pokemon.get('nature', 'Hardy')
        
        # Check if Pokemon already has this nature
        if current_nature == new_nature:
            return await ctx.reply(
                f"❌ **{pokemon_name}** already has the {new_nature} nature! "
                "No need to use a mint."
            )
        
        # Create confirmation embed
        embed = discord.Embed(
            title=f"🌿 Nature Mint Confirmation",
            description=f"Are you sure you want to change **{pokemon_name}**'s nature from **{current_nature}** to **{new_nature}**?",
            color=0x58a64e
        )
        
        embed.add_field(
            name="💰 Purchase Details",
            value=f"Item: {item_data['emoji']} {item_data['name']}\n"
                  f"Price: 🪙 {total_cost:,}\n"
                  f"Your Balance: 🪙 {coins:,}\n"
                  f"After Purchase: 🪙 {coins - total_cost:,}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Stat Changes",
            value=item_data["description"].split(": ")[-1],
            inline=True
        )
        
        embed.set_footer(text="This change will be applied immediately after confirmation")

        class MintPurchaseView(View):
            def __init__(self, shop_cog, author_id, pokemon_data, item_data, total_cost):
                super().__init__(timeout=60)
                self.shop_cog = shop_cog
                self.author_id = author_id
                self.pokemon = pokemon_data
                self.item_data = item_data
                self.cost = total_cost
                self.new_nature = item_data["nature"]
            
            @discord.ui.button(label="✅ Confirm Purchase", style=discord.ButtonStyle.green)
            async def confirm_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can confirm this purchase!", ephemeral=True)
                
                # Double-check balance
                current_coins, _ = await self.shop_cog.get_user_balance(self.author_id)
                if current_coins < self.cost:
                    return await interaction.response.send_message("❌ You no longer have enough coins for this purchase!", ephemeral=True)
                
                # Double-check nature (in case changed elsewhere)
                current_pokemon = await self.shop_cog.pokemon_collection.find_one({"_id": self.pokemon["_id"]})
                if current_pokemon.get('nature', 'Hardy') == self.new_nature:
                    return await interaction.response.send_message("❌ This Pokémon already has this nature!", ephemeral=True)
                
                # Process purchase
                await self.shop_cog.update_user_balance(self.author_id, coins_change=-self.cost)
                
                # Update Pokémon's nature
                await self.shop_cog.pokemon_collection.update_one(
                    {"_id": self.pokemon["_id"]},
                    {"$set": {"nature": self.new_nature}}
                )
                
                # Create success embed
                pokemon_name = self.pokemon.get('nickname') or self.pokemon['pokemon_name']
                
                success_embed = discord.Embed(
                    title="✅ Nature Changed!",
                    description=f"**{pokemon_name}**'s nature has been changed from **{current_pokemon.get('nature', 'Hardy')}** to **{self.new_nature}**!",
                    color=0x00ff00
                )
                
                success_embed.add_field(
                    name="📦 Item Used",
                    value=f"{self.item_data['emoji']} **{self.item_data['name']}**",
                    inline=True
                )
                
                success_embed.add_field(
                    name="💰 Transaction",
                    value=f"Spent: 🪙 {self.cost:,}\n"
                          f"Remaining: 🪙 {current_coins - self.cost:,}",
                    inline=True
                )
                
                success_embed.add_field(
                    name="📊 New Nature Effects",
                    value=self.item_data["description"].split(": ")[-1],
                    inline=False
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def cancel_purchase(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != self.author_id:
                    return await interaction.response.send_message("❌ Only the buyer can cancel this purchase!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Purchase Cancelled",
                    description="Your mint purchase has been cancelled.",
                    color=0xff3333
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = MintPurchaseView(self, ctx.author.id, selected_pokemon, item_data, total_cost)
        await ctx.reply(embed=embed, view=view)

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
                label=category_data["name"].split(" ")[-1] + " Items",
                description=f"{category_data['description']} ({item_count} items)",
                value=category_key,
                emoji=category_data["name"][:1]  # Use the first emoji
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
        
        # Create paginated view for categories with items
        if category["items"]:
            items_list = list(category["items"].items())
            items_per_page = 5
            total_pages = (len(items_list) + items_per_page - 1) // items_per_page
            
            # Create first page embed
            embed = self.create_category_embed(
                category, 
                coins, 
                diamonds, 
                items_list[:items_per_page], 
                1, 
                total_pages
            )
            
            # Create pagination view
            view = CategoryPaginationView(
                self.shop_cog,
                self.user_id,
                category,
                items_list,
                items_per_page,
                1  # Start at page 1
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Empty category
            embed = self.create_category_embed(category, coins, diamonds, [], 1, 1)
            view = ShopCategoryView(self.shop_cog, self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)
    
    def create_category_embed(self, category, coins, diamonds, items, current_page, total_pages):
        """Helper to create category embed with pagination"""
        embed = discord.Embed(
            title=f"🏪 {category['name']}",
            description=category['description'],
            color=0x58a64e
        )
        
        # Add page info if paginated
        if total_pages > 1:
            embed.title += f" (Page {current_page}/{total_pages})"
        
        # Add user balance
        embed.add_field(
            name="💰 Your Balance",
            value=f"🪙 **{coins:,}** coins\n💎 **{diamonds:,}** diamonds",
            inline=False
        )
        
        # Add items or empty message
        if items:
            items_text = ""
            for item_key, item_data in items:
                currency_emoji = "🪙" if item_data["currency"] == "coins" else "💎"
                items_text += (
                    f"{item_data['emoji']} **{item_data['name']}** - {currency_emoji} {item_data['price']:,}\n"
                    f"└ {item_data['description']}\n\n"
                )
            
            embed.add_field(
                name="📦 Available Items",
                value=items_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📦 Available Items",
                value="✨ Nothing here yet! Check back later for new items.",
                inline=False
            )
        
        prefix = self.shop_cog.bot.get_primary_prefix()
        embed.set_footer(text=f"Use {prefix}buy <item> [amount] to purchase items")
        
        return embed

class CategoryPaginationView(View):
    def __init__(self, shop_cog, user_id, category, items_list, items_per_page, current_page):
        super().__init__(timeout=300)
        self.shop_cog = shop_cog
        self.user_id = user_id
        self.category = category
        self.items_list = items_list
        self.items_per_page = items_per_page
        self.current_page = current_page
        self.total_pages = (len(items_list) + items_per_page - 1) // items_per_page
        
        # Add navigation buttons
        self.add_item(BackToShopButton(shop_cog, user_id))
        
        # Disable previous button if on first page
        if self.current_page == 1:
            self.children[1].disabled = True
        
        # Disable next button if on last page
        if self.current_page == self.total_pages:
            self.children[2].disabled = True
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple, row=1)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Only the original user can navigate!", ephemeral=True)
        
        self.current_page -= 1
        await self.update_page(interaction)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Only the original user can navigate!", ephemeral=True)
        
        self.current_page += 1
        await self.update_page(interaction)
    
    async def update_page(self, interaction: discord.Interaction):
        """Update the message with the new page"""
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.items_list[start_idx:end_idx]
        
        # Get user balance for the embed
        coins, diamonds = await self.shop_cog.get_user_balance(self.user_id)
        
        # Create new embed
        embed = CategorySelect.create_category_embed(
            self,
            self.category,
            coins,
            diamonds,
            page_items,
            self.current_page,
            self.total_pages
        )
        
        # Update button states
        for child in self.children:
            if child.label == "◀ Previous":
                child.disabled = (self.current_page == 1)
            elif child.label == "Next ▶":
                child.disabled = (self.current_page == self.total_pages)
        
        await interaction.response.edit_message(embed=embed, view=self)

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
            category_info += f"• {category_data['emoji']} **{category_data['name']}** - {item_count} items\n"
        
        embed.add_field(
            name="📦 Shop Categories",
            value=category_info,
            inline=False
        )
        
        prefix = self.shop_cog.bot.get_primary_prefix()
        embed.set_footer(text=f"Use the dropdown below to browse • {prefix}buy <item> [amount]")
        
        view = ShopView(self.shop_cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

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