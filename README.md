# Discord Leveling & Utility Bot

A multi-purpose Discord bot featuring an **XP leveling system**, **temporary voice channels**, **basic moderation**, **auto-kick for users without roles**, and useful admin commands.
For now configurable only through in-app commands.

## Main Features

### Leveling System
- Earn 1 XP per message sent (commands excluded)
- 5 configurable levels with increasing XP thresholds
- Automatic role assignment upon reaching a new level
- Previous level role is automatically removed
- Congratulations message sent in the configured channel
- `/level` command to view your current level and progress (with progress bar)
- Ability to enable/disable leveling per server (`/leveling-toggle`)

### Temporary Voice Channels (TempVoice)
- Configurable "creator" voice channel
- When a user joins the creator channel → a personal voice channel is created with their name
- The user automatically becomes manager of their channel
- Channel is automatically deleted when empty

### Moderation & Utilities
- Configurable goodbye message when a member leaves the server
- Auto-kick after 48 hours for users with no roles (except @everyone)
  - Background task runs every 60 minutes
  - Can be disabled per server with `/bg-task-toggle`
- `/list-id @role` → downloads a .txt file containing IDs and names of all members with that role
- `/serverinfo` → displays server info + invite link (if configured)
- `/ping` → shows bot latency
- `/sync` → force global slash command sync (owner only)

## Command List

| Command               | Description                                                  | Required Permissions       |
|-----------------------|--------------------------------------------------------------|----------------------------|
| `/ping`               | Shows bot latency                                            | Everyone                   |
| `/serverinfo`         | Server info + invite link (if set)                           | Everyone                   |
| `/level` [member]     | Shows your or another user's level and XP                    | Everyone                   |
| `/list-id @role`      | Downloads a .txt with IDs and names of members with the role | Administrator              |
| `/config`             | Configure everything (channels, roles, links, etc.)          | Administrator              |
| `/config-show`        | Displays current server configuration                        | Administrator              |
| `/leveling-toggle`    | Enable/disable the leveling system                           | Administrator              |
| `/bg-task-toggle`     | Enable/disable the 48-hour auto-kick task                    | Administrator              |
| `/sync`               | Force sync of global slash commands                          | Bot Owner only             |

## Requirements

- Python 3.11+
- `discord.py >= v2.3.0`
- `python-dotenv`

## Installation

1. Install the required Python packages
```bash
pip install discord.py python-dotenv
```
2. Clone the repository
```bash
git clone https://github.com/your-username/your-bot-name.git
```
3. Create an `.env` file inside the root
```
BOT_TOKEN = your_bot_token_here
BOT_OWNER_ID = your_user_id_here
```
4. Save and start the bot
```
python bot.py
```
## File Structure
```
Root
├── bot.py                     → Main bot file
├── cogs/
│   ├── leveling.py            → XP system, config & level-up commands
│   ├── tempvoice.py           → Temporary voice channels
│   ├── moderation.py          → Goodbye messages
│   └── member_id.py           → /list-id command
├── data/                      → (auto-created on first launch)
│   ├── levels.json            → XP and level data per user/server
│   ├── config.json            → Leveling configuration per server
│   ├── moderation_config.json → Goodbye message channel
│   └── tempvoice_config.json  → Voice creator channel config
├── .env                       → Bot token & owner ID (never commit!)
└── README.md
```
## Required Bot Permissions
**Reccomended**: Invite the bot with Administrator privileges or grant the following permissions.
- Manage Channels (for TempVoice)
- Kick Members (for auto-kick background task)
- Manage Roles (for level role assignment)
- Send Messages / Embed
- Read Message History
- Move Members (voice channels)

## Notes
- The `data/` folder and JSON files are automatically created on first launch
- All the data is stored in easy-to-edit JSON files
- The 48-hour auto-kick ignores bots, server owners, and anyone with at least one role
