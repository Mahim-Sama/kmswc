"""KMSWC - Kinetic Model of Solid Waste Composting.

A clean-architecture redesign of the original two-step model script. Layers:

* ``domain``       - pure physics, parameters, time-series and mass balance.
* ``application``  - orchestrates the two stages and the stage-1 -> stage-2 hand-off.
* ``presentation`` - matplotlib figure builder and the Tkinter GUI.

The engine (domain + application) has no GUI dependency and can be driven from a
script or a test; the GUI is one possible front-end.

Original author of the model: Zarif Tanzim Aziz (KUET CE 2k18),
supervised by Prof. Dr. Quazi Hamidul Bari.
"""
