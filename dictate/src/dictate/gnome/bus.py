"""The session bus interface between `dictate` and its engine."""

# The engine's name on both buses: IBus's, as its component, and the session's.
NAME = "io.github.jvrsantacruz.Dictate"
PATH = "/io/github/jvrsantacruz/Dictate"
INTERFACE = "io.github.jvrsantacruz.Dictate.Engine"

# IBus input purposes of fields that hold secrets: password and PIN.
SECRET_PURPOSES = (8, 9)

# Focus: the token, whether an input holds focus, and its IBus input purpose.
# Commit: insert `text` only if focus is still `token`; false otherwise.
# Preedit: show `text` as not yet typed, on the same terms; empty clears it.
# Active: whether the engine is the input source in use; with another one
# chosen it sees no focus.
INTROSPECTION = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Focus">
      <arg direction="out" type="s" name="token"/>
      <arg direction="out" type="b" name="focused"/>
      <arg direction="out" type="u" name="purpose"/>
    </method>
    <method name="Active">
      <arg direction="out" type="b" name="active"/>
    </method>
    <method name="Preedit">
      <arg direction="in" type="s" name="text"/>
      <arg direction="in" type="s" name="token"/>
      <arg direction="out" type="b" name="shown"/>
    </method>
    <method name="Commit">
      <arg direction="in" type="s" name="text"/>
      <arg direction="in" type="s" name="token"/>
      <arg direction="out" type="b" name="committed"/>
    </method>
  </interface>
</node>
"""
