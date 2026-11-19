from enum import Enum, StrEnum

from retico_core.text import TextIU

class PrivacyTextIU(TextIU):
    """An incremental unit representing a private disclosure in the dialog."""
    
    class DisclosureSeverity(StrEnum):
        NONE = "none"
        LOW = "low"
        HIGH = "high"
    
    @staticmethod
    def type():
        return "Disclosure IU"
        
    def __init__(self, final=False, severity=DisclosureSeverity.NONE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.severity = severity
        self.final = final

    def get_severity(self):
        return self.severity
    
    def set_severity(self, severity: DisclosureSeverity):
        self.severity = severity
        
    def set_final(self, final: bool):
        self.final = final

    def has_disclosure(self):
        return self.severity != self.DisclosureSeverity.NONE