# Lively Captions

**Lively Captions** is a real-time speech transcription and translation desktop app built with Python. It captures your voice through a microphone or your computer audio, transcribes it using Whisper, and and also translates it into other languages.

---

## ✨ Features

| Feature                  | Description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| 🎙️ Live Transcription    | Converts speech to text using `faster-whisper` for fast, accurate results. |
| 🌐 Real-Time Translation | Translates transcribed text with `translators` into many languages.        |
| 🖼️ GUI Interface         | Built with `tkinter`, with customization options for fonts and colors.     |
| ⚙️ Non-blocking Threads  | Uses threading to keep the UI responsive during audio capture and processing.|

---

## 🧰 Requirements

Install the necessary packages using `pip`:

```bash
pip install sounddevice numpy faster-whisper translators
```
## 🚀 Usage
Run the main application file:

```bash
python lively_captions.py
```

## You’ll be able to:

Select the input audio device (microphone).
- Choose the translation language.
- Customize the font size and text color.
- Start and stop transcription with ease.

Made with 💖 by [Slyv](https://github.com/zSlyv)
