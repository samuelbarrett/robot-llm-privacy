from collections import deque
import queue
import threading
import time

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
    def __init__(self, model: str, system_prompt: str, mode: str = "llm", debug: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.mode = mode
        self.model = model
        self.system_prompt = system_prompt
        self.debug = debug
        self.scan_queue = queue.Queue()
        self.end_of_utterance_received = False
        self.iu_revocation_lock = threading.Lock() # lock read/write of revoke state
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
                self.current_input.append(iu) # only append so we can revoke later if needed
                self.scan_queue.put((iu, ut))
                self.end_of_utterance_received = False
            elif ut == UpdateType.REVOKE:
                with self.iu_revocation_lock:
                    self.revoke(iu, remove_revoked=False)
            elif ut == UpdateType.COMMIT:
                if not self.end_of_utterance_received:
                    self.scan_queue.put((iu, ut))
                    self.end_of_utterance_received = True
                    self.current_input.clear()

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
                    um = UpdateMessage()
                    with self.iu_revocation_lock:
                        # only process unrevoked ADD IUs
                        process_batch = [(iu, ut) for iu, ut in batch if (not iu.revoked and ut == UpdateType.ADD)]
                    
                    if process_batch:
                        disclosure_detected = self.disclosure_scan_llm(process_batch) if self.mode == "llm" else self.disclosure_scan_text(process_batch)
                        um = self.populate_update_message(um, batch, disclosure_detected) # include revoked IUs in update message

                    if end_of_utterance:
                        end_of_utterance = False
                        um.add_iu(self.create_iu(iu), UpdateType.COMMIT)

                    self.append(um)
                    batch = []
            except queue.Empty:
                continue

    def disclosure_scan_text(self, batch) -> bool:
        # Simple keyword-based detection for privacy-sensitive information
        text = " ".join([iu.text for iu, ut in batch])
        for word in PRIVACY_VIOLATION_WORDS:
            if word in text.lower():
                return True
        return False

    def disclosure_scan_llm(self, batch) -> bool:
        # use ollama chat API to detect privacy-sensitive information in the text
        text = " ".join([iu.text for iu, ut in batch])
        start_time = time.perf_counter()
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
        end_time = time.perf_counter()
        if self.debug:
            print(f"{self.name()}: Inference on {len(batch)} IUs took {end_time - start_time:.4f} seconds.")
        
        result = PrivacyResult.model_validate_json(response.message.content)
        return result.has_privacy_violation

    def populate_update_message(self, um: UpdateMessage, batch: list, disclosure_detected: bool) -> UpdateMessage:
        for iu, ut in batch:
            update_iu: PrivacyTextIU = self.create_iu(iu)
            update_iu.set_text(iu.text)
            if ut == UpdateType.ADD and not update_iu.revoked:
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
