"""
CLI module for ImageSet Generator

Provides command-line interface and GUI for the ImageSet Generator.
"""

__all__ = ["main", "ImageSetGeneratorGUI"]


def __getattr__(name):
    if name == "main":
        from .launcher import main

        return main
    if name == "ImageSetGeneratorGUI":
        from .gui import ImageSetGeneratorGUI

        return ImageSetGeneratorGUI
    raise AttributeError(name)
