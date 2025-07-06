import discord
from discord.ext import commands, tasks
import aiohttp
import json
import asyncio
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional

class VoteSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_collection = bot.user_collection
        self.vote_collection = bot.db["vote_data"]
        self.topgg_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJib3QiOiJ0cnVlIiwiaWQiOiIxMzgwOTg0MjQ5NjMyNDIzOTk2IiwiaWF0IjoiMTc1MTc0MDA1MiJ9.scLEnk3Q45lHZ6HkaBD9qFHfsq5Q1Y728QgF-GKNEeU"
        self.bot_id = self.bot.user.id if self.bot.user else "1380984249632423996"
        self.topgg_api_url = f"https://top.gg/api/bots/{self.bot_id}"
        self.vote_reminder.start()
        
        # Vote rewards
        self.vote_rewards = {
            "coins": 500,
            "diamonds": 1,
            "items": {
                "vote_box": 1  # Give 1 vote box per vote
            }
        }
        
        # Vote streak rewards (additional rewards for consecutive days)
        self.streak_rewards = {
            3: {"coins": 500, "diamonds": 1},  # 3 day streak
            7: {"coins": 1000, "diamonds": 2},  # 7 day streak
            14: {"coins": 2000, "diamonds": 3},  # 14 day streak
            30: {"coins": 5000, "diamonds": 5}   # 30 day streak
        }

    def cog_unload(self):
        self.vote_reminder.cancel()

    async def get_user_vote_data(self, user_id: int) -> Dict:
        """Get user's vote data or create if it doesn't exist"""
        vote_data = await self.vote_collection.find_one({"user_id": user_id})
        
        if not vote_data:
            vote_data = {
                "user_id": user_id,
                "total_votes": 0,
                "last_vote": None,
                "current_streak": 0,
                "highest_streak": 0,
                "vote_reminders": False,
                "claimed_rewards": []
            }
            await self.vote_collection.insert_one(vote_data)
            
        return vote_data

    async def update_user_balance(self, user_id: int, coins_change=0, diamonds_change=0):
        """Update user's balance"""
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"coins": coins_change, "diamonds": diamonds_change}},
            upsert=True
        )
        print(f"🪙 Vote: Updated balance for user {user_id}: +{coins_change} coins, +{diamonds_change} diamonds")

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
        print(f"📦 Vote: Added {amount}x {item_name} to user {user_id}'s inventory")

    async def check_vote(self, user_id: int) -> bool:
        """Check if a user has voted on Top.gg recently"""
        headers = {"Authorization": self.topgg_token}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.topgg_api_url}/check?userId={user_id}",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return bool(data.get("voted", 0))
                    else:
                        print(f"⚠️ Vote: Failed to check vote status: {resp.status}")
                        return False
        except Exception as e:
            print(f"⚠️ Vote: Error checking vote status: {e}")
            return False

    async def process_vote(self, user_id: int, test_mode: bool = False) -> bool:
        """Process a user's vote and give rewards"""
        # In test mode, we skip the API check
        voted = True if test_mode else await self.check_vote(user_id)
        
        if not voted:
            return False
            
        # Get user's vote data
        vote_data = await self.get_user_vote_data(user_id)
        last_vote = vote_data.get("last_vote")
        
        # Convert string date to datetime if needed
        if isinstance(last_vote, str):
            try:
                last_vote = datetime.fromisoformat(last_vote)
            except:
                last_vote = None
        
        # Calculate streak
        current_streak = vote_data.get("current_streak", 0)
        now = datetime.utcnow()
        
        if last_vote:
            # Check if the last vote was within the past 48 hours (allowing for a 1-day grace period)
            hours_since_last_vote = (now - last_vote).total_seconds() / 3600
            
            if hours_since_last_vote <= 48:  # Within 48 hours
                current_streak += 1
            else:
                # Streak broken
                current_streak = 1
        else:
            # First vote
            current_streak = 1
        
        # Update vote data
        highest_streak = max(current_streak, vote_data.get("highest_streak", 0))
        
        await self.vote_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "last_vote": now,
                    "current_streak": current_streak,
                    "highest_streak": highest_streak
                },
                "$inc": {"total_votes": 1}
            },
            upsert=True
        )
        
        # Give base rewards
        await self.update_user_balance(
            user_id, 
            self.vote_rewards["coins"], 
            self.vote_rewards["diamonds"]
        )
        
        # Give item rewards
        for item_name, amount in self.vote_rewards.get("items", {}).items():
            await self.add_item_to_inventory(user_id, item_name, amount)
        
        # Check for streak rewards
        streak_reward = None
        for days, rewards in sorted(self.streak_rewards.items()):
            if current_streak >= days:
                # Check if this milestone has been claimed already
                milestone_key = f"streak_{days}_{current_streak // days}"
                if milestone_key not in vote_data.get("claimed_rewards", []):
                    streak_reward = {
                        "days": days,
                        "rewards": rewards,
                        "milestone_key": milestone_key
                    }
                    break
        
        # Give streak rewards if eligible
        if streak_reward:
            rewards = streak_reward["rewards"]
            await self.update_user_balance(
                user_id,
                rewards.get("coins", 0),
                rewards.get("diamonds", 0)
            )
            
            # Mark this milestone as claimed
            await self.vote_collection.update_one(
                {"user_id": user_id},
                {"$push": {"claimed_rewards": streak_reward["milestone_key"]}}
            )
        
        return {
            "success": True,
            "streak": current_streak,
            "total_votes": vote_data.get("total_votes", 0) + 1,
            "base_rewards": self.vote_rewards,
            "streak_reward": streak_reward
        }

    @commands.command(name="vote", aliases=["v"])
    async def vote_command(self, ctx):
        """Vote for the bot on Top.gg and receive rewards!"""
        user_id = ctx.author.id
        vote_data = await self.get_user_vote_data(user_id)
        
        # Create embed with vote information
        embed = discord.Embed(
            title="🗳️ Vote for Pokémon Bot!",
            description="Support the bot by voting on Top.gg and receive awesome rewards!",
            color=0x3498db
        )
        
        # Add vote link
        embed.add_field(
            name="Vote Link",
            value=f"[Click here to vote on Top.gg!](https://top.gg/bot/{self.bot_id}/vote)",
            inline=False
        )
        
        # Add rewards info
        rewards_text = f"• 🪙 **{self.vote_rewards['coins']}** coins\n"
        rewards_text += f"• 💎 **{self.vote_rewards['diamonds']}** diamonds\n"
        
        for item, amount in self.vote_rewards.get("items", {}).items():
            rewards_text += f"• 📦 **{amount}x** {item.replace('_', ' ').title()}\n"
        
        embed.add_field(
            name="Vote Rewards",
            value=rewards_text,
            inline=True
        )
        
        # Add vote box info
        embed.add_field(
            name="📦 Vote Box Contents",
            value="Each Vote Box can contain:\n• Coins (500-2000)\n• Diamonds (1-5)\n• High IV Pokémon (70%+ IVs)\n• Shiny Charm",
            inline=True
        )
        
        # Add streak info
        streak_text = f"• Current streak: **{vote_data.get('current_streak', 0)}** days\n"
        streak_text += f"• Highest streak: **{vote_data.get('highest_streak', 0)}** days\n"
        streak_text += f"• Total votes: **{vote_data.get('total_votes', 0)}**\n"
        
        embed.add_field(
            name="Your Stats",
            value=streak_text,
            inline=True
        )
        
        # Add streak rewards info
        streak_rewards_text = ""
        for days, rewards in sorted(self.streak_rewards.items()):
            streak_rewards_text += f"• **{days} days**: +{rewards.get('coins', 0)} coins, +{rewards.get('diamonds', 0)} diamonds\n"
        
        embed.add_field(
            name="Streak Bonuses",
            value=streak_rewards_text,
            inline=False
        )
        
        # Add last vote info
        last_vote = vote_data.get("last_vote")
        if last_vote:
            if isinstance(last_vote, str):
                try:
                    last_vote = datetime.fromisoformat(last_vote)
                except:
                    last_vote = None
            
            if last_vote:
                time_since_vote = datetime.utcnow() - last_vote
                hours_remaining = 24 - (time_since_vote.total_seconds() / 3600)
                
                if hours_remaining > 0:
                    embed.add_field(
                        name="Next Vote Available",
                        value=f"You can vote again in **{int(hours_remaining)} hours and {int((hours_remaining % 1) * 60)} minutes**",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Vote Now!",
                        value="You can vote right now! Click the link above to get your rewards!",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Vote Now!",
                    value="You can vote right now! Click the link above to get your rewards!",
                    inline=False
                )
        else:
            embed.add_field(
                name="Vote Now!",
                value="You haven't voted yet! Click the link above to get your rewards!",
                inline=False
            )
        
        # Add footer
        embed.set_footer(text="After voting, use 'b!claim' to claim your rewards and automatically open your Vote Box!")
        
        # Create vote button
        view = VoteView(self.bot_id)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="claim", aliases=["claimvote"])
    async def claim_vote(self, ctx):
        """Claim your vote rewards after voting on Top.gg"""
        user_id = ctx.author.id
        
        # Process the vote
        result = await self.process_vote(user_id)
        
        if not result:
            embed = discord.Embed(
                title="❌ Vote Not Found",
                description="You haven't voted yet or your vote has already been claimed. Please vote using the link below!",
                color=0xe74c3c
            )
            embed.add_field(
                name="Vote Link",
                value=f"[Click here to vote on Top.gg!](https://top.gg/bot/{self.bot_id}/vote)",
                inline=False
            )
            embed.set_footer(text="You can vote once every 12 hours.")
            
            # Create vote button
            view = VoteView(self.bot_id)
            await ctx.send(embed=embed, view=view)
            return
        
        # Create success embed
        embed = discord.Embed(
            title="✅ Vote Rewards Claimed!",
            description="Thank you for supporting the bot! Here are your rewards:",
            color=0x2ecc71
        )
        
        # Add base rewards
        base_rewards = result["base_rewards"]
        rewards_text = f"• 🪙 **{base_rewards['coins']}** coins\n"
        rewards_text += f"• 💎 **{base_rewards['diamonds']}** diamonds\n"
        
        for item, amount in base_rewards.get("items", {}).items():
            rewards_text += f"• 📦 **{amount}x** {item.replace('_', ' ').title()}\n"
        
        embed.add_field(
            name="Base Rewards",
            value=rewards_text,
            inline=True
        )
        
        # Add streak info
        streak_text = f"• Current streak: **{result['streak']}** days\n"
        streak_text += f"• Total votes: **{result['total_votes']}**\n"
        
        embed.add_field(
            name="Your Stats",
            value=streak_text,
            inline=True
        )
        
        # Add streak rewards if applicable
        if result.get("streak_reward"):
            streak_reward = result["streak_reward"]
            streak_rewards = streak_reward["rewards"]
            
            streak_text = f"🎉 **{streak_reward['days']}-Day Streak Bonus!**\n"
            streak_text += f"• 🪙 **+{streak_rewards.get('coins', 0)}** coins\n"
            streak_text += f"• 💎 **+{streak_rewards.get('diamonds', 0)}** diamonds\n"
            
            embed.add_field(
                name="Streak Bonus!",
                value=streak_text,
                inline=False
            )
        
        # Send the initial rewards message
        await ctx.send(embed=embed)
        
        # Now automatically open the vote box
        try:
            # Get the inventory cog
            inventory_cog = self.bot.get_cog("Inventory")
            if inventory_cog:
                # Check if user has a vote box
                user_data = await self.user_collection.find_one({"user_id": user_id})
                inventory = user_data.get("inventory", {})
                
                if inventory.get("vote_box", 0) > 0:
                    # Open the vote box
                    await ctx.send("🎁 Opening your Vote Box automatically...")
                    await inventory_cog.open_vote_box(ctx, user_id)
                    
                    # Add reminder toggle button in a separate message
                    view = VoteReminderView(self, user_id)
                    await ctx.send("Would you like to receive vote reminders?", view=view)
                else:
                    # This shouldn't happen normally, but just in case
                    await ctx.send("⚠️ You should have received a Vote Box, but it wasn't found in your inventory.")
                    
                    # Add reminder toggle button
                    view = VoteReminderView(self, user_id)
                    await ctx.send("Would you like to receive vote reminders?", view=view)
            else:
                # If inventory cog not found, just show reminder button
                view = VoteReminderView(self, user_id)
                await ctx.send("Would you like to receive vote reminders?", view=view)
        except Exception as e:
            print(f"⚠️ Error opening vote box automatically: {e}")
            # If there's an error, still show the reminder button
            view = VoteReminderView(self, user_id)
            await ctx.send("Would you like to receive vote reminders?", view=view)

    @commands.command(name="voteremind", aliases=["vr"])
    async def vote_remind_toggle(self, ctx):
        """Toggle vote reminders in DMs"""
        user_id = ctx.author.id
        vote_data = await self.get_user_vote_data(user_id)
        
        # Toggle reminder setting
        current_setting = vote_data.get("vote_reminders", False)
        new_setting = not current_setting
        
        await self.vote_collection.update_one(
            {"user_id": user_id},
            {"$set": {"vote_reminders": new_setting}}
        )
        
        if new_setting:
            await ctx.send("✅ Vote reminders have been **enabled**. You'll receive a DM when you can vote again!")
        else:
            await ctx.send("✅ Vote reminders have been **disabled**. You won't receive vote reminder DMs.")

    @commands.command(name="testvote", hidden=True)
    @commands.is_owner()
    async def test_vote(self, ctx, user_id: int = None):
        """Test the vote system (owner only)"""
        if user_id is None:
            user_id = ctx.author.id
            
        result = await self.process_vote(user_id, test_mode=True)
        await ctx.send(f"Test vote processed: ```json\n{json.dumps(result, default=str, indent=2)}\n```")

    @tasks.loop(minutes=30)
    async def vote_reminder(self):
        """Check for users who can vote again and send reminders"""
        now = datetime.utcnow()
        
        # Find users who have vote reminders enabled and haven't voted in the last 12 hours
        async for vote_data in self.vote_collection.find({"vote_reminders": True}):
            user_id = vote_data.get("user_id")
            last_vote = vote_data.get("last_vote")
            
            # Convert string date to datetime if needed
            if isinstance(last_vote, str):
                try:
                    last_vote = datetime.fromisoformat(last_vote)
                except:
                    last_vote = None
            
            # Check if it's been more than 12 hours since their last vote
            if last_vote and (now - last_vote).total_seconds() >= 12 * 3600:
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        embed = discord.Embed(
                            title="🗳️ Vote Reminder",
                            description="You can vote for the Pokémon bot again! Don't break your streak!",
                            color=0x3498db
                        )
                        embed.add_field(
                            name="Vote Link",
                            value=f"[Click here to vote on Top.gg!](https://top.gg/bot/{self.bot_id}/vote)",
                            inline=False
                        )
                        embed.add_field(
                            name="Current Streak",
                            value=f"**{vote_data.get('current_streak', 0)}** days",
                            inline=True
                        )
                        embed.add_field(
                            name="Total Votes",
                            value=f"**{vote_data.get('total_votes', 0)}**",
                            inline=True
                        )
                        embed.set_footer(text="Use 'b!voteremind' to disable these reminders")
                        
                        # Create vote button for DM
                        view = VoteView(self.bot_id)
                        await user.send(embed=embed, view=view)
                        print(f"📧 Vote: Sent reminder to {user.name} (ID: {user_id})")
                except Exception as e:
                    print(f"⚠️ Vote: Failed to send reminder to user {user_id}: {e}")

    @vote_reminder.before_loop
    async def before_vote_reminder(self):
        await self.bot.wait_until_ready()
        print("✅ Vote reminder task started")
        
    async def setup_webhook_server(self, app):
        """Set up the webhook server for Top.gg vote notifications"""
        from aiohttp import web
        
        # Define the webhook route
        async def webhook_handler(request):
            # Verify authorization
            auth_header = request.headers.get('Authorization')
            if not auth_header or auth_header != self.topgg_token:
                return web.Response(status=401, text="Unauthorized")
            
            try:
                # Parse the vote data
                data = await request.json()
                user_id = int(data.get('user'))
                
                # Process the vote
                result = await self.process_vote(user_id, test_mode=True)  # Force process regardless of API check
                print(f"✅ Vote: Processed webhook vote for user {user_id}: {result}")
                
                # Try to open the vote box automatically
                try:
                    inventory_cog = self.bot.get_cog("Inventory")
                    if inventory_cog:
                        # Get user data to check for vote box
                        user_data = await self.user_collection.find_one({"user_id": user_id})
                        inventory = user_data.get("inventory", {})
                        
                        if inventory.get("vote_box", 0) > 0:
                            # Get a channel to send the message
                            # We'll use a DM for this since we don't know which channel to use
                            user = await self.bot.fetch_user(user_id)
                            if user:
                                # Create a fake context for the open_vote_box method
                                class FakeContext:
                                    def __init__(self, user):
                                        self.author = user
                                    
                                    async def send(self, content=None, embed=None):
                                        if user:
                                            return await user.send(content=content, embed=embed)
                                
                                fake_ctx = FakeContext(user)
                                
                                # Open the vote box
                                await inventory_cog.open_vote_box(fake_ctx, user_id)
                                print(f"✅ Vote: Automatically opened vote box for user {user_id} via webhook")
                except Exception as e:
                    print(f"⚠️ Vote: Error opening vote box via webhook: {e}")
                
                # Try to notify the user
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        embed = discord.Embed(
                            title="✅ Vote Received!",
                            description="Thank you for voting! Your rewards have been automatically credited and your Vote Box has been opened!",
                            color=0x2ecc71
                        )
                        embed.add_field(
                            name="Rewards",
                            value=f"• 🪙 **{self.vote_rewards['coins']}** coins\n• 💎 **{self.vote_rewards['diamonds']}** diamonds\n• 📦 **1x Vote Box** (automatically opened)",
                            inline=False
                        )
                        embed.set_footer(text="Use 'b!vote' to check your voting stats!")
                        await user.send(embed=embed)
                except:
                    # It's okay if we can't DM the user
                    pass
                
                return web.Response(status=200, text="Vote processed")
            except Exception as e:
                print(f"⚠️ Vote: Error processing webhook: {e}")
                return web.Response(status=500, text="Internal error")
        
        # Add the route to the app
        app.router.add_post('/topgg-webhook', webhook_handler)
        
        # Get server IP and port for display
        import socket
        hostname = socket.gethostname()
        try:
            # Try to get the local IP address
            ip_address = socket.gethostbyname(hostname)
        except:
            ip_address = "YOUR_SERVER_IP"
        
        webhook_port = self.bot.config.get("webhook_port", 8017)
        webhook_url = f"http://{ip_address}:{webhook_port}/topgg-webhook"
        
        print(f"✅ Vote: Top.gg webhook endpoint set up at /topgg-webhook")
        print(f"📝 Top.gg Webhook Setup Instructions:")
        print(f"   1. Go to https://top.gg/bot/{self.bot_id}/webhooks")
        print(f"   2. Set Webhook URL to: {webhook_url}")
        print(f"   3. Set Authorization to: {self.topgg_token}")
        print(f"   4. Select the 'vote' event")
        print(f"   5. Click 'Save'")
        print(f"   Note: If your server is behind a router, you need to forward port {webhook_port}")

class VoteView(discord.ui.View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id
        
        # Add vote button
        vote_button = discord.ui.Button(
            label="Vote on Top.gg",
            style=discord.ButtonStyle.url,
            url=f"https://top.gg/bot/{bot_id}/vote",
            emoji="🗳️"
        )
        self.add_item(vote_button)

class VoteReminderView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
    
    @discord.ui.button(label="Toggle Vote Reminders", style=discord.ButtonStyle.secondary, emoji="🔔")
    async def toggle_reminders(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button isn't for you!", ephemeral=True)
            return
            
        # Get current setting
        vote_data = await self.cog.get_user_vote_data(self.user_id)
        current_setting = vote_data.get("vote_reminders", False)
        new_setting = not current_setting
        
        # Update setting
        await self.cog.vote_collection.update_one(
            {"user_id": self.user_id},
            {"$set": {"vote_reminders": new_setting}}
        )
        
        if new_setting:
            await interaction.response.send_message("✅ Vote reminders have been **enabled**. You'll receive a DM when you can vote again!", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Vote reminders have been **disabled**. You won't receive vote reminder DMs.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(VoteSystem(bot)) 