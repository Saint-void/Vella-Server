import mlx_whisper
import ollama

# 1. Define your audio source
# (Assuming your assistant script records a 'user_voice.wav' file)
audio_input = "user_voice.wav"

print("Listening completed. Transcribing with M4 GPU...")

# 2. Transcribe the audio natively on Apple Silicon
# SWEET SPOT: "mlx-community/whisper-large-v3-turbo" (Highly accurate, very fast)
# LUDICROUS SPEED: "mlx-community/whisper-base" (Instant transcription, slightly less accurate)
transcription = mlx_whisper.transcribe(
    audio_input, 
    path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
)

user_text = transcription["text"]
print(f"\n🗣️ User: {user_text}")

print("\nThinking...")

# 3. Feed the text directly into your local Ollama LLM
# (Swap 'llama3' with whatever model you have pulled in Ollama)
response = ollama.chat(model='qwen2.5:3b', messages=[
    {
        'role': 'user',
        'content': user_text,
    },
])

print(f"\n🤖 Assistant: {response['message']['content']}")