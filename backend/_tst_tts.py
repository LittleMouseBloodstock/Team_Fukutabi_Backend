import sys
print('python:', sys.executable)
from google.cloud import texttospeech
print('module file:', getattr(texttospeech, '__file__', None))
print('client:', texttospeech.TextToSpeechClient)
