import datetime

class ActionEngine:
    def __init__(self):
        # We don't need Spotify API keys here! 
        # Volco has the master token on the hardware.
        pass

    def execute(self, text: str):
        """
        Analyzes the text. If it's a command, returns:
        (Did I execute?, Response to speak, Command Payload for Volco)
        """
        text = text.lower().strip()

        # --- COMMAND 1: MUSIC PLAYBACK (SPOTIFY) ---
        if text.startswith("play"):
            query = text.replace("play", "").strip()
            
            # If you just say "Play", it resumes current music
            if not query or query in ["music", "some music"]:
                return True, "Resuming Spotify.", {"action": "spotify_resume", "query": None}
            
            # If you specify a playlist
            if query.startswith("playlist"):
                playlist_name = query.replace("playlist", "").strip()
                return True, f"Playing the playlist {playlist_name}.", {"action": "spotify_play_playlist", "query": playlist_name}
            
            # If you specify an album
            if query.startswith("album"):
                album_name = query.replace("album", "").strip()
                return True, f"Playing the album {album_name}.", {"action": "spotify_play_album", "query": album_name}
            
            # Default to playing a specific track/artist
            return True, f"Playing {query}.", {"action": "spotify_play_track", "query": query}

        # --- COMMAND 2: MUSIC CONTROLS ---
        if "next song" in text or "skip song" in text or "skip this" in text:
            return True, "Skipping to the next track.", {"action": "spotify_next", "query": None}

        if "previous song" in text or "go back" in text:
            return True, "Playing the previous track.", {"action": "spotify_previous", "query": None}

        if "pause music" in text or "stop music" in text:
            return True, "Pausing playback.", {"action": "spotify_pause", "query": None}

        # --- COMMAND 3: TIME & DATE ---
        if "what time" in text or "current time" in text:
            now = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"It is currently {now}.", {"action": "none"}

        if "what date" in text or "what's the date" in text:
            today = datetime.datetime.now().strftime("%A, %B %d")
            return True, f"Today is {today}.", {"action": "none"}

        # --- NOT A COMMAND (Send to LLM or regular chat) ---
        return False, "", {}