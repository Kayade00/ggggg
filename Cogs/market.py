import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from datetime import datetime, timedelta
import os
import sys
import json
from theme_loader import theme

# Add the parent directory to sys.path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokemon_filters import parse_command_with_filters, filter_pokemon_list, get_filter_help, PokemonFilter

class Market(commands.Cog):
    def __init__(self, bot, pokemon_collection, user_profiles, market_collection):
        self.bot = bot
        self.pokemon_collection = pokemon_collection
        self.user_profiles = user_profiles
        self.market_collection = market_collection
        self.filter_system = PokemonFilter()

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

    async def get_next_listing_id(self):
        """Get the next available listing ID"""
        # Find the highest listing ID
        highest_listing = await self.market_collection.find_one(
            {},
            sort=[("listing_id", -1)]
        )
        return 1 if not highest_listing else highest_listing["listing_id"] + 1

    async def reindex_market_listings(self):
        """Reindex all market listings to remove gaps in numbering"""
        # Get all listings sorted by listing_id
        all_listings = await self.market_collection.find({}).sort("listing_id", 1).to_list(length=None)
        
        # Update each listing with new sequential ID
        for index, listing in enumerate(all_listings, 1):
            if listing["listing_id"] != index:
                await self.market_collection.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"listing_id": index}}
                )

    def format_market_listing(self, listing, include_seller=True):
        """Format a market listing for display"""
        pokemon = listing['pokemon']
        name = pokemon.get('nickname') or pokemon['pokemon_name']
        level = pokemon['level']
        price = listing['price']
        
        # Calculate IV percentage
        total_iv = sum([pokemon.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
        total_iv_percent = round((total_iv / 186) * 100, 1)
        
        status_icons = ""
        if pokemon.get("favorite", False):
            status_icons += theme.emoji('ui', 'heart')
        if pokemon.get("shiny", False):
            status_icons += theme.emoji('ui', 'shiny')
        
        line = f"`{listing['listing_id']:>3}.` {status_icons} **{name}** • Lv. {level} • {total_iv_percent}% • **{price:,}** {theme.emoji('currency', 'coins')}"
        
        if include_seller:
            seller_name = listing.get('seller_name', 'Unknown')
            line += f" • *{seller_name}*"
        
        return line

    def format_pokemon_info(self, pokemon, listing_id=None, price=None, seller_name=None):
        """Format detailed Pokemon info for market info command - matches b!info format"""
        
        # Load Pokemon base data for stat calculation
        try:
            with open('pokedex.json', 'r', encoding='utf-8') as f:
                POKEMON_DATA = json.load(f)
        except:
            POKEMON_DATA = {}
        
        poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == pokemon["pokemon_name"].lower()), None)
        
        # Handle both old and new IV field names like b!info does
        hp_iv = pokemon.get('hpiv', pokemon.get('hp_iv', 0))
        atk_iv = pokemon.get('atkiv', pokemon.get('atk_iv', 0))
        def_iv = pokemon.get('defiv', pokemon.get('def_iv', 0))
        spatk_iv = pokemon.get('spatkiv', pokemon.get('sp_atk_iv', 0))
        spdef_iv = pokemon.get('spdefiv', pokemon.get('sp_def_iv', 0))
        spd_iv = pokemon.get('spdiv', pokemon.get('spd_iv', 0))
        
        total_iv = hp_iv + atk_iv + def_iv + spatk_iv + spdef_iv + spd_iv
        total_iv_percent = round((total_iv / 186) * 100, 2)

        # Calculate actual stats if we have base data
        stat_text = ""
        if poke_data:
            stats = poke_data["stats"]
            nature_name = pokemon.get('nature', 'Hardy')
            level = pokemon['level']
            
            # Calculate stats using the same formula as b!info
            calculated_hp = self.calculate_stat(hp_iv, level, stats['hp'], 0, nature_name, 0, is_hp=True)
            calculated_attack = self.calculate_stat(atk_iv, level, stats['attack'], 0, nature_name, 1)
            calculated_defense = self.calculate_stat(def_iv, level, stats['defense'], 0, nature_name, 2)
            calculated_sp_atk = self.calculate_stat(spatk_iv, level, stats['special-attack'], 0, nature_name, 3)
            calculated_sp_def = self.calculate_stat(spdef_iv, level, stats['special-defense'], 0, nature_name, 4)
            calculated_speed = self.calculate_stat(spd_iv, level, stats['speed'], 0, nature_name, 5)

            stat_text = "\n".join([
                f"HP: {calculated_hp} – IV: {hp_iv}/31",
                f"Attack: {calculated_attack} – IV: {atk_iv}/31",
                f"Defense: {calculated_defense} – IV: {def_iv}/31",
                f"Sp. Atk: {calculated_sp_atk} – IV: {spatk_iv}/31",
                f"Sp. Def: {calculated_sp_def} – IV: {spdef_iv}/31",
                f"Speed: {calculated_speed} – IV: {spd_iv}/31",
            ])
        else:
            # Fallback if no base data
            stat_text = "\n".join([
                f"HP: ??? – IV: {hp_iv}/31",
                f"Attack: ??? – IV: {atk_iv}/31",
                f"Defense: ??? – IV: {def_iv}/31",
                f"Sp. Atk: ??? – IV: {spatk_iv}/31",
                f"Sp. Def: ??? – IV: {spdef_iv}/31",
                f"Speed: ??? – IV: {spd_iv}/31",
            ])

        # Calculate XP needed for next level
        xp_needed = self.calculate_xp_for_level(pokemon["level"] + 1)
        
        # Create embed exactly like b!info format
        embed = discord.Embed(
            title=f"{pokemon.get('nickname') or pokemon['pokemon_name']} (#{listing_id or 'Market'})",
            description=(
                f"**Level**: {pokemon['level']}\n"
                f"**XP**: {pokemon.get('xp', 0)} / {xp_needed}\n"
                f"**Nature**: {pokemon.get('nature', 'Unknown')}\n"
                f"**Held Item**: {pokemon.get('held_item') or 'None'}\n"
                f"**Total IV**: {total_iv_percent}%\n"
                f"**Friendship**: {pokemon.get('friendship', 0)}/255\n"
                f"**💰 Price**: {price:,} coins\n"
                f"**👤 Seller**: {seller_name}"
            ),
            color=discord.Color.gold()
        )

        # Moves field exactly like b!info
        embed.add_field(name="Moves", value="\n".join([
            pokemon.get("move1", "None"),
            pokemon.get("move2", "None"),
            pokemon.get("move3", "None"),
            pokemon.get("move4", "None")
        ]), inline=False)

        # Stats field exactly like b!info
        embed.add_field(name="Stats", value=stat_text, inline=False)
        
        # Footer like b!info but market-specific
        embed.set_footer(text=f"Shiny: {pokemon.get('shiny', False)} | Favorite: {pokemon.get('favorite', False)} | Listed by: {seller_name}")

        return embed

    def calculate_stat(self, iv, level, base_stat, ev, nature_name, stat_index, is_hp=False):
        """Calculate actual stat like b!info does"""
        if is_hp:
            return ((2 * base_stat + iv + (ev // 4)) * level // 100) + level + 10
        else:
            base_calc = ((2 * base_stat + iv + (ev // 4)) * level // 100) + 5
            # Apply nature modifier if needed (simplified)
            return base_calc

    def calculate_xp_for_level(self, level):
        """Calculate XP needed for a level"""
        if level <= 1:
            return 0
        return int((4 * (level ** 3)) / 5)

    @commands.group(name="market", aliases=["m"], invoke_without_command=True)
    async def market(self, ctx):
        """Pokemon Market - Buy and sell Pokemon"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🏪 Pokemon Market",
                description="Welcome to the Pokemon Market! Buy and sell Pokemon with other trainers.",
                color=0x58a64e
            )
            prefix = ctx.bot.get_primary_prefix()
            embed.add_field(
                name="📋 **Commands**",
                value=f"`{prefix}market search` or `{prefix}m s` - Browse market listings\n"
                      f"`{prefix}market info <listing_id>` or `{prefix}m i` - View detailed Pokemon info\n"
                      f"`{prefix}market add <number> <price>` or `{prefix}m a` - List Pokemon for sale\n"
                      f"`{prefix}market remove <listing_id>` or `{prefix}m r` - Remove your listing\n"
                      f"`{prefix}market list` or `{prefix}m l` - View your active listings\n"
                      f"`{prefix}market buy <listing_id>` or `{prefix}m b` - Buy a Pokemon\n"
                      f"`{prefix}market filters` - Show available filters",
                inline=False
            )
            embed.add_field(
                name="🔍 **Filter Examples**",
                value=f"`{prefix}m s --n pikachu --shiny` - Search for shiny Pikachu\n"
                      f"`{prefix}m s --price < 50000 --level > 80` - Cheap high-level Pokemon\n"
                      f"`{prefix}m s --evo eevee --spdiv > 25` - Eevee line with good speed",
                inline=False
            )
            await ctx.reply(embed=embed)

    @market.command(name="info", aliases=["i"])
    async def market_info(self, ctx, listing_id = None):
        """View detailed information about a market listing"""
        if listing_id is None:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}market info <listing_id>`\nUse `{prefix}market search` to find listing IDs.")
        
        try:
            listing_id = int(listing_id)
        except ValueError:
            return await ctx.reply("❌ Please provide a valid listing ID!")
        
        # Find the listing
        listing = await self.market_collection.find_one({"listing_id": listing_id})
        
        if not listing:
            return await ctx.reply("❌ That listing doesn't exist!")
        
        pokemon = listing['pokemon']
        embed = self.format_pokemon_info(
            pokemon, 
            listing_id=listing['listing_id'],
            price=listing['price'],
            seller_name=listing['seller_name']
        )
        
        # Add Pokemon sprite like b!info does
        if pokemon.get('pokemon_name'):
            try:
                with open('pokedex.json', 'r', encoding='utf-8') as f:
                    POKEMON_DATA = json.load(f)
                
                poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == pokemon["pokemon_name"].lower()), None)
                if poke_data and 'id' in poke_data:
                    # Check if Pokemon is shiny and use appropriate sprite folder
                    if pokemon.get("shiny", False):
                        image_path = f"full_shiny/{poke_data['id']}_full.png"
                    else:
                        image_path = f"full/{poke_data['id']}.png"
                        
                    if os.path.exists(image_path):
                        file = discord.File(image_path, filename="pokemon.png")
                        embed.set_image(url="attachment://pokemon.png")
                        prefix = ctx.bot.get_primary_prefix()
                        embed.set_footer(text=f"Use {prefix}market buy {listing_id} to purchase this Pokemon!")
                        return await ctx.reply(embed=embed, file=file)
            except:
                pass
        
        # Fallback without image
        prefix = ctx.bot.get_primary_prefix()
        embed.set_footer(text=f"Use {prefix}market buy {listing_id} to purchase this Pokemon!")
        await ctx.reply(embed=embed)

    @market.command(name="search", aliases=["s"])
    async def market_search(self, ctx, *args):
        """Search market listings with filters"""
        try:
            # Parse filters from arguments
            filters, remaining_args = parse_command_with_filters(list(args), market_mode=True)
            
            # Get all market listings
            all_listings = await self.market_collection.find({}).to_list(length=None)
            
            if not all_listings:
                prefix = ctx.bot.get_primary_prefix()
                return await ctx.reply(f"🏪 The market is empty! Be the first to list a Pokemon with `{prefix}market add`.")
            
            # Create a list of Pokemon from listings for filtering
            pokemon_for_filtering = []
            for listing in all_listings:
                pokemon = listing['pokemon'].copy()
                pokemon['price'] = listing['price']  # Add price for filtering
                pokemon['listing_id'] = listing['listing_id']
                pokemon['seller_id'] = listing['seller_id']
                pokemon['seller_name'] = listing['seller_name']
                pokemon_for_filtering.append(pokemon)
            
            # Apply filters
            filtered_pokemon = filter_pokemon_list(pokemon_for_filtering, filters)
            
            if not filtered_pokemon:
                filter_desc = self.filter_system.get_filter_description(filters, market_mode=True)
                return await ctx.reply(f"🔍 No Pokemon found matching your filters.\n**Filters:** {filter_desc}")
            
            # Recreate listings from filtered Pokemon
            filtered_listings = []
            for pokemon in filtered_pokemon:
                original_listing = next((l for l in all_listings if l['listing_id'] == pokemon['listing_id']), None)
                if original_listing:
                    filtered_listings.append(original_listing)
            
            # Sort by price (cheapest first)
            filtered_listings.sort(key=lambda x: x['price'])
            
            # Create paginated embeds (15 per page)
            listings_per_page = 15
            total_pages = (len(filtered_listings) + listings_per_page - 1) // listings_per_page
            
            embeds = []
            for page in range(total_pages):
                start_idx = page * listings_per_page
                end_idx = min(start_idx + listings_per_page, len(filtered_listings))
                page_listings = filtered_listings[start_idx:end_idx]
                
                embed = discord.Embed(
                    title="🏪 Market Search Results",
                    description="\n".join([self.format_market_listing(listing) for listing in page_listings]),
                    color=0x58a64e
                )
                
                if filters:
                    filter_desc = self.filter_system.get_filter_description(filters, market_mode=True)
                    embed.add_field(name="🔍 Active Filters", value=filter_desc, inline=False)
                
                prefix = ctx.bot.get_primary_prefix()
                embed.set_footer(text=f"Page {page + 1}/{total_pages} • {len(filtered_listings)} listings • Use {prefix}market buy <id> to purchase")
                embeds.append(embed)
            
            if len(embeds) == 1:
                await ctx.reply(embed=embeds[0])
            else:
                # Use pagination view
                class MarketPaginationView(View):
                    def __init__(self, embeds, author):
                        super().__init__(timeout=300)
                        self.embeds = embeds
                        self.current_page = 0
                        self.author = author

                    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
                    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id != self.author.id:
                            return await interaction.response.send_message("❌ Only the command user can navigate pages!", ephemeral=True)
                        
                        self.current_page = (self.current_page - 1) % len(self.embeds)
                        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

                    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
                    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id != self.author.id:
                            return await interaction.response.send_message("❌ Only the command user can navigate pages!", ephemeral=True)
                        
                        self.current_page = (self.current_page + 1) % len(self.embeds)
                        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

                view = MarketPaginationView(embeds, ctx.author)
                await ctx.reply(embed=embeds[0], view=view)
            
        except Exception as e:
            await ctx.reply("❌ Something went wrong with the market search. Please try again later.")

    @market.command(name="add", aliases=["a"])
    async def market_add(self, ctx, number = None, price = None):
        """Add a Pokemon to the market"""
        if number is None or price is None:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}market add <pokemon_number> <price>`\nExample: `{prefix}market add 5 25000`")
        
        try:
            number = int(number)
            price = int(price)
        except ValueError:
            return await ctx.reply("❌ Please provide valid numbers for Pokemon number and price!")
        
        if price <= 0:
            return await ctx.reply("❌ Price must be greater than 0!")
        
        if price > 999999999:
            return await ctx.reply("❌ Price cannot exceed 999,999,999 coins!")
        
        # Find the Pokemon
        pokemon = await self.pokemon_collection.find_one({"user_id": ctx.author.id, "pokemon_number": number})
        
        if not pokemon:
            return await ctx.reply("❌ You don't have a Pokemon with that number!")
        
        # Check if Pokemon is already on market
        existing_listing = await self.market_collection.find_one({
            "seller_id": ctx.author.id,
            "pokemon.pokemon_number": number
        })
        
        if existing_listing:
            return await ctx.reply("❌ This Pokemon is already listed on the market!")
        
        # Check if user has more than one Pokemon (can't list their only Pokemon)
        user_pokemon_count = await self.pokemon_collection.count_documents({"user_id": ctx.author.id})
        if user_pokemon_count <= 1:
            return await ctx.reply("❌ You cannot list your only Pokémon! You must always have at least one Pokémon in your collection.")
        
        # Create confirmation embed
        pokemon_name = pokemon.get('nickname') or pokemon['pokemon_name']
        total_iv = sum([pokemon.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
        total_iv_percent = round((total_iv / 186) * 100, 1)
        
        embed = discord.Embed(
            title="🏪 Confirm Market Listing",
            description=f"Are you sure you want to list **{pokemon_name}** for **{price:,}** coins?",
            color=0x58a64e
        )
        embed.add_field(
            name="Pokemon Details",
            value=f"Level: {pokemon['level']}\n"
                  f"Nature: {pokemon['nature']}\n"
                  f"Total IV: {total_iv_percent}%\n"
                  f"Friendship: {pokemon.get('friendship', 0)}/255",
            inline=True
        )
        embed.add_field(
            name="Listing Details",
            value=f"Price: {price:,} coins\n"
                  f"Market Fee: 0 coins\n"
                  f"You'll receive: {price:,} coins",
            inline=True
        )
        embed.set_footer(text="⚠️ Once listed, other players can buy this Pokemon!")
        
        class ConfirmView(View):
            def __init__(self, pokemon_data, listing_price, market_cog, pokemon_collection):
                super().__init__(timeout=60)
                self.pokemon = pokemon_data
                self.price = listing_price
                self.confirmed = False
                self.market_cog = market_cog
                self.pokemon_collection = pokemon_collection
            
            @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.green)
            async def confirm(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ Only the listing owner can confirm!", ephemeral=True)
                
                # Generate next listing ID
                listing_id = await self.market_cog.get_next_listing_id()
                
                # Create market listing
                listing = {
                    "listing_id": listing_id,
                    "seller_id": ctx.author.id,
                    "seller_name": ctx.author.display_name,
                    "pokemon": self.pokemon,
                    "price": self.price,
                    "listed_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(days=30)  # 30 day expiration
                }
                
                await self.market_cog.market_collection.insert_one(listing)
                
                # Remove Pokemon from user's collection
                await self.pokemon_collection.delete_one({"_id": self.pokemon["_id"]})
                
                success_embed = discord.Embed(
                    title="✅ Pokemon Listed Successfully!",
                    description=f"**{pokemon_name}** has been listed for **{self.price:,}** coins!\n"
                               f"Listing ID: **{listing_id}**",
                    color=0x00ff00
                )
                success_embed.set_footer(text="Other players can now buy your Pokemon! Use !market list to view your listings.")
                
                await interaction.response.edit_message(embed=success_embed, view=None)
                self.confirmed = True
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ Only the listing owner can cancel!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Listing Cancelled",
                    description="Your Pokemon was not listed on the market.",
                    color=0xff0000
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = ConfirmView(pokemon, price, self, self.pokemon_collection)
        await ctx.reply(embed=embed, view=view)

    @market.command(name="remove", aliases=["r"])
    async def market_remove(self, ctx, listing_id = None):
        """Remove your Pokemon from the market"""
        if listing_id is None:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}market remove <listing_id>`\nUse `{prefix}market list` to see your listings.")
        
        try:
            listing_id = int(listing_id)
        except ValueError:
            return await ctx.reply("❌ Please provide a valid listing ID!")
        
        # Find the listing
        listing = await self.market_collection.find_one({
            "listing_id": listing_id,
            "seller_id": ctx.author.id
        })
        
        if not listing:
            return await ctx.reply("❌ You don't have a listing with that ID!")
        
        # Return Pokemon to user's collection
        pokemon = listing['pokemon']
        
        # Find the highest pokemon_number for this user and increment
        last_pokemon = await self.pokemon_collection.find_one(
            {"user_id": ctx.author.id},
            sort=[("pokemon_number", -1)]
        )
        
        next_number = 1 if not last_pokemon else last_pokemon["pokemon_number"] + 1
        pokemon["pokemon_number"] = next_number
        
        await self.pokemon_collection.insert_one(pokemon)
        
        # Remove from market
        await self.market_collection.delete_one({"listing_id": listing_id})
        
        pokemon_name = pokemon.get('nickname') or pokemon['pokemon_name']
        embed = discord.Embed(
            title="✅ Listing Removed",
            description=f"**{pokemon_name}** has been removed from the market and returned to your collection!\n"
                       f"New Pokemon number: **{next_number}**",
            color=0x00ff00
        )
        await ctx.reply(embed=embed)

    @market.command(name="list", aliases=["l"])
    async def market_list(self, ctx):
        """View your active market listings"""
        listings = await self.market_collection.find({"seller_id": ctx.author.id}).to_list(length=None)
        
        if not listings:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"📋 You don't have any active market listings!\nUse `{prefix}market add <number> <price>` to list a Pokemon.")
        
        embed = discord.Embed(
            title=f"📋 {ctx.author.display_name}'s Market Listings",
            description="\n".join([self.format_market_listing(listing, include_seller=False) for listing in listings]),
            color=0x58a64e
        )
        prefix = ctx.bot.get_primary_prefix()
        embed.set_footer(text=f"Total listings: {len(listings)} • Use {prefix}market remove <id> to remove a listing")
        await ctx.reply(embed=embed)

    @market.command(name="buy", aliases=["b"])
    async def market_buy(self, ctx, listing_id = None):
        """Buy a Pokemon from the market"""
        if listing_id is None:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ Usage: `{prefix}market buy <listing_id>`\nUse `{prefix}market search` to find Pokemon to buy.")
        
        try:
            listing_id = int(listing_id)
        except ValueError:
            return await ctx.reply("❌ Please provide a valid listing ID!")
        
        # Find the listing
        listing = await self.market_collection.find_one({"listing_id": listing_id})
        
        if not listing:
            return await ctx.reply("❌ That listing doesn't exist or has already been sold!")
        
        if listing['seller_id'] == ctx.author.id:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You can't buy your own Pokemon! Use `{prefix}market remove` to remove it instead.")
        
        # Check buyer's balance
        buyer_coins, _ = await self.get_user_balance(ctx.author.id)
        price = listing['price']
        
        if buyer_coins < price:
            return await ctx.reply(f"❌ You don't have enough coins! You need **{price:,}** coins but only have **{buyer_coins:,}**.")
        
        # Create confirmation embed
        pokemon = listing['pokemon']
        pokemon_name = pokemon.get('nickname') or pokemon['pokemon_name']
        total_iv = sum([pokemon.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
        total_iv_percent = round((total_iv / 186) * 100, 1)
        
        embed = discord.Embed(
            title="💰 Confirm Purchase",
            description=f"Are you sure you want to buy **{pokemon_name}** for **{price:,}** coins?",
            color=0x58a64e
        )
        embed.add_field(
            name="Pokemon Details",
            value=f"Level: {pokemon['level']}\n"
                  f"Nature: {pokemon['nature']}\n"
                  f"Total IV: {total_iv_percent}%\n"
                  f"Friendship: {pokemon.get('friendship', 0)}/255",
            inline=True
        )
        embed.add_field(
            name="Purchase Details",
            value=f"Price: {price:,} coins\n"
                  f"Your balance: {buyer_coins:,} coins\n"
                  f"After purchase: {buyer_coins - price:,} coins",
            inline=True
        )
        embed.set_footer(text=f"Seller: {listing['seller_name']}")
        
        class PurchaseView(View):
            def __init__(self, listing_data, market_cog, pokemon_collection):
                super().__init__(timeout=60)
                self.listing = listing_data
                self.market_cog = market_cog
                self.pokemon_collection = pokemon_collection
            
            @discord.ui.button(label="💰 Buy Now", style=discord.ButtonStyle.green)
            async def buy(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ Only the buyer can confirm!", ephemeral=True)
                
                # Double-check the listing still exists
                current_listing = await self.market_cog.market_collection.find_one({"listing_id": listing_id})
                if not current_listing:
                    return await interaction.response.edit_message(
                        content="❌ This Pokemon has already been sold!",
                        embed=None, view=None
                    )
                
                # Process the transaction
                pokemon = self.listing['pokemon']
                
                # Find the next pokemon number for buyer
                last_pokemon = await self.pokemon_collection.find_one(
                    {"user_id": ctx.author.id},
                    sort=[("pokemon_number", -1)]
                )
                
                next_number = 1 if not last_pokemon else last_pokemon["pokemon_number"] + 1
                
                # Update pokemon data for new owner
                pokemon["user_id"] = ctx.author.id
                pokemon["pokemon_number"] = next_number
                pokemon["selected"] = False
                pokemon["purchased_at"] = datetime.utcnow()
                
                # Add to buyer's collection
                await self.pokemon_collection.insert_one(pokemon)
                
                # Transfer coins
                await self.market_cog.update_user_balance(ctx.author.id, coins_change=-price)
                await self.market_cog.update_user_balance(self.listing['seller_id'], coins_change=price)
                
                # Remove from market
                await self.market_cog.market_collection.delete_one({"listing_id": listing_id})
                
                # Reindex market listings to remove gaps
                await self.market_cog.reindex_market_listings()
                
                pokemon_name = pokemon.get('nickname') or pokemon['pokemon_name']
                success_embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"You've successfully bought **{pokemon_name}** for **{price:,}** coins!\n"
                               f"Pokemon number: **{next_number}**",
                    color=0x00ff00
                )
                success_embed.set_footer(text="The seller has received the coins. Enjoy your new Pokemon!")
                
                await interaction.response.edit_message(embed=success_embed, view=None)
                
                # Notify seller if they're online (optional)
                try:
                    seller = self.market_cog.bot.get_user(self.listing['seller_id'])
                    if seller:
                        seller_embed = discord.Embed(
                            title="💰 Pokemon Sold!",
                            description=f"Your **{pokemon_name}** was sold for **{price:,}** coins!\n"
                                       f"Buyer: {ctx.author.display_name}",
                            color=0x00ff00
                        )
                        await seller.send(embed=seller_embed)
                except:
                    pass  # Don't fail if we can't notify seller
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ Only the buyer can cancel!", ephemeral=True)
                
                cancel_embed = discord.Embed(
                    title="❌ Purchase Cancelled",
                    description="The purchase was cancelled.",
                    color=0xff0000
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = PurchaseView(listing, self, self.pokemon_collection)
        await ctx.reply(embed=embed, view=view)

    @market.command(name="filters")
    async def market_filters(self, ctx):
        """Show available market filters"""
        embed = discord.Embed(
            title="🔍 Market Filters",
            description=get_filter_help(),
            color=0x58a64e
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    pokemon_db = bot.pokemon_collection
    user_profiles_db = bot.db["user_profiles"]
    market_db = bot.db["market_listings"]
    await bot.add_cog(Market(bot, pokemon_db, user_profiles_db, market_db))
