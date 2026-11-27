from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import TextIU

from classes.conditional_update_message import ConditionalUpdateMessage


class ConditionalModule(AbstractModule):
    def __init__(self, condition: str, **kwargs):
        super().__init__(**kwargs)
        self.conditional_update_message_type = condition

    @staticmethod
    def name():
        return "ConditionalModule"

    @staticmethod
    def input_ius():
        return TextIU

    @staticmethod
    def output_iu():
        return TextIU

    def process_update(self, update_message: ConditionalUpdateMessage):
        """
        Process the update message and check if the condition is met.
        If the condition is met, set the condition_met flag to True.
        """
        if update_message.get_condition() == self.conditional_update_message_type:
            if self.conditional_update_message_type == "tts":
                # log TTS output
                prompt = " ".join([iu.text for iu, ut in update_message if ut == UpdateType.ADD])
                print(f"{self.name()}: {self.conditional_update_message_type}: {prompt}")
            um = UpdateMessage()
            for iu, ut in update_message:
                um.add_iu(iu, ut)
            return um