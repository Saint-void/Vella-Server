import os
from huggingface_hub import snapshot_download

# 1. The exact folder path you want
local_path = r"V:/Document/Vella-Modes/models/models--distil-whisper--distil-large-v3/snapshots/latest"

# 2. The Repo ID for the CTranslate2 version of Distil-Large-V3
# (This is the specific format faster-whisper needs)
repo_id = "Systran/faster-distil-whisper-small-v3"

print(f"🚀 Downloading {repo_id}...")
print(f"📂 Destination: {local_path}")

try:
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_path,
        local_dir_use_symlinks=False, # Downloads actual files, not links
        allow_patterns=["config.json", "model.bin", "vocabulary.json"] # Get only essential files
    )
    print("\n✅ Download Complete!")
    print("You can now run your router.")

except Exception as e:
    print(f"\n❌ Error: {e}")