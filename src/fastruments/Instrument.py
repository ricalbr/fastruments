# This is an interface that any instrument has to implement.
from abc import ABC, abstractmethod


class Instrument(ABC):

    def __init__(self):
        super().__init__()

    @abstractmethod
    def connect(self):
        """Connect to the instrument"""
        pass

    @abstractmethod
    def close(self):
        """Close connection with the instrument"""
        pass
