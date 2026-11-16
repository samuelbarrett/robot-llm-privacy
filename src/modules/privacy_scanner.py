from collections import deque
import queue
import threading

from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import SpeechRecognitionIU, TextIU
from pydantic import BaseModel
from ollama import chat

from classes.privacy_text_iu import PrivacyTextIU

"""
PrivacyScannerModule

Parse SpeechRecognitionIU objects for potential privacy-sensitive information using an LLM.
If a private disclosure is detected, the module flags this for downstream modules to handle appropriately.

Supports two modes of detection:
 - keyword: keyword-based detection from a list of known/decided privacy-sensitive words
 - llm: uses an LLM to infer potential disclosures of private information
"""


POLL_INTERVAL = 0.1  # seconds
SCAN_CHUNK_MAX_SIZE = 8  # max IUs to send to the LLM at once
PRIVACY_VIOLATION_WORDS = [
    "password",
    "social security number",
    "credit card",
    "bank account",
    "address",
    "phone number",
]


class PrivacyScannerModule(AbstractModule):
    def __init__(self, model: str, system_prompt: str, mode: str = "llm", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode
        self.model = model
        self.system_prompt = system_prompt
        self.scan_queue = queue.Queue()
        self.end_of_utterance_received = False
        self.list_lock = threading.Lock()
        self.worker_thread = threading.Thread(
            target=self.worker_loop, args=(), daemon=True
        )
        self._stop_event = threading.Event()

    @staticmethod
    def name():
        return "PrivacyScanner"

    @staticmethod
    def description():
        return "A module that scans text for privacy-sensitive information."

    @staticmethod
    def input_ius():
        return SpeechRecognitionIU

    @staticmethod
    def output_iu():
        return PrivacyTextIU

    def run(self):
        super().run()
        self.worker_thread.start()

    def process_update(self, update_message: UpdateMessage):
        """
        send ADD IUs to the worker thread for processing in chunks, passing each chunk downstream once processed.
        use COMMIT IUs to signal the end of an utterance.
        """
        for iu, ut in update_message:
            if ut == UpdateType.ADD:
                self.scan_queue.put((iu, ut))
                self.end_of_utterance_received = False
            elif ut == UpdateType.REVOKE:
                self.revoke(iu)
            elif ut == UpdateType.COMMIT:
                if not self.end_of_utterance_received:
                    self.scan_queue.put((iu, ut))
                    self.end_of_utterance_received = True

    def worker_loop(self):
        batch = []
        end_of_utterance = False

        while not self._stop_event.is_set():
            try:
                iu, ut = self.scan_queue.get(timeout=POLL_INTERVAL)
                if ut == UpdateType.COMMIT:
                    end_of_utterance = True
                else:
                    batch.append((iu, ut))

                if end_of_utterance or len(batch) >= SCAN_CHUNK_MAX_SIZE:
                    if self.mode == "llm":
                        disclosure_detected = self.disclosure_scan_llm(batch)
                    elif self.mode == "keyword":
                        disclosure_detected = self.disclosure_scan_text(batch)
                    else:
                        raise ValueError(
                            f"Unknown mode: {self.mode}. Acceptablel values are llm or keyword."
                        )
                    um = self.build_update_message(batch, disclosure_detected)

                    if end_of_utterance:
                        end_of_utterance = False
                        um.add_iu(self.create_iu(iu), UpdateType.COMMIT)

                    self.append(um)
                    batch = []
            except queue.Empty:
                continue

    def disclosure_scan_text(self, batch) -> bool:
        # Simple keyword-based detection for privacy-sensitive information
        text = " ".join([iu.text for iu, ut in batch if ut == UpdateType.ADD])
        for word in PRIVACY_VIOLATION_WORDS:
            if word in text.lower():
                return True
        return False

    def disclosure_scan_llm(self, batch) -> bool:
        # use ollama chat API to detect privacy-sensitive information in the text
        text = " ".join([iu.text for iu, ut in batch if ut == UpdateType.ADD])
        response = chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt,
                },
                {"role": "user", "content": text},
            ],
            format=PrivacyResult.model_json_schema(),
        )
        result = PrivacyResult.model_validate_json(response.message.content)
        return result.has_privacy_violation

    def build_update_message(self, batch, disclosure_detected) -> UpdateMessage:
        um = UpdateMessage()
        for iu, ut in batch:
            update_iu: PrivacyTextIU = self.create_iu(iu)
            update_iu.set_text(iu.text)
            update_iu.set_severity(
                PrivacyTextIU.DisclosureSeverity.LOW
                if disclosure_detected
                else PrivacyTextIU.DisclosureSeverity.NONE
            )
            um.add_iu(update_iu, ut)
        return um

    def shutdown(self):
        self._stop_event.set()
        super().shutdown()


class PrivacyResult(BaseModel):
    """
    Simple pydantic class for LLM structured output
    """
    has_privacy_violation: bool
