import os

# This tells the bot to look for Railway's secure environment variable first.
# If it doesn't find it, it falls back to the local string.
TOKEN: str = os.getenv("TOKEN", "YOUR_BOT_TOKEN_HERE")

# TTS Settings
TTS_VOICE: str = "en-US-AriaNeural" 

# Embed Colors
COLOR_SUCCESS: int = 0x2ECC71
COLOR_ERROR: int = 0xE74C3C
COLOR_INFO: int = 0x3498DB
