import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import json

# Store active trade sessions
active_trades = {}

def calculate_iv_percentage(pokemon):
    """Calculate IV percentage for a Pokemon"""
    total_iv = sum([pokemon.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
    return round((total_iv / 186) * 100, 1)

class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command
    @app_commands.command(name="trade", description="Trade Pokemon with other players")
    @app_commands.describe(user="The user you want to trade with")
    async def trade_slash(self, interaction: discord.Interaction, user: discord.Member):
        # Check if user exists in database
        db_user = await self.bot.pokemon_collection.find_one({"user_id": interaction.user.id})
        if not db_user:
            return await interaction.response.send_message("❌ You need to start your Pokemon journey first! Use `/start`", ephemeral=True)
        
        await interaction.response.defer()
        await self.handle_trade_request(interaction, db_user, user)

    # Prefix command
    @commands.command(name="trade", aliases=["t"])
    async def trade_prefix(self, ctx, user: Optional[discord.Member] = None):
        if not user:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ **Usage:** `{prefix}trade @user` - Send trade request")
        
        # Check if user exists in database
        db_user = await self.bot.pokemon_collection.find_one({"user_id": ctx.author.id})
        if not db_user:
            prefix = ctx.bot.get_primary_prefix()
            return await ctx.reply(f"❌ You need to start your Pokemon journey first! Use `{prefix}start`")
        
        await self.handle_trade_request(ctx, db_user, user)

    async def handle_trade_request(self, ctx_or_interaction, db_user, target_user):
        # Get the appropriate objects based on whether it's slash or prefix
        if isinstance(ctx_or_interaction, discord.Interaction):
            author = ctx_or_interaction.user
            channel = ctx_or_interaction.channel
            followup_func = ctx_or_interaction.followup.send
            edit_func = ctx_or_interaction.edit_original_response
        else:
            author = ctx_or_interaction.author
            channel = ctx_or_interaction.channel
            followup_func = ctx_or_interaction.reply
            edit_func = None

        # Basic validation
        if target_user.id == author.id:
            return await followup_func("❌ You can't trade with yourself!")
        
        if target_user.bot:
            return await followup_func("❌ You can't trade with bots!")

        # Check if either user is already in a trade
        existing_trade = None
        for trade in active_trades.values():
            if (trade["user1"]["id"] == author.id or 
                trade["user2"]["id"] == author.id or
                trade["user1"]["id"] == target_user.id or 
                trade["user2"]["id"] == target_user.id):
                existing_trade = trade
                break

        if existing_trade:
            return await followup_func("❌ One of you is already in an active trade!")

        # Check if target user exists in database
        db_target_user = await self.bot.pokemon_collection.find_one({"user_id": target_user.id})
        if not db_target_user:
            return await followup_func(f"❌ {target_user.mention} hasn't started their Pokemon journey yet! They need to use `/start` first.")

        # Create trade request
        trade_id = f"{int(datetime.now().timestamp())}"
        trade_request = {
            "id": trade_id,
            "user1": {"id": author.id, "name": author.display_name, "data": db_user},
            "user2": {"id": target_user.id, "name": target_user.display_name, "data": db_target_user},
            "status": "pending",
            "user1_offer": None,
            "user2_offer": None,
            "user1_ready": False,
            "user2_ready": False,
            "channel": channel,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5)
        }

        active_trades[trade_id] = trade_request

        # Set timeout for trade request expiration
        asyncio.create_task(self.expire_trade(trade_id, 300))

        embed = discord.Embed(
            color=0x3498db,
            title="🤝 Trade Request",
            description=f"**{author.display_name}** is requesting a trade with {target_user.mention}!\nClick the accept button to accept!",
        )
        embed.set_footer(text="Trade expires in 5 minutes")

        view = TradeRequestView(trade_id, target_user.id)
        
        message = await followup_func(embed=embed, view=view)
        trade_request["message"] = message

    async def expire_trade(self, trade_id, delay):
        await asyncio.sleep(delay)
        if trade_id in active_trades and active_trades[trade_id]["status"] == "pending":
            trade = active_trades[trade_id]
            del active_trades[trade_id]
            
            embed = discord.Embed(
                color=0xe74c3c,
                title="⏰ Trade Expired",
                description=f"Trade request from **{trade['user1']['name']}** to **{trade['user2']['name']}** has expired!"
            )
            
            try:
                await trade["message"].edit(embed=embed, view=None)
            except:
                pass

class TradeRequestView(discord.ui.View):
    def __init__(self, trade_id, target_user_id):
        super().__init__(timeout=300)
        self.trade_id = trade_id
        self.target_user_id = target_user_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user_id:
            return await interaction.response.send_message("❌ This trade request is not for you!", ephemeral=True)

        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade request is no longer valid!", ephemeral=True)

        trade = active_trades[self.trade_id]
        if trade["status"] != "pending":
            return await interaction.response.send_message("❌ This trade request is no longer valid!", ephemeral=True)

        # Convert to active trade
        trade["status"] = "active"

        embed = self.create_trade_embed(trade)
        view = ActiveTradeView(self.trade_id)

        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user_id:
            return await interaction.response.send_message("❌ This trade request is not for you!", ephemeral=True)

        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade request is no longer valid!", ephemeral=True)

        trade = active_trades[self.trade_id]
        del active_trades[self.trade_id]

        embed = discord.Embed(
            color=0xe74c3c,
            title="❌ Trade Rejected",
            description=f"**{interaction.user.display_name}** rejected the trade request."
        )

        await interaction.response.edit_message(embed=embed, view=None)

    def create_trade_embed(self, trade):
        user1_status = "🟢" if trade["user1_ready"] else "🔴"
        user2_status = "🟢" if trade["user2_ready"] else "🔴"
        
        user1_offer_text = "None"
        user2_offer_text = "None"
        
        if trade["user1_offer"]:
            offer = trade["user1_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user1_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"
        
        if trade["user2_offer"]:
            offer = trade["user2_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user2_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"

        embed = discord.Embed(
            color=0x3498db,
            title=f"Trade between {trade['user1']['name']} and {trade['user2']['name']}",
            description=f"{user1_status} **{trade['user1']['name']}**\n{user1_offer_text}\n\n{user2_status} **{trade['user2']['name']}**\n{user2_offer_text}"
        )
        embed.set_footer(text="Use the buttons below to add Pokemon or confirm the trade")
        
        return embed

class ActiveTradeView(discord.ui.View):
    def __init__(self, trade_id):
        super().__init__(timeout=600)
        self.trade_id = trade_id

    @discord.ui.button(label="Add Pokemon", style=discord.ButtonStyle.secondary)
    async def add_pokemon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        trade = active_trades[self.trade_id]
        if trade["status"] != "active":
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        # Check if user is part of this trade
        is_user1 = trade["user1"]["id"] == interaction.user.id
        is_user2 = trade["user2"]["id"] == interaction.user.id
        
        if not is_user1 and not is_user2:
            return await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)

        # Show pokemon selection modal
        modal = PokemonSelectionModal(self.trade_id, is_user1)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Confirm Trade", style=discord.ButtonStyle.success)
    async def confirm_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        trade = active_trades[self.trade_id]
        if trade["status"] != "active":
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        is_user1 = trade["user1"]["id"] == interaction.user.id
        is_user2 = trade["user2"]["id"] == interaction.user.id
        
        if not is_user1 and not is_user2:
            return await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)

        # Show confirmation embed
        embed = discord.Embed(
            color=0xf39c12,
            title="⚠️ Confirm Trade",
            description="Are you sure you want to confirm this trade? Please make sure that you are trading what you intended to."
        )
        
        user1_offer_text = "None"
        user2_offer_text = "None"
        
        if trade["user1_offer"]:
            offer = trade["user1_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user1_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"
        
        if trade["user2_offer"]:
            offer = trade["user2_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user2_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"

        embed.add_field(
            name=f"Trade between {trade['user1']['name']} and {trade['user2']['name']}",
            value=f"🟢 **{trade['user1']['name']}**\n{user1_offer_text}\n\n🔴 **{trade['user2']['name']}**\n{user2_offer_text}",
            inline=False
        )

        view = ConfirmTradeView(self.trade_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        trade = active_trades[self.trade_id]
        is_user1 = trade["user1"]["id"] == interaction.user.id
        is_user2 = trade["user2"]["id"] == interaction.user.id
        
        if not is_user1 and not is_user2:
            return await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)

        del active_trades[self.trade_id]

        other_user = trade["user2"]["name"] if is_user1 else trade["user1"]["name"]

        embed = discord.Embed(
            color=0xe74c3c,
            title="❌ Trade Cancelled",
            description=f"**{interaction.user.display_name}** cancelled the trade with **{other_user}**."
        )

        await interaction.response.edit_message(embed=embed, view=None)

class PokemonSelectionModal(discord.ui.Modal):
    def __init__(self, trade_id, is_user1):
        super().__init__(title="Select Pokemon to Trade")
        self.trade_id = trade_id
        self.is_user1 = is_user1
        
        self.pokemon_number = discord.ui.TextInput(
            label="Pokemon Number",
            placeholder="Enter the number of the Pokemon you want to trade",
            required=True,
            max_length=10
        )
        self.add_item(self.pokemon_number)

    async def on_submit(self, interaction: discord.Interaction):
        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        try:
            pokemon_num = int(self.pokemon_number.value)
        except ValueError:
            return await interaction.response.send_message("❌ Please enter a valid Pokemon number!", ephemeral=True)

        trade = active_trades[self.trade_id]
        user_data = trade["user1"]["data"] if self.is_user1 else trade["user2"]["data"]

        # Get user's Pokemon collection
        bot = interaction.client
        
        # Find the specific Pokemon with the matching pokemon_number
        selected_pokemon = await bot.pokemon_collection.find_one({
            "user_id": user_data["user_id"],
            "pokemon_number": pokemon_num
        })
        
        if not selected_pokemon:
            return await interaction.response.send_message(f"❌ You don't have a Pokemon with number {pokemon_num}!", ephemeral=True)

        # Check if user has more than one Pokemon (can't trade their only Pokemon)
        total_pokemon = await bot.pokemon_collection.count_documents({"user_id": user_data["user_id"]})
        if total_pokemon <= 1:
            return await interaction.response.send_message("❌ You cannot trade your only Pokémon! You must always have at least one Pokémon in your collection.", ephemeral=True)

        # Update trade offer
        if self.is_user1:
            trade["user1_offer"] = selected_pokemon
            trade["user1_ready"] = False
        else:
            trade["user2_offer"] = selected_pokemon
            trade["user2_ready"] = False

        # Update the trade embed
        embed = self.create_trade_embed(trade)
        view = ActiveTradeView(self.trade_id)

        try:
            await trade["message"].edit(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Added **{selected_pokemon['pokemon_name']}** to the trade!", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Added **{selected_pokemon['pokemon_name']}** to the trade!", ephemeral=True)

    def create_trade_embed(self, trade):
        user1_status = "🟢" if trade["user1_ready"] else "🔴"
        user2_status = "🟢" if trade["user2_ready"] else "🔴"
        
        user1_offer_text = "None"
        user2_offer_text = "None"
        
        if trade["user1_offer"]:
            offer = trade["user1_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user1_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"
        
        if trade["user2_offer"]:
            offer = trade["user2_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user2_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"

        embed = discord.Embed(
            color=0x3498db,
            title=f"Trade between {trade['user1']['name']} and {trade['user2']['name']}",
            description=f"{user1_status} **{trade['user1']['name']}**\n{user1_offer_text}\n\n{user2_status} **{trade['user2']['name']}**\n{user2_offer_text}"
        )
        embed.set_footer(text="Use the buttons below to add Pokemon or confirm the trade")
        
        return embed

class ConfirmTradeView(discord.ui.View):
    def __init__(self, trade_id, user_id):
        super().__init__(timeout=60)
        self.trade_id = trade_id
        self.user_id = user_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def final_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Invalid confirmation!", ephemeral=True)

        if self.trade_id not in active_trades:
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        trade = active_trades[self.trade_id]
        if trade["status"] != "active":
            return await interaction.response.send_message("❌ This trade is no longer active!", ephemeral=True)

        is_user1 = trade["user1"]["id"] == interaction.user.id
        
        # Mark user as ready
        if is_user1:
            trade["user1_ready"] = True
        else:
            trade["user2_ready"] = True

        await interaction.response.edit_message(content="✅ You have confirmed the trade. Waiting for the other player...", embed=None, view=None)

        # Check if both users are ready
        if trade["user1_ready"] and trade["user2_ready"]:
            await self.complete_trade(trade, interaction.client)
        else:
            # Update the main trade embed to show one user is ready
            embed = self.create_trade_embed(trade)
            view = ActiveTradeView(self.trade_id)
            
            try:
                await trade["message"].edit(embed=embed, view=view)
            except:
                pass

    @discord.ui.button(label="Abort", style=discord.ButtonStyle.danger)
    async def abort_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Trade confirmation cancelled.", embed=None, view=None)

    def create_trade_embed(self, trade):
        user1_status = "🟢" if trade["user1_ready"] else "🔴"
        user2_status = "🟢" if trade["user2_ready"] else "🔴"
        
        user1_offer_text = "None"
        user2_offer_text = "None"
        
        if trade["user1_offer"]:
            offer = trade["user1_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user1_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"
        
        if trade["user2_offer"]:
            offer = trade["user2_offer"]
            shiny_text = "✨ " if offer.get("shiny") else ""
            iv_percentage = calculate_iv_percentage(offer)
            user2_offer_text = f"{shiny_text}**{offer['pokemon_name']}** • Lvl. {offer['level']} • {iv_percentage}%"

        embed = discord.Embed(
            color=0x3498db,
            title=f"Trade between {trade['user1']['name']} and {trade['user2']['name']}",
            description=f"{user1_status} **{trade['user1']['name']}**\n{user1_offer_text}\n\n{user2_status} **{trade['user2']['name']}**\n{user2_offer_text}"
        )
        embed.set_footer(text="Use the buttons below to add Pokemon or confirm the trade")
        
        return embed

    async def complete_trade(self, trade, bot):
        try:
            trade_results = []

            # Helper function to get next pokemon number for a user
            async def get_next_pokemon_number(user_id):
                # Get the highest pokemon_number for this user
                highest = await bot.pokemon_collection.find_one(
                    {"user_id": user_id},
                    sort=[("pokemon_number", -1)]
                )
                return (highest["pokemon_number"] + 1) if highest else 1

            # Handle Pokemon transfers
            if trade["user1_offer"]:
                # Transfer Pokemon from user1 to user2
                pokemon = trade["user1_offer"]
                next_number = await get_next_pokemon_number(trade["user2"]["id"])
                
                await bot.pokemon_collection.update_one(
                    {"_id": pokemon["_id"]},
                    {"$set": {
                        "user_id": trade["user2"]["id"],
                        "pokemon_number": next_number,
                        "selected": False  # Unselect traded Pokemon
                    }}
                )
                
                # Clear selected Pokemon if it was traded from user1
                user1_selected = await bot.pokemon_collection.find_one({
                    "user_id": trade["user1"]["id"], 
                    "selected": True
                })
                if user1_selected and str(user1_selected["_id"]) == str(pokemon["_id"]):
                    # Find another Pokemon to select for user1, or leave none selected
                    replacement = await bot.pokemon_collection.find_one({
                        "user_id": trade["user1"]["id"],
                        "_id": {"$ne": pokemon["_id"]}
                    })
                    if replacement:
                        await bot.pokemon_collection.update_one(
                            {"_id": replacement["_id"]},
                            {"$set": {"selected": True}}
                        )
                
                shiny_text = "✨ " if pokemon.get("shiny") else ""
                trade_results.append(f"**{trade['user2']['name']}** received: {shiny_text}{pokemon['pokemon_name']} (Lvl {pokemon['level']})")

            if trade["user2_offer"]:
                # Transfer Pokemon from user2 to user1
                pokemon = trade["user2_offer"]
                next_number = await get_next_pokemon_number(trade["user1"]["id"])
                
                await bot.pokemon_collection.update_one(
                    {"_id": pokemon["_id"]},
                    {"$set": {
                        "user_id": trade["user1"]["id"],
                        "pokemon_number": next_number,
                        "selected": False  # Unselect traded Pokemon
                    }}
                )
                
                # Clear selected Pokemon if it was traded from user2
                user2_selected = await bot.pokemon_collection.find_one({
                    "user_id": trade["user2"]["id"], 
                    "selected": True
                })
                if user2_selected and str(user2_selected["_id"]) == str(pokemon["_id"]):
                    # Find another Pokemon to select for user2, or leave none selected
                    replacement = await bot.pokemon_collection.find_one({
                        "user_id": trade["user2"]["id"],
                        "_id": {"$ne": pokemon["_id"]}
                    })
                    if replacement:
                        await bot.pokemon_collection.update_one(
                            {"_id": replacement["_id"]},
                            {"$set": {"selected": True}}
                        )
                
                shiny_text = "✨ " if pokemon.get("shiny") else ""
                trade_results.append(f"**{trade['user1']['name']}** received: {shiny_text}{pokemon['pokemon_name']} (Lvl {pokemon['level']})")

            # Remove from active trades
            del active_trades[trade["id"]]

            embed = discord.Embed(
                color=0x00ff00,
                title="✅ Trade Completed!",
                description="The trade has been completed successfully!"
            )
            embed.add_field(
                name="🎉 Trade Results",
                value="\n".join(trade_results) if trade_results else "Nothing was traded!",
                inline=False
            )
            embed.set_footer(text="Thank you for trading!")

            try:
                await trade["message"].edit(embed=embed, view=None)
            except:
                pass

        except Exception as error:
            print(f"❌ Error completing trade: {error}")
            if trade["id"] in active_trades:
                del active_trades[trade["id"]]

async def setup(bot):
    await bot.add_cog(TradeCog(bot)) 