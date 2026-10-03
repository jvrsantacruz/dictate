"""The GNOME on Wayland adapter: wl-clipboard, a key sender, and the IBus engine.

Every module here but `focus` and `component` imports `gi`, which comes from
apt and is absent from the development venv, so the unit tests stop at those
two.
"""
