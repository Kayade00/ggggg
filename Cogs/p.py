@commands.Cog.listener()
    async def on_message(self, message):
        """Handle message counting with anti-spam for spawn triggers"""
        if message.author.bot or not message.guild:
            return
        
        # Anti-spam: 1.5 second cooldown per user
        user_id = message.author.id
        current_time = datetime.utcnow()
        
        if user_id in self.last_message_time:
            time_diff = current_time - self.last_message_time[user_id]
            if time_diff < timedelta(seconds=1.5):
                return  # Ignore message due to spam protection
        
        self.last_message_time[user_id] = current_time
        
        # Server-wide message counting (count messages from ALL channels)
        server_id = message.guild.id
        
        # Add channel to general spawn channels if it's text channel and bot can send messages
        if isinstance(message.channel, discord.TextChannel):
            permissions = message.channel.permissions_for(message.guild.me)
            if permissions.send_messages and permissions.attach_files:
                if server_id not in self.spawn_channels:
                    self.spawn_channels[server_id] = set()
                self.spawn_channels[server_id].add(message.channel.id)
        
        # Initialize or increment message count for this server
        if server_id not in self.server_message_count:
            self.server_message_count[server_id] = 0
        
        self.server_message_count[server_id] += 1
        
        # Check if we should spawn a Pokémon (every 10 messages)
        if self.server_message_count[server_id] >= self.messages_until_spawn:
            # Reset counter
            self.server_message_count[server_id] = 0
            
            # Clean up old spawns first
            self.cleanup_old_spawns()
            
            # Determine which channels to use for spawning
            available_channels = []
            
            # Check if server has redirect channels set
            if server_id in self.redirect_channels and self.redirect_channels[server_id]:
                print(f"🎯 Using redirect channels for server {server_id}: {self.redirect_channels[server_id]}")
                # Use only redirect channels
                for channel_id in list(self.redirect_channels[server_id]):
                    channel = self.bot.get_channel(channel_id)
                    if channel and channel_id not in self.active_spawns:
                        # Verify channel still exists and bot has permissions
                        permissions = channel.permissions_for(channel.guild.me)
                        if permissions.send_messages and permissions.attach_files:
                            available_channels.append(channel)
                            print(f"✅ Added redirect channel {channel.name} to available channels")
                        else:
                            print(f"❌ No permissions in redirect channel {channel.name if channel else 'Unknown'}")
                            # Remove channel if no permissions
                            self.redirect_channels[server_id].discard(channel_id)
                    else:
                        if not channel:
                            print(f"❌ Redirect channel {channel_id} not found")
                        elif channel_id in self.active_spawns:
                            print(f"⏸️ Redirect channel {channel.name} has active spawn")
            else:
                print(f"🌐 Using all available channels for server {server_id}")
                # Use all available channels (default behavior)
                if server_id in self.spawn_channels and self.spawn_channels[server_id]:
                    for channel_id in list(self.spawn_channels[server_id]):
                        channel = self.bot.get_channel(channel_id)
                        if channel and channel_id not in self.active_spawns:
                            # Verify channel still exists and bot has permissions
                            permissions = channel.permissions_for(channel.guild.me)
                            if permissions.send_messages and permissions.attach_files:
                                available_channels.append(channel)
                            else:
                                # Remove channel if no permissions
                                self.spawn_channels[server_id].discard(channel_id)
            
            print(f"📊 Available spawn channels: {len(available_channels)}")
            print(f"📊 Available spawn channels: {len(available_channels)}")
            # Spawn in a random available channel
            if available_channels:
                spawn_channel = random.choice(available_channels)
                await self.spawn_pokemon(spawn_channel)
            else:
                print(f"❌ No available channels to spawn in for server {server_id}")
                # Debug: Show redirect channels
                if server_id in self.redirect_channels:
                    print(f"🎯 Redirect channels set: {self.redirect_channels[server_id]}")
                    for channel_id in self.redirect_channels[server_id]:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            permissions = channel.permissions_for(channel.guild.me)
                            print(f"   Channel {channel.name}: send_messages={permissions.send_messages}, attach_files={permissions.attach_files}, active_spawn={channel_id in self.active_spawns}")
                        else:
                            print(f"   Channel {channel_id}: NOT FOUND")
                else:
                    print(f"🌐 No redirect channels set for server {server_id}")