# Clow

A minimal Discord server maintenance bot with two slash commands.

## Commands

- `/on` — enables maintenance mode, hides channels from @everyone, and explicitly allows configured exempt roles.
- `/start` — ends maintenance mode and restores the channel permission overwrites saved before the lock.
- Channels created while maintenance is active are locked automatically.

Both commands require the Discord Administrator permission.

## Setup

1. Create a Discord application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Invite the bot with the `bot` and `applications.commands` scopes. Give it **Manage Channels** permission. Keep its role above any roles it needs to manage.
3. Copy `.env.example` to `.env`.
4. Put the bot token in `DISCORD_TOKEN`.
5. Put comma-separated role IDs in `EXEMPT_ROLE_IDS` for roles that should retain channel visibility during maintenance.
6. Install dependencies and run:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## Important

- Keep `.env` and `maintenance_state.json` private. Never commit bot tokens.
- The bot needs **Manage Channels** to edit channel permission overwrites.
- Keep `maintenance_state.json` persistent between restarts; it stores the original overwrites needed by `/start`.
- Test on a private test server first. Maintenance mode changes channel permission overwrites across the server.
- The bot restores saved overwrites for channels it successfully recorded. If roles or members are deleted during maintenance, their old overwrites cannot be restored for those missing targets.
