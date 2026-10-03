"""The session bus interface between `dictate` and its engine."""

# The engine's name on both buses: IBus's, as its component, and the session's.
NAME = "io.github.jvrsantacruz.Dictate"
PATH = "/io/github/jvrsantacruz/Dictate"
INTERFACE = "io.github.jvrsantacruz.Dictate.Engine"

# Focus: the token, whether an input holds focus, and its IBus input purpose.
# Commit: insert `text` only if focus is still `token`; false otherwise.
INTROSPECTION = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Focus">
      <arg direction="out" type="s" name="token"/>
      <arg direction="out" type="b" name="focused"/>
      <arg direction="out" type="u" name="purpose"/>
    </method>
    <method name="Commit">
      <arg direction="in" type="s" name="text"/>
      <arg direction="in" type="s" name="token"/>
      <arg direction="out" type="b" name="committed"/>
    </method>
  </interface>
</node>
"""
