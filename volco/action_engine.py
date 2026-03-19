import datetime
import urllib.parse

class ActionEngine:
    def execute(self, text: str):
        """
        Analyzes the text. If it's a command, returns:
        (Did I execute?, Response to speak, Command Payload for Volco)
        """
        text = text.lower().strip()

        # --- COMMAND 1: MUSIC PLAYBACK (SPOTIFY) ---
        if text.startswith("play"):
            query = text.replace("play", "").strip()
            if not query:
                # Just say "Play" → resume
                return True, "Resuming Spotify.", {"action": "spotify_resume", "query": None}

            # Album command
            if "album" in query:
                album_name = query.replace("album", "").replace("for me", "").strip()
                return True, f"Playing the album {album_name}.", {"action": "spotify_play_album", "query": album_name}

            # Playlist command
            if "playlist" in query:
                playlist_name = query.replace("playlist", "").replace("for me", "").strip()
                return True, f"Playing the playlist {playlist_name}.", {"action": "spotify_play_playlist", "query": playlist_name}

            # Default: track/artist
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

        # --- NOT A COMMAND ---
        return False, "", {}
