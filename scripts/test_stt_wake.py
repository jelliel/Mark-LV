import sys
sys.path.insert(0, r'C:\Users\toshr\AppData\Local\Programs\MarkLV')

from core.stt import WhisperSTT, VoskSTT
from core.wake_word import WakeWordDetector, is_ready

print('STT modules available?', bool(WhisperSTT and VoskSTT))
print('Wake model ready:', is_ready())

# Try starting wake listener
wd = WakeWordDetector(lambda: print('Detected'))
print('Starting WakeWordDetector:', wd.start())
print('Is running:', wd._running)

# Instantiate Whisper (will download if not cached)
whisper = WhisperSTT('tiny', language='en')
print('Whisper ready')