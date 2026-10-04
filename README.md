# 🦉 Night Owl JEE Buddy

A tiny, fully offline JEE doubt-solver I built for my friend who is in his drop year and studies all night.

- **Ask** a Physics / Chemistry / Maths doubt (type it or snap a photo) and get a step-by-step explanation.
- **Revise**: every doubt is logged on the laptop. Get fresh practice problems on your weak spots.
- **Weekend**: a random cook-together dish + horror movie for our Saturday nights.

Everything runs locally with open-weight models through [Ollama](https://ollama.com). No API keys, no cloud, no monthly bill.

## Run it

1. Install Ollama, then pull the models:
   ```
   ollama pull qwen3:8b
   ollama pull qwen2.5vl:7b
   ```
2. Start the app (Python 3.8+, nothing to pip install):
   ```
   python server.py
   ```
3. Open the `http://localhost:8000` link it prints, or open the "phone" link on a phone connected to the same Wi-Fi.

If the phone can't connect, allow Python through the Windows firewall for private networks.

## Swap the models

```
TEXT_MODEL=llama3.1:8b VISION_MODEL=gemma3:4b python server.py
```

On Windows PowerShell: `$env:TEXT_MODEL="llama3.1:8b"; python server.py`

Tested target: RTX 5050 8 GB, 24 GB RAM. Both models fit in 8 GB VRAM (one is loaded at a time).

## Files

- `server.py`: small standard-library server that talks to Ollama and keeps the doubt log in `doubts.json`
- `static/index.html`: the whole mobile-friendly UI in one file
