import urllib.request
import zipfile
import os

# 1. Setup Path
DEST_DIR = r"V:/Document/Vella-Modes/models/vosk"
if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)

# 2. URL for the BIG English Model (1.8 GB)
# This is "vosk-model-en-us-0.22" - The accurate one.
URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
FILE_NAME = "model.zip"
FILE_PATH = os.path.join(DEST_DIR, FILE_NAME)

print(f"⬇️ Downloading Vosk Giant Model (1.8 GB)... This will take time.")

try:
    # 3. Download
    urllib.request.urlretrieve(URL, FILE_PATH)
    print("✅ Download complete.")

    # 4. Extract
    print("📦 Extracting...")
    with zipfile.ZipFile(FILE_PATH, 'r') as zip_ref:
        zip_ref.extractall(DEST_DIR)
    
    print(f"✅ Extracted! Ready at: {DEST_DIR}")
    
    # 5. Cleanup
    os.remove(FILE_PATH)

except Exception as e:
    print(f"❌ Error: {e}")