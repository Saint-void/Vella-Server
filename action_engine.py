import os
import datetime
import webbrowser
import subprocess

class ActionEngine:
    def __init__(self):
        # You can add API keys here later (e.g., Spotify)
        pass

    def execute(self, text: str):
        """
        Analyzes the text. If it matches a command, executes it.
        Returns: (bool, str) -> (Did I execute a command?, Response to speak)
        """
        text = text.lower().strip()

        # --- COMMAND 1: MUSIC (Simple Web Browser Fallback) ---
        if text.startswith("play"):
            song = text.replace("play", "").strip()
            if not song: return True, "What should I play?"
            
            # For Phase 1, we just open YouTube. Phase 2 = Spotify API.
            url = f"https://www.youtube.com/results?search_query={song.replace(' ', '+')}"
            webbrowser.open(url)
            return True, f"Playing {song} on YouTube."

        # --- COMMAND 2: TIME ---
        if "what time" in text or "current time" in text:
            now = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"It is currently {now}."

        # --- COMMAND 3: DATE ---
        if "what date" in text or "what's the date" in text:
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return True, f"Today is {today}."

        # --- COMMAND 4: SYSTEM COMMANDS ---
        if "open calculator" in text:
            subprocess.Popen('calc.exe')
            return True, "Opening Calculator."
        
        if "shutdown system" in text:
             # Safety check: Don't actually shut down during testing!
            return True, "I cannot shut down your system for safety reasons."

        # --- NO COMMAND MATCHED ---
        return False, ""