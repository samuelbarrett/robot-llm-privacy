import threading

from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import TextIU
from retico_ollama import ResponseEndIU

"""
Parse output from the retico-ollama module to produce clean TextIU-based update messages, dropping the custom ResponseEndIU which other modules (e.g., retico-speechbraintts) do not handle.
Provides a gate function to open/close the flow of text downstream, used by the dialog manager.
"""

class OllamaOutputParserGate(AbstractModule):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gate_open = threading.Event()
        self.gate_open.set()

    @staticmethod
    def name():
        return "OllamaOutputParserGate"

    @staticmethod
    def description():
        return "Cleans up output from retico-ollama."

    @staticmethod
    def input_ius():
        return [TextIU, ResponseEndIU]

    @staticmethod
    def output_iu():
        return TextIU
    
    def set_gate_open(self, set: bool):
        if set:
            self.gate_open.set()
        else:
            self.gate_open.clear()

    def process_update(self, update_message):
        """
        This module conforms to retico-ollama's response structure:
         - one full response per update_message
         - once we hit a COMMIT IU, we know the message
         - Append one COMMIT to the list of ADD IU accumulated and send downstream
        """
        for iu, ut in update_message:
            if isinstance(iu, TextIU):
                if ut == UpdateType.ADD:
                    self.current_output.append(iu)
                elif ut == UpdateType.REVOKE:
                    self.revoke(iu)
                elif ut == UpdateType.COMMIT:
                    um = UpdateMessage()
                    for current_iu in self.current_output:
                        um.add_iu(current_iu, UpdateType.ADD)
                    um.add_iu(iu, UpdateType.COMMIT)
                    
                    self.gate_open.wait()  # block until gate is open
                    print(f"{self.name()}: sending message: '{' '.join([iu.text for iu in self.current_output])}'")
                    self.append(um)
                    self.current_output = []
                    break