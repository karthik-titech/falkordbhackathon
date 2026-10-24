"""Bounded, on-demand OpenAI speech for opening lines and message drafts."""
import json
from urllib.request import Request, urlopen

API_URL = "https://api.openai.com/v1/audio/speech"
# Speech endpoint supported until Jan 2027; migrate to Realtime before sunset.
MODEL = "gpt-4o-mini-tts"
MAX_TEXT = 800
MAX_AUDIO_BYTES = 2_000_000


def validate_text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ValueError("Enter a message between 1 and 800 characters.")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
        raise ValueError("Message contains unsupported characters.")
    return value.strip()


def speech_client(api_key, transport=None):
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Voice requires a configured API key.")
    transport = transport or urlopen

    def speak(text):
        text = validate_text(text)
        request = Request(API_URL, data=json.dumps({
            "model": MODEL, "voice": "coral", "input": text,
            "response_format": "mp3",
            "instructions": "Speak warmly and naturally, like rehearsing a conversation opener. Do not add words.",
        }).encode(), headers={"Authorization": "Bearer " + api_key,
                              "Content-Type": "application/json"}, method="POST")
        try:
            with transport(request, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
                audio = response.read(MAX_AUDIO_BYTES + 1)
                if content_type not in ("audio/mpeg", "audio/mp3", "application/octet-stream"):
                    raise RuntimeError("Unexpected speech response")
                if not audio or len(audio) > MAX_AUDIO_BYTES:
                    raise RuntimeError("Invalid audio length")
                return audio
        except Exception:
            # Provider errors may contain request details. Never expose them.
            raise RuntimeError("Voice is unavailable right now. Please try again.") from None
    return speak


def transcription_client(api_key, transport=None):
    """Upload a bounded microphone clip; retain neither file nor transcript."""
    import secrets
    transport = transport or urlopen
    def transcribe(audio, content_type):
        formats = {'audio/webm': 'webm', 'audio/mp4': 'mp4', 'audio/ogg': 'ogg', 'audio/mpeg': 'mp3', 'audio/wav': 'wav'}
        if content_type not in formats or not isinstance(audio, bytes) or not 0 < len(audio) <= 5_000_000:
            raise ValueError('Use a short supported audio recording.')
        boundary = 'audio' + secrets.token_hex(18)
        fields = (f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\ngpt-transcribe\r\n'
                  f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.{formats[content_type]}"\r\n'
                  f'Content-Type: {content_type}\r\n\r\n').encode()
        request = Request('https://api.openai.com/v1/audio/transcriptions', data=fields + audio + f'\r\n--{boundary}--\r\n'.encode(),
                          headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'multipart/form-data; boundary=' + boundary}, method='POST')
        try:
            with transport(request, timeout=45) as response:
                result = json.loads(response.read(40_000))
            return validate_text(result.get('text'))
        except Exception:
            raise RuntimeError('Could not transcribe that recording. Try again or type your request.') from None
    return transcribe
