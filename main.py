import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
EXEMPT_ROLE_IDS = {
    int(value.strip())
    for value in os.getenv("EXEMPT_ROLE_IDS", "").split(",")
    if value.strip().isdigit()
}
STATE_FILE = Path(os.getenv("STATE_FILE", "maintenance_state.json"))


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATE_FILE)


def get_guild_state(guild):
    key = str(guild.id)
    if key not in state:
        state[key] = {
            "active": False,
            "channels": {},
            "exempt_role_ids": sorted(EXEMPT_ROLE_IDS),
        }
    elif "exempt_role_ids" not in state[key]:
        # Migrate state files created before per-server exempt roles existed.
        state[key]["exempt_role_ids"] = sorted(EXEMPT_ROLE_IDS)
    return state[key]


def overwrite_to_data(overwrite):
    allow, deny = overwrite.pair()
    return {"allow": allow.value, "deny": deny.value}


def overwrite_from_data(data):
    return discord.PermissionOverwrite.from_pair(
        discord.Permissions(data["allow"]),
        discord.Permissions(data["deny"]),
    )


def target_key(target):
    kind = "role" if isinstance(target, discord.Role) else "member"
    return f"{kind}:{target.id}"


def serialize_overwrites(channel):
    result = {}
    for target, overwrite in channel.overwrites.items():
        result[target_key(target)] = overwrite_to_data(overwrite)
    return result


async def restore_overwrites(guild, channel, saved):
    restored = {}
    for key, data in saved.items():
        kind, raw_id = key.split(":", 1)
        target_id = int(raw_id)
        target = (
            guild.get_role(target_id)
            if kind == "role"
            else guild.get_member(target_id)
        )
        if target is None and kind == "member":
            try:
                target = await guild.fetch_member(target_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                target = None
        if target is not None:
            restored[target] = overwrite_from_data(data)
    await channel.edit(overwrites=restored, reason="Clow: restore maintenance permissions")


intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
state = load_state()


async def lock_channel(channel):
    guild = channel.guild
    guild_state = get_guild_state(guild)
    exempt_role_ids = {int(role_id) for role_id in guild_state["exempt_role_ids"]}
    channel_id = str(channel.id)

    # Save the pre-lock state once, so /start can restore it.
    if channel_id not in guild_state["channels"]:
        guild_state["channels"][channel_id] = serialize_overwrites(channel)
        save_state(state)

    overwrites = dict(channel.overwrites)
    everyone = guild.default_role
    everyone_overwrite = overwrites.get(everyone, discord.PermissionOverwrite())
    everyone_overwrite.view_channel = False
    overwrites[everyone] = everyone_overwrite

    # Ordinary roles are denied; configured exempt roles are allowed.
    for role in guild.roles:
        if role == everyone:
            continue
        role_overwrite = overwrites.get(role, discord.PermissionOverwrite())
        role_overwrite.view_channel = role.id in exempt_role_ids
        overwrites[role] = role_overwrite

    # Remove member-specific view overrides that could bypass role-level rules.
    for target, member_overwrite in list(overwrites.items()):
        if isinstance(target, discord.Member):
            member_overwrite.view_channel = None
            overwrites[target] = member_overwrite

    await channel.edit(overwrites=overwrites, reason="Clow: maintenance enabled")


async def apply_lock_to_guild(guild):
    for channel in guild.channels:
        try:
            await lock_channel(channel)
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"Could not lock channel {channel.id} in {guild.id}: {exc}")


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user}; synced {len(synced)} slash commands.")
    except discord.HTTPException as exc:
        print(f"Command sync failed: {exc}")


@bot.event
async def on_guild_channel_create(channel):
    guild_state = state.get(str(channel.guild.id))
    if not guild_state or not guild_state.get("active"):
        return
    try:
        await lock_channel(channel)
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not lock new channel {channel.id}: {exc}")


@bot.tree.command(name="on", description="Enable server maintenance mode.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def maintenance_on(interaction: discord.Interaction):
    guild = interaction.guild
    guild_state = get_guild_state(guild)
    if guild_state["active"]:
        await interaction.response.send_message(
            "Maintenance mode is already on.", ephemeral=True
        )
        return

    guild_state["active"] = True
    save_state(state)
    await interaction.response.send_message(
        "Maintenance mode enabled. Locking channels…", ephemeral=True
    )
    await apply_lock_to_guild(guild)
    await interaction.followup.send(
        "Maintenance mode is on. Newly created channels will also be locked.",
        ephemeral=True,
    )


@bot.tree.command(name="start", description="End maintenance and restore channel permissions.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def maintenance_start(interaction: discord.Interaction):
    guild = interaction.guild
    guild_state = state.get(str(guild.id))
    if not guild_state or not guild_state.get("active"):
        await interaction.response.send_message(
            "Maintenance mode is not active.", ephemeral=True
        )
        return

    guild_state["active"] = False
    save_state(state)
    await interaction.response.send_message(
        "Maintenance is ending. Restoring channel permissions…", ephemeral=True
    )

    failed = []
    for channel_id, saved in list(guild_state.get("channels", {}).items()):
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            await restore_overwrites(guild, channel, saved)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(channel.name)
            print(f"Could not restore channel {channel.id}: {exc}")

    guild_state["channels"] = {}
    save_state(state)
    if failed:
        await interaction.followup.send(
            "Maintenance ended, but I couldn't restore these channels: "
            + ", ".join(failed[:20])
            + ". Check Clow's Manage Channels permission.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "Maintenance ended. Saved channel permissions have been restored.",
            ephemeral=True,
        )


exempt_group = app_commands.Group(
    name="exempt",
    description="Manage roles that can view channels during maintenance.",
)


@exempt_group.command(name="add", description="Allow a role to view channels during maintenance.")
@app_commands.describe(role="The role to exempt from maintenance lockdown.")
@app_commands.checks.has_permissions(administrator=True)
async def exempt_add(interaction: discord.Interaction, role: discord.Role):
    guild_state = get_guild_state(interaction.guild)
    role_ids = {int(role_id) for role_id in guild_state["exempt_role_ids"]}
    if role.id in role_ids:
        await interaction.response.send_message(
            f"{role.mention} is already exempt.", ephemeral=True
        )
        return

    role_ids.add(role.id)
    guild_state["exempt_role_ids"] = sorted(role_ids)
    save_state(state)

    note = ""
    if guild_state["active"]:
        await apply_lock_to_guild(interaction.guild)
        note = " The active maintenance lock has been updated."
    await interaction.response.send_message(
        f"Added {role.mention} to the exempt roles.{note}", ephemeral=True
    )


@exempt_group.command(name="remove", description="Remove a role's maintenance exemption.")
@app_commands.describe(role="The role to remove from the exempt list.")
@app_commands.checks.has_permissions(administrator=True)
async def exempt_remove(interaction: discord.Interaction, role: discord.Role):
    guild_state = get_guild_state(interaction.guild)
    role_ids = {int(role_id) for role_id in guild_state["exempt_role_ids"]}
    if role.id not in role_ids:
        await interaction.response.send_message(
            f"{role.mention} is not currently exempt.", ephemeral=True
        )
        return

    role_ids.remove(role.id)
    guild_state["exempt_role_ids"] = sorted(role_ids)
    save_state(state)

    note = ""
    if guild_state["active"]:
        await apply_lock_to_guild(interaction.guild)
        note = " The active maintenance lock has been updated."
    await interaction.response.send_message(
        f"Removed {role.mention} from the exempt roles.{note}", ephemeral=True
    )


@exempt_group.command(name="list", description="List roles exempt from maintenance.")
@app_commands.checks.has_permissions(administrator=True)
async def exempt_list(interaction: discord.Interaction):
    guild_state = get_guild_state(interaction.guild)
    roles = [
        interaction.guild.get_role(int(role_id))
        for role_id in guild_state["exempt_role_ids"]
    ]
    roles = [role for role in roles if role is not None]
    if not roles:
        message = "No exempt roles are configured for this server."
    else:
        message = "Exempt roles: " + ", ".join(role.mention for role in roles)
    await interaction.response.send_message(message, ephemeral=True)


bot.tree.add_command(exempt_group)


@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = "You need Administrator permission to use this command."
    else:
        message = "The command failed. Check Clow's permissions and console logs."
        print(f"Slash command error: {error}")

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Add it to your .env file.")

bot.run(TOKEN)
