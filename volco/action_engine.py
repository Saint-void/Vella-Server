import datetime
import re


def _clean_music_query(query: str) -> str:
    query = re.sub(r"\b(on|with)\s+spotify\b", "", query)
    query = re.sub(r"\b(for me|please|now)\b", "", query)
    return query.strip(" .,!?'\"")


def _extract_music_query(text: str) -> str:
    patterns = [
        r"^(?:please\s+)?play\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?play\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?put\s+on\s+(.+)$",
        r"^(?:please\s+)?put\s+on\s+(.+)$",
        r"^(?:please\s+)?start\s+playing\s+(.+)$",
        r"^i\s+(?:want|wanna|would\s+like)\s+to\s+(?:listen\s+to|hear|play)\s+(.+)$",
        r"^let'?s\s+(?:listen\s+to|hear|play)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return _clean_music_query(match.group(1))

    return ""


class ActionEngine:
    def execute(self, text: str):
        """
        Analyzes the text. If it's a command, returns:
        (Did I execute?, Response to speak, Command Payload for Volco)
        """
        text = text.lower().strip()

        # --- COMMAND 1: MUSIC PLAYBACK (SPOTIFY) ---
        query = _extract_music_query(text)
        if query or text == "play":
            if not query or query in {"music", "some music", "my music"}:
                # Just say "Play" -> resume
                return True, "Certainly. Resuming your music on Spotify.", {"action": "spotify_resume", "query": ""}

            # Album command
            if "album" in query:
                album_name = query.replace("album", "").replace("for me", "").strip()
                return True, f"Of course. Playing the album {album_name} for you.", {"action": "spotify_play_album", "query": album_name}

            # Playlist command
            if "playlist" in query:
                playlist_name = query.replace("playlist", "").replace("for me", "").strip()
                return True, f"I'd be happy to. Playing the playlist {playlist_name}.", {"action": "spotify_play_playlist", "query": playlist_name}

            # Default: track/artist
            return True, f"Certainly. Playing {query} for you.", {"action": "spotify_play_track", "query": query}

        # --- COMMAND 2: MUSIC CONTROLS ---
        # Resuming (Play music, Resume, Resume track)
        if text == "resume" or "resume music" in text or "resume song" in text or "resume track" in text or text == "play music":
            return True, "Certainly. Resuming your music on Spotify.", {"action": "spotify_resume", "query": ""}

        # Next Track (Next song, Next track, Skip song, Skip track, Skip this)
        if "next song" in text or "next track" in text or "skip song" in text or "skip track" in text or "skip this" in text:
            return True, "Certainly. Skipping to the next track.", {"action": "spotify_next", "query": ""}

        # Previous Track (Previous song, Previous track, Go back)
        if "previous song" in text or "previous track" in text or "go back" in text:
            return True, "Of course. Playing the previous track.", {"action": "spotify_previous", "query": ""}

        # Pause/Stop (Pause music, Pause track, Pause song, Stop music, Stop track)
        if "pause" in text or "stop music" in text or "stop track" in text or "stop song" in text:
            return True, "Certainly. Pausing your music.", {"action": "spotify_pause", "query": ""}

        # --- COMMAND 3: TIME & DATE ---
        if "what time" in text or "current time" in text:
            now = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"Of course. It is currently {now}.", {"action": "none"}

        if "what date" in text or "what's the date" in text:
            today = datetime.datetime.now().strftime("%A, %B %d")
            return True, f"Certainly. Today is {today}.", {"action": "none"}

        # --- NOT A COMMAND ---
        return False, "", {}
