# Clow

A minimal Discord server maintenance bot.

## Commands

- `/on exemptroles: Admin, Moderator` — enables maintenance and lets only the listed roles view channels. You can enter role names, role mentions, or role IDs separated by commas.
- `/start` — ends maintenance and restores the channel permission overwrites saved before the lock.
- Channels created while maintenance is active are locked automatically using the same exempt-role list.

All commands require the Discord Administrator permission. Exempt roles are set per server each time `/on` is used. If `EXEMPT_ROLE_IDS` is set in `.env`, those IDs are used only as the initial default before the first `/on` for that server.

## Setup

1. Create a Discord application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Invite the bot with the `bot` and `applications.commands` scopes. Give it **Manage Channels** permission and keep its role above roles it needs to manage.
3. Copy `.env.example` to `.env`.
4. Put the bot token in `DISCORD_TOKEN`.
5. Install dependencies and run:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## Important

- Keep `.env` and `maintenance_state.json` private. Never commit bot tokens.
- Keep `maintenance_state.json` persistent between restarts; it stores the original overwrites needed by `/start`.
- Test on a private test server first. Maintenance mode changes channel permission overwrites across the server.
- Discord administrators and members with Administrator permission can still see all channels regardless of channel overwrites. Do not give Administrator permission to anyone who should be restricted.
- If roles or members are deleted during maintenance, their old overwrites cannot be restored for those missing targets.
