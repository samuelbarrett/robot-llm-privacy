from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import TextIU
from retico_ollama import ResponseEndIU

"""
Parse output from the retico-ollama module to produce clean TextIU-based update messages, dropping the custom ResponseEndIU which other modules (e.g., retico-speechbraintts) do not handle.
"""

class OllamaOutputParser(AbstractModule):

    @staticmethod
    def name():
        return "OllamaOutputParser"

    @staticmethod
    def description():
        return "Cleans up output from retico-ollama."

    @staticmethod
    def input_ius():
        return [TextIU, ResponseEndIU]

    @staticmethod
    def output_iu():
        return TextIU

    def process_update(self, update_message):
        downstream_message = UpdateMessage()
        response_complete = False
        
        for iu, ut in update_message:
            if isinstance(iu, ResponseEndIU):
                # end of LLM response, commit current_output
                response_complete = True
                continue
            elif isinstance(iu, TextIU):
                if ut == UpdateType.ADD:
                    self.current_output.append(iu)
                    downstream_message.add_iu(iu, UpdateType.ADD)
                elif ut == UpdateType.REVOKE:
                    self.revoke(iu)
                    downstream_message.add_iu(iu, UpdateType.REVOKE)
                
        if response_complete:
            for iu in self.current_output:
                iu.committed = True
                downstream_message.add_iu(iu, UpdateType.COMMIT)
            self.current_output = []
        return downstream_message