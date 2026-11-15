import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sota_thinclient import ConnectionManager
from retico_huggingfacelm.huggingface_lm_module import HuggingfaceLMModule
from retico_huggingfacelm.huggingface_lm_client import HuggingfaceLMClient
from retico_ollama import OllamaModule

from src.modules.ollama_output_parser import OllamaOutputParser
from sota_retico.debug_utils import text_candidate_callback
from sota_retico.audio_filter import AudioGatingModule
from sota_retico import SotaMicrophoneModule
from sota_retico import SotaSpeakerModule
from retico_whisperasr import WhisperASRModule
from retico_speechbraintts import  SpeechBrainTTSModule
import retico_core
import torch

# SOTA_IP = "10.0.0.178"
SOTA_IP = "10.151.63.77"
HTTP_PORT = "8080"
MIC_UDP_PORT = 52001
SPEAKER_UDP_PORT = 52002
OLLAMA_MODEL = "llama3.2:1b"

sota = ConnectionManager(SOTA_IP, HTTP_PORT)

#################initialize the retico modules
microphone_module = SotaMicrophoneModule(sota, MIC_UDP_PORT, buffer_ms=20)
speaker_module = SotaSpeakerModule(sota, SPEAKER_UDP_PORT)
text_callback_module = retico_core.debug.CallbackModule(callback=text_candidate_callback)

print("Starting Whisper ASR...", end="")
asr_module = WhisperASRModule()
print("done.")

print("Starting SpeechBrains...", end="")
tts_module = SpeechBrainTTSModule(language="en")
print("done.")

ollama_module = OllamaModule(
    model=OLLAMA_MODEL,
    system_prompt="You are a grumpy Wizard who talks very little. Limit your responses to 1 short sentence.",
    temperature=0.2,
)
ollama_text_parser_module = OllamaOutputParser()
print("Done")

self_filter_module = AudioGatingModule(tts_module, sleep_interval=0.001)

#################setup the connections
microphone_module.subscribe(self_filter_module)
self_filter_module.subscribe(asr_module)
asr_module.subscribe(ollama_module)
asr_module.subscribe(text_callback_module)
ollama_module.subscribe(ollama_text_parser_module)
ollama_text_parser_module.subscribe(tts_module)
tts_module.subscribe(speaker_module)
tts_module.subscribe(self_filter_module)

##################start everyone
speaker_module.run()
self_filter_module.run()
text_callback_module.run()
tts_module.run()
asr_module.run()
microphone_module.run()
ollama_module.run()
ollama_text_parser_module.run()

print("go")
input()   # wait for user key

#clean up and stop
microphone_module.stop()
asr_module.stop()
tts_module.stop()
speaker_module.stop()
self_filter_module.stop()
text_callback_module.stop()
ollama_module.stop()
ollama_text_parser_module.stop()