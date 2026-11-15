from retico_core import AbstractModule, UpdateMessage
from retico_core.audio import AudioIU

import numpy as np


class AudioGatingModule(AbstractModule):
    ENERGY_KEY = "energy"
    START_TALKING_THRESH = 20

    def __init__(self, speech_gen_module, **kwargs):
        super().__init__(**kwargs)
        self._is_talking = None
        self._speech_gen_module = speech_gen_module

    @staticmethod
    def name():
        return "Simple Audio Gating Module"

    @staticmethod
    def description():
        return "A simple filter that suppresses IUs from the microphone while the speaker has output."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return AudioIU

    def process_update(self, update_message):
        output_update = UpdateMessage()
        has_ius = False

        for iu, ut in update_message:
            if iu.creator == self._speech_gen_module:
                self._update_is_talking_check(
                    self._rms_energy(iu.raw_audio, iu.sample_width)
                )
            elif not self._is_talking:
                output_iu = self.create_iu(iu)
                output_iu.set_audio(iu.raw_audio, iu.nframes, iu.rate, iu.sample_width)
                output_update.add_iu(output_iu, ut)
                has_ius = True

        if has_ius:
            self.append(output_update)

    def _update_is_talking_check(self, energy):
        talking = energy > self.START_TALKING_THRESH

        if talking:
            if self._is_talking is None or not self._is_talking:
                print("is speaking changed to: true")
                self._is_talking = True
        elif self._is_talking is None or self._is_talking:
            print("is speaking changed to: false")
            self._is_talking = False

    @staticmethod
    def _rms_energy(audio_bytes, sample_width_bytes):
        sample_width_bits = sample_width_bytes * 8
        samples = np.frombuffer(audio_bytes, dtype=np.dtype(f"int{sample_width_bits}"))
        return np.sqrt(np.mean(samples.astype(np.float64) ** 2))
