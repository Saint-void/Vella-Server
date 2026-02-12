import os
from huggingface_hub import snapshot_download

# 1. Define the model repository and your local target directory
MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
TARGET_DIR = "V:/Document/Vella-Modes/models/TinyLlama-1.1B-Chat-v1.0"

# 2. Create the directory if it doesn't exist
os.makedirs(TARGET_DIR, exist_ok=True)

print(f"⏳ Downloading {MODEL_ID} to {TARGET_DIR}...")
print("This may take a few minutes depending on your internet speed.")

# 3. Download the model (Snapshot ensures we get config, tokenizer, and safetensors)
try:
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=TARGET_DIR,
        local_dir_use_symlinks=False,  # Important for Windows to ensure actual files are downloaded
        resume_download=True
    )
    print("\n✅ Download Complete!")
    print(f"Model saved to: {TARGET_DIR}")

except Exception as e:
    print(f"\n❌ Error downloading model: {e}")