import datetime
import webbrowser
import subprocess

class ActionEngine:
    def __init__(self):
        pass

    def execute(self, text: str):
        """
        Analyzes the text. If it's a command, executes it and returns (True, Response).
        If it's normal conversation, returns (False, "").
        """
        text = text.lower().strip()

        # --- COMMAND: MUSIC ---
        if text.startswith("play"):
            song = text.replace("play", "").strip()
            if not song: return True, "What should I play?"
            
            url = f"https://www.youtube.com/results?search_query={song.replace(' ', '+')}"
            webbrowser.open(url)
            return True, f"Playing {song}."

        # --- COMMAND: TIME ---
        if "what time" in text or "current time" in text:
            now = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"It is currently {now}."

        # --- COMMAND: DATE ---
        if "what date" in text or "what's the date" in text:
            today = datetime.datetime.now().strftime("%A, %B %d")
            return True, f"Today is {today}."

        # --- COMMAND: SYSTEM ---
        if "open calculator" in text:
            subprocess.Popen('calc.exe')
            return True, "Opening Calculator."

        # --- NOT A COMMAND ---
        return False, ""