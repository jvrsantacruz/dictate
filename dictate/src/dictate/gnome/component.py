"""The IBus component file that makes the engine an input source.

IBus reads it from its component directory. The file names the program and
asks it for the engine's description, so the layout comes from the user's
config at the moment IBus builds its registry, and one file installed for the
whole machine serves any layout. The package installs it; the headless tests
point a private IBus at their own copy.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape, quoteattr

from dictate.gnome.bus import NAME

ENGINE = "dictate"
# What a GNOME XKB id may hold. Anything else is not written into the XML.
_LAYOUT = re.compile(r"[a-z0-9_]+(\+[a-z0-9_-]+)?")


def xml(program: str) -> str:
    """The component, with `program` as the engine and as its describer."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Installed by the dictate package. -->
<component>
  <name>{NAME}</name>
  <description>Dictation: inserts text, types like the plain layout</description>
  <exec>{escape(program)} engine --ibus</exec>
  <version>0.1.0</version>
  <author>jvrsantacruz</author>
  <license>GPL-3.0-or-later</license>
  <homepage>https://github.com/jvrsantacruz/dictate</homepage>
  <textdomain></textdomain>
  <engines exec={quoteattr(program + " engines")}/>
</component>
"""


def valid_layout(layout: str) -> bool:
    """Whether `layout` is the shape of a GNOME XKB id, such as `us+intl`."""
    return bool(_LAYOUT.fullmatch(layout))


def engines(layout: str) -> str:
    """The engine's description, typing on `layout`.

    `layout` is a whole GNOME XKB id such as `us+intl`, written into `layout`
    and not split into `layout_variant`: GNOME Shell 50 reads the variant from
    `engineDesc.variant`, which IBus does not have, so a variant given apart
    would be dropped, and the dead keys with it.
    """
    return f"""<engines>
  <engine>
    <name>{ENGINE}</name>
    <language>en</language>
    <license>GPL-3.0-or-later</license>
    <author>jvrsantacruz</author>
    <icon></icon>
    <layout>{escape(layout)}</layout>
    <longname>Dictation</longname>
    <description>The {escape(layout)} layout, with dictation</description>
    <rank>0</rank>
    <symbol>D</symbol>
  </engine>
</engines>
"""
