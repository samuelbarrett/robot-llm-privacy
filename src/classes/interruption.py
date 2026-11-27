import threading
import time
import random

# interjections based on severity of privacy disclosure
LOW_INTERRUPTION_TEXTS = [
    "Hey! Sorry.",
    "Um, excuse me.",
    "Hey, um, sorry.",
    "Wait, hold on a second.",
    "Sorry to interrupt.",
]
HIGH_INTERRUPTION_TEXTS = [
    "Stop!",
    "Wait, wait, wait!",
    "Woah, woah, hold on!",
]

# explanations of the reasoning for the interruption
LOW_EXPLANATION_TEXTS = [
    "I don't think I should know about that.",
    "I think you might consider keeping that information private.",
    "It's okay, I don't need to know that.",
    "How about we talk about something else?",
]
HIGH_EXPLANATION_TEXTS = [
    "That might be private information that you should not share with me.",
    "Let's not go there.",
    "I'd rather not get into that.",
    "Let's move on to a different topic.",
]

LOW_SEVERITY_INTERRUPTION_MAX_WAIT_FOR_EXPLANATION_S = 8.0


class RobotInterruption:
    """Defines an interruption logic flow used by the dialog manager to handle robot interruptions."""

    timeout_s: float = 8.0
    
    def __init__(self, dm):
        self.dm = dm
        self.done = False

    def start(self):
        self.start_time = time.monotonic()
        pass

    def handle_event(self, event):
        pass


class LowSeverityRobotInterruption(RobotInterruption):
    """Represents a low severity robot interruption."""

    def start(self):
        super().start()
        self.dm.send_message(random.choice(LOW_INTERRUPTION_TEXTS), self.dm.tts_path)
        
    def handle_event(self, event):
        if event == "end_of_utterance" and time.monotonic() - self.start_time <= LOW_SEVERITY_INTERRUPTION_MAX_WAIT_FOR_EXPLANATION_S:
            self.done = True
            self.dm.send_message(random.choice(LOW_EXPLANATION_TEXTS), self.dm.tts_path)
            self.dm.llm_gate_module.set_gate_open(True)


class HighSeverityRobotInterruption(RobotInterruption):
    """Represents a high severity robot interruption."""
    
    time_between_interruption_attempts_s: float = 4.0

    def start(self):
        super().start()
        self.dm.send_message(random.choice(HIGH_INTERRUPTION_TEXTS), self.dm.tts_path)
        self.time_since_last_interruption = time.monotonic()
        self.timer_thread = threading.Thread(target=self.repeat_interruption_timer).start()
        self.stop_event = threading.Event()
        
    def repeat_interruption_timer(self):
        while not self.stop_event.is_set():
            time.sleep(0.1)
            if time.monotonic() - self.time_since_last_interruption >= self.time_between_interruption_attempts_s:
                self.time_since_last_interruption = time.monotonic()
                self.handle_event("interrupt_again")
        
    def handle_event(self, event):
        if event == "end_of_utterance":
            self.done = True
            self.stop_event.set()
            self.dm.send_message(random.choice(HIGH_EXPLANATION_TEXTS), self.dm.tts_path)
            self.dm.llm_gate_module.set_gate_open(True)
            
        elif event == "interrupt_again":
            if not self.done:
                self.dm.send_message(random.choice(HIGH_INTERRUPTION_TEXTS), self.dm.tts_path)
