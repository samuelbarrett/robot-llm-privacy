import ollama
import retico_core
from pathlib import Path
from modules.conditional_module import ConditionalModule
from modules.ollama_output_parser_gate import OllamaOutputParserGate
from modules.privacy_scanner import PrivacyScannerModule
from modules.dialog_manager import DialogManagerModule
from sota_retico import SotaMicrophoneModule, SotaSpeakerModule
from sota_retico.audio_filter import AudioGatingModule
from sota_thinclient import ConnectionManager
from sota_retico.debug_utils import text_candidate_callback
from retico_whisperasr import WhisperASRModule
from retico_speechbraintts import SpeechBrainTTSModule
from retico_ollama import OllamaModule

SOTA_IP = "10.151.63.77"
# SOTA_IP = "10.0.0.178"
HTTP_PORT = "8080"
MIC_UDP_PORT = 52001
SPEAKER_UDP_PORT = 52002
MIC_BUFFER_MS = 20
AUDIO_GATE_SLEEP_INTERVAL = 0.001
DIALOG_MODEL = "llama3.2:1b"
PRIVACY_SCANNER_MODEL = "qwen3:0.6b"
DIALOG_SYSTEM_ROLE = Path("config/dialog_system_role.txt").read_text(encoding="utf-8").strip()
PRIVACY_SCANNER_SYSTEM_ROLE = Path("config/privacy_scanner_system_role.txt").read_text(encoding="utf-8").strip()

LLM_PATH_CONDITION = "llm"
TTS_PATH_CONDITION = "tts"

# load models so they're cached
ollama.generate(model=DIALOG_MODEL, prompt="", keep_alive=-1)
ollama.generate(model=PRIVACY_SCANNER_MODEL, prompt="", keep_alive=-1)

sota = ConnectionManager(SOTA_IP, HTTP_PORT)

mic = SotaMicrophoneModule(sota, MIC_UDP_PORT, buffer_ms=MIC_BUFFER_MS)
speaker = SotaSpeakerModule(sota, SPEAKER_UDP_PORT)
text_callback = retico_core.debug.CallbackModule(callback=text_candidate_callback)

asr = WhisperASRModule()
tts = SpeechBrainTTSModule(language="en")
audio_filter = AudioGatingModule(tts, sleep_interval=AUDIO_GATE_SLEEP_INTERVAL)
privacy_scanner = PrivacyScannerModule(mode="llm", model=PRIVACY_SCANNER_MODEL, system_prompt=PRIVACY_SCANNER_SYSTEM_ROLE, debug=False)
llm_forwarder = ConditionalModule(condition=LLM_PATH_CONDITION)
tts_forwarder = ConditionalModule(condition=TTS_PATH_CONDITION)

ollama_module = OllamaModule(
    model=DIALOG_MODEL,
    system_prompt=DIALOG_SYSTEM_ROLE,
    temperature=0.7,
)
ollama_parser_gate = OllamaOutputParserGate()

dm = DialogManagerModule(sota=sota, gate_module=ollama_parser_gate, llm_path=LLM_PATH_CONDITION, tts_path=TTS_PATH_CONDITION)


mic.subscribe(audio_filter)
audio_filter.subscribe(asr)
asr.subscribe(privacy_scanner)
asr.subscribe(text_callback)
asr.subscribe(dm)
privacy_scanner.subscribe(dm)
dm.subscribe(tts_forwarder)
dm.subscribe(llm_forwarder)
llm_forwarder.subscribe(ollama_module)
tts_forwarder.subscribe(tts)
ollama_module.subscribe(ollama_parser_gate)
ollama_parser_gate.subscribe(tts)
tts.subscribe(speaker)
tts.subscribe(audio_filter)

speaker.run()
audio_filter.run()
text_callback.run()
tts.run()
asr.run()
mic.run()
ollama_module.run()
ollama_parser_gate.run()
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
ollama_module.stop()
ollama_parser_gate.stop()
llm_forwarder.stop()
tts_forwarder.stop()
dm.stop()
privacy_scanner.stop()
