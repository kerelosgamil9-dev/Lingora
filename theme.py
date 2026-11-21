# -*- coding: utf-8 -*-
"""
theme.py - colours for the dark / light themes.

Dark mode follows the spec exactly: background #151515, cards #1a1a1a.
Use C('name') everywhere; the screens are rebuilt when the theme changes.
"""

from kivy.utils import get_color_from_hex as hx

PALETTES = {
    'dark': {
        'bg': hx('#151515'),
        'card': hx('#1a1a1a'),
        'card2': hx('#242424'),
        'border': hx('#2b2b2b'),
        'input': hx('#202020'),
        'topbar': hx('#181818'),
        'text': hx('#F1F1F1'),
        'sub': hx('#A2A2A2'),
        'primary': hx('#5F82FF'),
        'on_primary': hx('#FFFFFF'),
        'accent': hx('#FFB547'),
        'success': hx('#34C98A'),
        'danger': hx('#F0566A'),
        'warn': hx('#FFB547'),
        'divider': hx('#505050'),
        'chip': hx('#272727'),
        'shadow': (0, 0, 0, 0.35),
    },
    'light': {
        'bg': hx('#F3F4F7'),
        'card': hx('#FFFFFF'),
        'card2': hx('#EEF0F5'),
        'border': hx('#E1E4EA'),
        'input': hx('#F1F3F7'),
        'topbar': hx('#FFFFFF'),
        'text': hx('#1C1D21'),
        'sub': hx('#6B7080'),
        'primary': hx('#3F63E6'),
        'on_primary': hx('#FFFFFF'),
        'accent': hx('#F29A1F'),
        'success': hx('#1FAF74'),
        'danger': hx('#E2394F'),
        'warn': hx('#F29A1F'),
        'divider': hx('#AEB4C4'),
        'chip': hx('#E8EAF0'),
        'shadow': (0, 0, 0, 0.12),
    },
}

# Transparent "marker pen" colours.  Index 0 = no highlight.
HIGHLIGHTS = [
    None,
    (1.00, 0.92, 0.20, 0.50),   # yellow
    (0.40, 0.90, 0.45, 0.42),   # green
    (1.00, 0.45, 0.72, 0.42),   # pink
    (0.35, 0.72, 1.00, 0.45),   # blue
    (1.00, 0.62, 0.20, 0.50),   # orange
    (0.72, 0.52, 1.00, 0.45),   # purple
]

FOLDER_COLORS = [
    hx('#5F82FF'), hx('#FF7A7A'), hx('#34C98A'), hx('#FFB547'),
    hx('#B57BFF'), hx('#38BDF8'), hx('#F472B6'), hx('#A3E635'),
]


class _Theme:
    mode = 'dark'

    def set_mode(self, mode):
        self.mode = mode if mode in PALETTES else 'dark'

    @property
    def is_dark(self):
        return self.mode == 'dark'

    def c(self, name):
        return list(PALETTES[self.mode][name])


THEME = _Theme()


def C(name):
    """Colour by name for the active theme (returns a fresh list)."""
    return THEME.c(name)


def alpha(color, a):
    c = list(color)
    c[3] = a
    return c


def mix(c1, c2, t):
    """Linear mix of two RGBA colours."""
    return [c1[i] + (c2[i] - c1[i]) * t for i in range(4)]
