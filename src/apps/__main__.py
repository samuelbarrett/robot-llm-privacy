import torch
import retico_core
from pathlib import Path
from modules.conditional_module import ConditionalModule
from modules.ollama_output_parser import OllamaOutputParser
from modules.privacy_scanner import PrivacyScannerModule
from modules.dialog_manager import DialogManagerModule
from sota_retico.audio_filter import AudioGatingModule
from sota_retico import SotaMicrophoneModule, SotaSpeakerModule
from sota_thinclient import ConnectionManager
from sota_retico.debug_utils import text_candidate_callback
from retico_whisperasr import WhisperASRModule
from retico_speechbraintts import SpeechBrainTTSModule
from retico_ollama import OllamaModule

# SOTA_IP = "10.151.63.77"
SOTA_IP = "10.0.0.178"
HTTP_PORT = "8080"
MIC_UDP_PORT = 52001
SPEAKER_UDP_PORT = 52002
MIC_BUFFER_MS = 20
AUDIO_GATE_SLEEP_INTERVAL = 0.001
OLLAMA_MODEL = "llama3.2:1b"
SYSTEM_ROLE = Path("config/system_role.txt").read_text(encoding="utf-8").strip()

LLM_PATH_CONDITION = "llm"
TTS_PATH_CONDITION = "tts"

sota = ConnectionManager(SOTA_IP, HTTP_PORT)

mic = SotaMicrophoneModule(sota, MIC_UDP_PORT, buffer_ms=MIC_BUFFER_MS)
speaker = SotaSpeakerModule(sota, SPEAKER_UDP_PORT)
text_callback = retico_core.debug.CallbackModule(callback=text_candidate_callback)

asr = WhisperASRModule()
tts = SpeechBrainTTSModule(language="en")
audio_filter = AudioGatingModule(tts, sleep_interval=AUDIO_GATE_SLEEP_INTERVAL)
privacy_scanner = PrivacyScannerModule()

llm_forwarder = ConditionalModule(condition=LLM_PATH_CONDITION)
tts_forwarder = ConditionalModule(condition=TTS_PATH_CONDITION)

dm = DialogManagerModule(llm_path=LLM_PATH_CONDITION, tts_path=TTS_PATH_CONDITION)

ollama = OllamaModule(
    model=OLLAMA_MODEL,
    system_prompt=SYSTEM_ROLE,
    temperature=0.7,
)
ollama_parser = OllamaOutputParser()


mic.subscribe(audio_filter)
audio_filter.subscribe(asr)
asr.subscribe(privacy_scanner)
asr.subscribe(text_callback)
privacy_scanner.subscribe(dm)
dm.subscribe(tts_forwarder)
dm.subscribe(llm_forwarder)
llm_forwarder.subscribe(ollama)
tts_forwarder.subscribe(tts)
ollama.subscribe(ollama_parser)
ollama_parser.subscribe(tts)
tts.subscribe(speaker)
tts.subscribe(audio_filter)

speaker.run()
audio_filter.run()
text_callback.run()
tts.run()
asr.run()
mic.run()
ollama.run()
ollama_parser.run()
llm_forwarder.run()
tts_forwarder.run()
dm.run()
privacy_scanner.run()

print("started. press enter to stop")
input()

speaker.stop()
audio_filter.stop()
text_callback.stop()
tts.stop()
asr.stop()
mic.stop()
ollama.stop()
ollama_parser.stop()
llm_forwarder.stop()
tts_forwarder.stop()
dm.stop()
privacy_scanner.stop()
