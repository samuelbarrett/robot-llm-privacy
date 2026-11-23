import random
import threading
import time

from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import SpeechRecognitionIU, TextIU
from sota_thinclient import ConnectionManager

from classes.conditional_update_message import ConditionalUpdateMessage
from classes.interruption import (
    HighSeverityRobotInterruption,
    LowSeverityRobotInterruption,
)
from classes.privacy_text_iu import PrivacyTextIU
from modules.ollama_output_parser_gate import OllamaOutputParserGate

"""
DialogManagerModule

The dialog manager orchestrates the robot's knowledge of and contributions to the conversation. 
It receives ASR input and other dialog information (e.g., whether private information may have been disclosed), 
and uses a rule-based approach to determine the appropriate response, which is executed by downstream LLM and TTS modules.
"""

INTERRUPTION_MAX_WAIT_FOR_EXPLANATION_S = 5.0

PROMPT_USER_SPEECH = "User said: {text}"
PROMPT_REDIRECT_TOPIC = (
    "Redirect conversation topic to a previous topic by asking a question."
)


class DialogManagerModule(AbstractModule):
    def __init__(
        self,
        sota: ConnectionManager,
        gate_module: OllamaOutputParserGate,
        llm_path: str,
        tts_path: str,
        **kwargs,
    ):
        super().__init__()
        self.sota = sota
        self.llm_gate_module: OllamaOutputParserGate = gate_module
        self.llm_path = llm_path
        self.tts_path = tts_path
        self.current_input = []

        self.active_interruption = None

    @staticmethod
    def name():
        return "DialogManager"

    @staticmethod
    def description():
        return "Dialog manager module that manages the flow of conversation and handles privacy-sensitive information and topic redirection."

    @staticmethod
    def input_ius():
        return PrivacyTextIU, SpeechRecognitionIU

    @staticmethod
    def output_iu():
        return TextIU

    def run(self):
        super().run()
        self.send_message("Hi there! How are you doing today?", self.tts_path)

    def process_update(self, update_message: UpdateMessage):
        for iu, ut in update_message:
            if isinstance(iu, PrivacyTextIU):
                if ut == UpdateType.ADD:
                    self.interruption_finalized = False
                    self.current_input.append(iu)
                    if iu.has_disclosure() and not self.active_interruption:
                        self.issue_interruption(iu.get_severity())
                if ut == UpdateType.REVOKE:
                    self.revoke(iu)
                if ut == UpdateType.COMMIT:
                    current = " ".join([iu.text for iu in self.current_input])
                    print(f"{self.name()}: COMMIT: {current}")
                    if self.active_interruption:
                        self.finalize_interruption()
                    else:
                        prompt = " ".join([iu.text for iu in self.current_input])
                        print(f"{self.name()}: Sending prompt to LLM: {prompt}")
                        self.respond(prompt)
                    self.current_input = []
            elif isinstance(iu, SpeechRecognitionIU):
                # check for end of utterance to signal interruption logic
                if ut == UpdateType.COMMIT:
                    if self.active_interruption:
                        self.finalize_interruption()

    def respond(self, prompt_input: str):
        """
        Respond to the user's speech input.
        """
        # TODO: call motion speaking
        prompt = PROMPT_USER_SPEECH.format(text=prompt_input)
        self.send_message(prompt, self.llm_path)

    def issue_interruption(
        self,
        severity: PrivacyTextIU.DisclosureSeverity = PrivacyTextIU.DisclosureSeverity.LOW,
    ):
        """
        Interrupt the current conversation flow and redirect the topic.
        """
        print(f"{self.name()}: Interrupt, severity={severity}")

        if not self.active_interruption:
            self.active_interruption = (
                LowSeverityRobotInterruption(self)
                if severity == PrivacyTextIU.DisclosureSeverity.LOW
                else HighSeverityRobotInterruption(self)
            )
            self.active_interruption.start()

            # generate topic redirection, but gate LLM output while interruption is active to avoid sending topic redirection while the user (or robot) is still speaking
            self.llm_gate_module.set_gate_open(False)
            self.send_message(PROMPT_REDIRECT_TOPIC, self.llm_path)
        else:
            print(
                f"{self.name()}: Interruption already active! Ignoring new interruption request."
            )

    def finalize_interruption(self):
        if self.active_interruption:
            self.active_interruption.handle_event("end_of_utterance")
            self.llm_gate_module.set_gate_open(
                True
            )  # end of utterance, now open gate for topic redirection
            self.active_interruption = None

    def send_message(self, text, condition):
        um = ConditionalUpdateMessage(condition=condition)
        words = text.split()
        for i, word in enumerate(words):
            update_iu = self.create_iu()
            update_iu.set_text(word)
            um.add_iu(update_iu, UpdateType.ADD)
            if i == len(words) - 1:
                um.add_iu(update_iu, UpdateType.COMMIT)
        self.append(um)
