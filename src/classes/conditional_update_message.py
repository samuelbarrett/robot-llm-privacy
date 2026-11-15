from retico_core import UpdateMessage

class ConditionalUpdateMessage(UpdateMessage):
    """
    A conditional IU that is only activated when a certain condition is met.
    It wraps another IU along with a condition variable.
    """

    def __init__(self, condition: str, **kwargs):
        super().__init__(**kwargs)
        self.condition = condition

    def get_um(self) -> UpdateMessage:
        return self.um

    def get_condition(self) -> str:
        return self.condition