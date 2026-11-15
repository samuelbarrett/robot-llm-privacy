from retico_core import AbstractModule, UpdateMessage, UpdateType
from retico_core.text import TextIU

from classes.conditional_update_message import ConditionalUpdateMessage
from classes.privacy_text_iu import PrivacyTextIU

"""
DialogManagerModule

The dialog manager orchestrates the robot's knowledge of and contributions to the conversation. 
It receives ASR input and other dialog information (e.g., whether private information may have been disclosed), 
and uses a rule-based approach to determine the appropriate response, which is executed by downstream LLM and TTS modules.
"""


PROMPT_USER_SPEECH = "User said: {text}"
INTERRUPTION_TEXT = "Hey! Sorry, I don't think I should know about that."
PROMPT_HANDLE_DISCLOSURE = (
    "Redirect conversation topic to a previous topic by asking a question."
)


class DialogManagerModule(AbstractModule):
    def __init__(self, llm_path: str, tts_path: str, **kwargs):
        super().__init__()
        self.llm_path = llm_path
        self.tts_path = tts_path
        self.disclosure_handling = False
        self.current_input = []

    @staticmethod
    def name():
        return "DialogManager"

    @staticmethod
    def description():
        return "Dialog manager module that manages the flow of conversation and handles privacy-sensitive information and topic redirection."

    @staticmethod
    def input_ius():
        return PrivacyTextIU

    @staticmethod
    def output_iu():
        return TextIU

    def process_update(self, update_message: UpdateMessage):
        for iu, ut in update_message:
            if ut == UpdateType.ADD:
                print(
                    f"{self.name()}: Received ADD IU: {iu.text}, severity: {iu.get_severity()}"
                )
                self.current_input.append(iu)
                if iu.has_disclosure() and not self.disclosure_handling:
                    self.interrupt_and_redirect(severity=iu.get_severity())
                    self.disclosure_handling = True
            if ut == UpdateType.COMMIT:
                current = " ".join([iu.text for iu in self.current_input])
                print(f"{self.name()}: Received COMMIT for current input: {current}")
                if not self.disclosure_handling:
                    prompt = " ".join([iu.text for iu in self.current_input])
                    self.respond(prompt)
                self.current_input = []
                self.disclosure_handling = False

    def respond(self, prompt_input: str):
        """
        Respond to the user's speech input.
        """
        # TODO: call motion speaking
        # TODO: send context to LLM to generate response
        prompt = PROMPT_USER_SPEECH.format(text=prompt_input)
        self.send_message(prompt, self.llm_path)

    def interrupt_and_redirect(
        self,
        severity: PrivacyTextIU.DisclosureSeverity = PrivacyTextIU.DisclosureSeverity.LOW,
    ):
        """
        Interrupt the current conversation flow and redirect the topic.
        """
        print(f"{self.name()}: Interrupting conversation due to privacy disclosure with severity: {severity}")

        # 1. interrupt the user
        # TODO: call motion interrupt
        self.send_message(INTERRUPTION_TEXT, self.tts_path)

        # 2. handle the disclosure
        # TODO: call LLM to stop generating response
        self.send_message(PROMPT_HANDLE_DISCLOSURE, self.llm_path)

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
