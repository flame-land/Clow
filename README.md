# Clow

A minimal Discord server maintenance bot.

## Commands

- `/on` — enables maintenance mode, hides channels from non-exempt roles, and keeps exempt roles able to view channels.
- `/start` — ends maintenance mode and restores the channel permission overwrites saved before the lock.
- `/exempt add role:@Role` — exempts a role from maintenance lockdown.
- `/exempt remove role:@Role` — removes a role's exemption.
- `/exempt list` — lists the server's exempt roles.
- Channels created while maintenance is active are locked automatically.

All commands require the Discord Administrator permission. Exempt roles are stored per server in `maintenance_state.json` and persist across restarts. If `EXEMPT_ROLE_IDS` is set in `.env`, those IDs are used as the initial exempt-role list for a server.

## Setup

1. Create a Discord application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Invite the bot with the `bot` and `applications.commands` scopes. Give it **Manage Channels** permission. Keep its role above any roles it needs to manage.
3. Copy `.env.example` to `.env`.
4. Put the bot token in `DISCORD_TOKEN`.
5. Install dependencies and run:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## Important

- Keep `.env` and `maintenance_state.json` private. Never commit bot tokens.
- The bot needs **Manage Channels** to edit channel permission overwrites.
- Keep `maintenance_state.json` persistent between restarts; it stores exempt roles and the original overwrites needed by `/start`.
- Test on a private test server first. Maintenance mode changes channel permission overwrites across the server.
- If roles or members are deleted during maintenance, their old overwrites cannot be restored for those missing targets.
