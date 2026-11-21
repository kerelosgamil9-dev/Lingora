# -*- coding: utf-8 -*-
"""
widgets.py - the reusable UI toolkit of Lingora (pure Kivy, no KivyMD).

ALabel        Arabic-aware label (shaping, bidi, wrapping, highlighter)
RButton       rounded button
Icon / IconButton   vector icons drawn with the canvas (no icon fonts)
Card, Divider, BarProgress, Toggle, Segmented, ColorDots
FlameWidget   the streak fire with real fire colours
ATextInput, FormField   text inputs with live Arabic preview
Dialog, Toast, NavDrawer, TopBar
"""

import math

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, InstructionGroup, Line, Mesh,
                           Rectangle, RoundedRectangle)
try:                                    # present in every normal Kivy build
    from kivy.graphics.tesselator import Tesselator, WINDING_ODD, TYPE_POLYGONS
except Exception:                       # noqa: BLE001 - fallback drawing is used
    Tesselator = None
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, OptionProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import rtl
from theme import C, alpha, mix


# ======================================================================
# helpers
# ======================================================================
_core_cache = {}


def measure_text(text, font_name, font_size, bold=False):
    """Pixel width of a single line of text with the given font."""
    key = (font_name, round(float(font_size), 1), bool(bold))
    cl = _core_cache.get(key)
    if cl is None:
        cl = CoreLabel(font_name=font_name, font_size=font_size, bold=bold)
        _core_cache[key] = cl
    try:
        return cl.get_extents(text)[0]
    except Exception:
        return len(text) * font_size * 0.55


def is_rtl():
    return rtl.UI_RTL


def vbox(**kw):
    """Vertical box whose height follows its content."""
    kw.setdefault('size_hint_y', None)
    b = BoxLayout(orientation='vertical', **kw)
    b.bind(minimum_height=b.setter('height'))
    return b


def hbox(height=None, **kw):
    """Horizontal box with a fixed height."""
    if height is not None:
        kw['size_hint_y'] = None
        kw['height'] = height
    return BoxLayout(orientation='horizontal', **kw)


def add_row(box, widgets):
    """Add widgets in reading order (reversed automatically in RTL mode)."""
    for w in (reversed(list(widgets)) if rtl.UI_RTL else widgets):
        box.add_widget(w)
    return box


def spacer(w=None, h=None):
    kw = {}
    if w is not None:
        kw.update(size_hint_x=None, width=w)
    if h is not None:
        kw.update(size_hint_y=None, height=h)
    return Widget(**kw)


def label(text='', size=15, color='text', bold=False, align='auto', wrap=True,
          autoheight=True, **kw):
    """Factory for the most common label configuration."""
    col = kw.pop('color_rgba', None) or C(color)
    if wrap:
        kw.setdefault('size_hint_y', None)
        if not autoheight:
            kw.setdefault('height', dp(size * 2))
    return ALabel(raw=text, font_size=sp(size), color=col, bold=bold,
                  align=align, wrap=wrap, autoheight=autoheight, **kw)


# ======================================================================
# ALabel
# ======================================================================
class ALabel(Label):
    """Label that draws Arabic correctly and can paint a marker highlight.

    raw        logical text (what the user typed / what is stored)
    align      auto | left | right | center   (auto follows the text direction)
    wrap       word-wrap inside the widget width
    autoheight resize the widget height to the wrapped text (needs wrap=True)
    fit        resize the widget to the text (single line)
    hl         RGBA list painted behind the text like a highlighter pen
    """

    raw = StringProperty('')
    align = OptionProperty('auto', options=('auto', 'left', 'right', 'center'))
    wrap = BooleanProperty(False)
    autoheight = BooleanProperty(False)
    fit = BooleanProperty(False)
    hl = ListProperty([])

    def __init__(self, **kw):
        raw = kw.pop('raw', kw.pop('text', ''))
        kw.setdefault('markup', False)
        super().__init__(**kw)
        self._hl_group = InstructionGroup()
        self.canvas.before.add(self._hl_group)
        self._trig = Clock.create_trigger(self._refresh, -1)
        self._trig_hl = Clock.create_trigger(self._draw_hl, -1)
        self.bind(raw=self._trig, width=self._trig, height=self._trig,
                  font_size=self._trig, font_name=self._trig, align=self._trig,
                  wrap=self._trig, bold=self._trig, fit=self._trig,
                  hl=self._trig_hl, pos=self._trig_hl, size=self._trig_hl,
                  texture_size=self._on_texture_size)
        self.raw = raw
        self._refresh()

    # -- layout / text ----------------------------------------------------
    def _refresh(self, *args):
        raw = self.raw or ''
        base_rtl = rtl.base_is_rtl(raw)
        align = self.align
        if align == 'auto':
            align = 'right' if base_rtl else 'left'
        self.halign = align
        px, py = self.padding_x, self.padding_y
        if self.wrap:
            avail = max(1.0, self.width - 2 * px)
            self.text_size = (avail, None)
            self.valign = 'top' if self.autoheight else 'middle'
            if self.width > 1 and rtl.ENABLED and rtl.has_rtl(raw):
                fn, fs, bd = self.font_name, self.font_size, self.bold
                self.text = rtl.wrap_display(
                    raw, avail - 3, lambda s: measure_text(s, fn, fs, bd), base_rtl)
            else:
                self.text = raw
        elif self.fit:
            self.text_size = (None, None)
            self.text = rtl.display(raw, base_rtl)
        else:
            self.text_size = (max(1.0, self.width - 2 * px),
                              max(1.0, self.height - 2 * py))
            self.valign = 'middle'
            self.shorten = True
            self.text = rtl.display(raw, base_rtl)
        self._trig_hl()

    def _on_texture_size(self, *args):
        tw, th = self.texture_size
        if self.fit:
            self.size = (tw + 2 * self.padding_x, th + 2 * self.padding_y)
        elif self.wrap and self.autoheight:
            new_h = th + 2 * self.padding_y
            if abs(new_h - self.height) > 0.5:
                self.height = new_h
        self._trig_hl()

    # -- marker highlight --------------------------------------------------
    def _draw_hl(self, *args):
        self._hl_group.clear()
        if not self.hl or not self.text:
            return
        tw, th = self.texture_size
        if tw <= 1 or th <= 1:
            return
        lines = self.text.split('\n')
        n = len(lines)
        lh = th / float(n)
        x0 = self.center_x - tw / 2.0
        y_top = self.center_y + th / 2.0
        pad = dp(4)
        self._hl_group.add(Color(*self.hl))
        for i, ln in enumerate(lines):
            if not ln.strip():
                continue
            w = measure_text(ln, self.font_name, self.font_size, self.bold)
            if self.halign == 'right':
                x = x0 + tw - w
            elif self.halign == 'center':
                x = x0 + (tw - w) / 2.0
            else:
                x = x0
            y = y_top - (i + 1) * lh
            self._hl_group.add(RoundedRectangle(
                pos=(x - pad, y + lh * 0.08), size=(w + 2 * pad, lh * 0.84),
                radius=[dp(5)]))


# ======================================================================
# Icons
# ======================================================================
def _star_points(cx, cy, ro, ri):
    pts = []
    for k in range(10):
        ang = math.pi / 2 + k * math.pi / 5
        r = ro if k % 2 == 0 else ri
        pts += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
    return pts


_SPEAKER = [('R', .14, .38, .16, .24),
            ('F', [.30, .38, .52, .20, .52, .80, .30, .62])]

ICONS = {
    'menu': [('L', [.15, .28, .85, .28]), ('L', [.15, .50, .85, .50]),
             ('L', [.15, .72, .85, .72])],
    'back': [('L', [.80, .50, .22, .50]), ('L', [.46, .76, .22, .50, .46, .24])],
    'chevron': [('L', [.36, .22, .66, .50, .36, .78])],
    'plus': [('L', [.50, .20, .50, .80]), ('L', [.20, .50, .80, .50])],
    'close': [('L', [.24, .24, .76, .76]), ('L', [.24, .76, .76, .24])],
    'check': [('L', [.20, .52, .42, .30, .80, .72])],
    'speaker': _SPEAKER + [('A', .50, .50, .20, 45, 135), ('A', .50, .50, .34, 45, 135)],
    'mute': _SPEAKER + [('L', [.64, .36, .88, .64]), ('L', [.64, .64, .88, .36])],
    'edit': [('L', [.26, .26, .70, .70]), ('L', [.62, .78, .78, .62]),
             ('T', .14, .14, .22, .36, .36, .22)],
    'trash': [('L', [.20, .76, .80, .76]), ('L', [.40, .76, .40, .86, .60, .86, .60, .76]),
              ('L', [.28, .70, .32, .15, .68, .15, .72, .70]),
              ('L', [.45, .60, .45, .28]), ('L', [.55, .60, .55, .28])],
    'star': [('STAR',)],
    'marker': [('F', [.28, .38, .62, .72, .80, .54, .46, .20]),
               ('T', .28, .38, .46, .20, .16, .16), ('L', [.12, .08, .56, .08])],
    'search': [('C', .43, .57, .24), ('L', [.62, .38, .84, .16])],
    'home': [('L', [.12, .50, .50, .86, .88, .50]),
             ('L', [.22, .46, .22, .14, .78, .14, .78, .46]),
             ('L', [.42, .14, .42, .38, .58, .38, .58, .14])],
    'folder': [('LC', [.10, .20, .10, .78, .40, .78, .48, .66, .90, .66, .90, .20])],
    'levels': [('R', .14, .14, .20, .26), ('R', .40, .14, .20, .46), ('R', .66, .14, .20, .68)],
    'bolt': [('F', [.58, .92, .22, .46, .52, .46]), ('F', [.42, .08, .78, .54, .48, .54]),
             ('R', .38, .44, .24, .12)],
    'gear': [('C', .50, .50, .18)] + [
        ('L', [.50 + .27 * math.cos(k * math.pi / 4), .50 + .27 * math.sin(k * math.pi / 4),
               .50 + .40 * math.cos(k * math.pi / 4), .50 + .40 * math.sin(k * math.pi / 4)])
        for k in range(8)],
    'lock': [('R', .24, .14, .52, .38), ('A', .50, .54, .17, -90, 90),
             ('L', [.33, .54, .33, .46]), ('L', [.67, .54, .67, .46])],
    'replay': [('A', .50, .48, .30, 40, 340), ('T', .72, .88, .88, .66, .56, .66)],
    'download': [('L', [.50, .85, .50, .32]), ('L', [.30, .50, .50, .30, .70, .50]),
                 ('L', [.20, .16, .80, .16])],
    'upload': [('L', [.50, .30, .50, .83]), ('L', [.30, .65, .50, .85, .70, .65]),
               ('L', [.20, .16, .80, .16])],
    'play': [('F', [.30, .18, .30, .82, .82, .50])],
    'book': [('LC', [.10, .26, .50, .18, .90, .26, .90, .78, .50, .70, .10, .78]),
             ('L', [.50, .18, .50, .70])],
    'dot': [('D', .50, .50, .22)],
}


class Icon(Widget):
    """Vector icon. Shapes are described in a unit square (see ICONS)."""

    name = StringProperty('')
    color = ListProperty([1, 1, 1, 1])
    mirror = BooleanProperty(False)
    filled = BooleanProperty(False)
    lw = NumericProperty(dp(1.9))

    def __init__(self, **kw):
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, name=self._trig, color=self._trig,
                  mirror=self._trig, filled=self._trig, lw=self._trig)
        self._trig()

    def _draw(self, *args):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s <= 1:
            return
        ox = self.center_x - s / 2.0
        oy = self.center_y - s / 2.0
        mir = self.mirror

        def X(x):
            return ox + ((1 - x) if mir else x) * s

        def Y(y):
            return oy + y * s

        def pts(seq):
            out = []
            for i in range(0, len(seq), 2):
                out += [X(seq[i]), Y(seq[i + 1])]
            return out

        def fan(seq):
            p = pts(seq)
            verts = []
            for i in range(0, len(p), 2):
                verts += [p[i], p[i + 1], 0, 0]
            return Mesh(vertices=verts, indices=list(range(len(p) // 2)),
                        mode='triangle_fan')

        lw = self.lw
        with self.canvas:
            Color(*self.color)
            for cmd in ICONS.get(self.name, []):
                k = cmd[0]
                if k == 'L':
                    Line(points=pts(cmd[1]), width=lw, cap='round', joint='round')
                elif k == 'LC':
                    Line(points=pts(cmd[1]), width=lw, cap='round', joint='round', close=True)
                elif k == 'F':
                    fan(cmd[1])
                elif k == 'T':
                    fan(list(cmd[1:]))
                elif k == 'A':
                    Line(circle=(X(cmd[1]), Y(cmd[2]), cmd[3] * s, cmd[4], cmd[5]),
                         width=lw, cap='round')
                elif k == 'C':
                    Line(circle=(X(cmd[1]), Y(cmd[2]), cmd[3] * s), width=lw)
                elif k == 'D':
                    r = cmd[3] * s
                    Ellipse(pos=(X(cmd[1]) - r, Y(cmd[2]) - r), size=(2 * r, 2 * r))
                elif k == 'R':
                    Rectangle(pos=(X(cmd[1]) if not mir else X(cmd[1] + cmd[3]), Y(cmd[2])),
                              size=(cmd[3] * s, cmd[4] * s))
                elif k == 'STAR':
                    sp_ = _star_points(.5, .52, .44, .19)
                    if self.filled:
                        p = pts(sp_)
                        verts = [X(.5), Y(.52), 0, 0]
                        for i in range(0, len(p), 2):
                            verts += [p[i], p[i + 1], 0, 0]
                        verts += [p[0], p[1], 0, 0]
                        Mesh(vertices=verts, indices=list(range(len(verts) // 4)),
                             mode='triangle_fan')
                    else:
                        Line(points=pts(sp_), width=lw, cap='round', joint='round', close=True)


class IconButton(ButtonBehavior, Icon):
    """Icon with a soft round press feedback."""

    bg = ListProperty([])           # optional filled circle behind the icon

    def __init__(self, **kw):
        super().__init__(**kw)
        self._ov = InstructionGroup()
        self.canvas.before.add(self._ov)
        self.bind(state=self._on_state, pos=self._ov_draw, size=self._ov_draw, bg=self._ov_draw)
        self._ov_draw()

    def _ov_draw(self, *a):
        self._ov.clear()
        s = min(self.width, self.height)
        if s <= 1:
            return
        if self.bg:
            self._ov.add(Color(*self.bg))
            self._ov.add(Ellipse(pos=(self.center_x - s / 2, self.center_y - s / 2), size=(s, s)))
        if self.state == 'down':
            self._ov.add(Color(1, 1, 1, 0.14))
            self._ov.add(Ellipse(pos=(self.center_x - s / 2, self.center_y - s / 2), size=(s, s)))

    def _on_state(self, *a):
        self._ov_draw()


# ======================================================================
# Containers
# ======================================================================
class Card(BoxLayout):
    """Rounded surface with a subtle border."""

    bg = ListProperty([])
    border = ListProperty([])
    radius = NumericProperty(dp(18))

    def __init__(self, bg_name='card', **kw):
        self._bg_name = bg_name
        kw.setdefault('orientation', 'vertical')
        kw.setdefault('padding', dp(14))
        kw.setdefault('spacing', dp(8))
        super().__init__(**kw)
        with self.canvas.before:
            self._c_bg = Color(*(self.bg or C(bg_name)))
            self._r_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._c_bd = Color(*(self.border or C('border')))
            self._l_bd = Line(rounded_rectangle=(self.x, self.y, self.width, self.height,
                                                 self.radius), width=1)
        self.bind(pos=self._upd, size=self._upd, bg=self._upd, border=self._upd,
                  radius=self._upd)

    def _upd(self, *a):
        self._c_bg.rgba = self.bg or C(self._bg_name)
        self._c_bd.rgba = self.border or C('border')
        self._r_bg.pos = self.pos
        self._r_bg.size = self.size
        self._r_bg.radius = [self.radius]
        self._l_bd.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)


class TapCard(ButtonBehavior, Card):
    """Card that can be tapped (children such as icon buttons still work)."""


def auto_card(**kw):
    """Card whose height follows its content."""
    kw.setdefault('size_hint_y', None)
    c = Card(**kw)
    c.bind(minimum_height=c.setter('height'))
    return c


class Divider(Widget):
    """Visual separator between list items. Shape / thickness / colour are
    controlled from the Settings screen (solid, dashed, dotted, fade, ornament)."""

    style = StringProperty('solid')
    thickness = NumericProperty(1)
    color = ListProperty([0.5, 0.5, 0.5, 1])

    _grad = None

    @classmethod
    def gradient(cls):
        if cls._grad is None:
            n = 64
            buf = bytearray()
            for i in range(n):
                a = math.sin(math.pi * i / (n - 1))
                buf += bytes([255, 255, 255, int(255 * a)])
            tex = Texture.create(size=(n, 1), colorfmt='rgba')
            tex.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
            tex.mag_filter = 'linear'
            cls._grad = tex
        return cls._grad

    def __init__(self, **kw):
        kw.setdefault('size_hint_y', None)
        kw.setdefault('height', dp(14))
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, style=self._trig,
                  thickness=self._trig, color=self._trig)
        self._trig()

    def _draw(self, *a):
        self.canvas.clear()
        w, h = self.size
        if w <= 2:
            return
        t = dp(1.3) * max(1, float(self.thickness))
        y = self.center_y
        m = dp(6)
        x0, x1 = self.x + m, self.right - m
        with self.canvas:
            Color(*self.color)
            st = self.style
            if st == 'dashed':
                dash, gap = dp(8), dp(5)
                x = x0
                while x < x1:
                    Rectangle(pos=(x, y - t / 2), size=(min(dash, x1 - x), t))
                    x += dash + gap
            elif st == 'dotted':
                r = max(dp(1.2), t * 0.75)
                step = r * 4.2
                x = x0 + r
                while x < x1 - r:
                    Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
                    x += step
            elif st == 'fade':
                Rectangle(texture=self.gradient(), pos=(x0, y - t / 2), size=(x1 - x0, t))
            elif st == 'ornament':
                cx = self.center_x
                gap = dp(14)
                Rectangle(texture=self.gradient(), pos=(x0, y - t / 2),
                          size=(cx - gap - x0, t))
                Rectangle(texture=self.gradient(), pos=(cx + gap, y - t / 2),
                          size=(x1 - cx - gap, t))
                s = dp(4) + t
                Mesh(vertices=[cx, y + s, 0, 0, cx + s, y, 0, 0, cx, y - s, 0, 0,
                               cx - s, y, 0, 0], indices=[0, 1, 2, 3], mode='triangle_fan')
            else:
                Rectangle(pos=(x0, y - t / 2), size=(x1 - x0, t))


class BarProgress(Widget):
    value = NumericProperty(0)      # 0..1
    fg = ListProperty([])
    bg = ListProperty([])

    def __init__(self, **kw):
        kw.setdefault('size_hint_y', None)
        kw.setdefault('height', dp(8))
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, value=self._trig, fg=self._trig, bg=self._trig)
        self._trig()

    def _draw(self, *a):
        self.canvas.clear()
        r = self.height / 2.0
        v = max(0.0, min(1.0, self.value))
        if rtl.UI_RTL:
            fill_x = self.right - self.width * v
        else:
            fill_x = self.x
        with self.canvas:
            Color(*(self.bg or C('card2')))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            if v > 0:
                Color(*(self.fg or C('primary')))
                RoundedRectangle(pos=(fill_x, self.y),
                                 size=(max(self.height, self.width * v), self.height),
                                 radius=[r])


# ======================================================================
# Buttons & controls
# ======================================================================
class RButton(ButtonBehavior, ALabel):
    """Rounded button (also used for chips and list rows)."""

    bg = ListProperty([0.3, 0.4, 0.9, 1])
    radius = NumericProperty(dp(14))
    outline = ListProperty([])
    click_sound = BooleanProperty(True)

    def __init__(self, **kw):
        kw.setdefault('align', 'center')
        kw.setdefault('bold', True)
        kw.setdefault('font_size', sp(15))
        super().__init__(**kw)
        with self.canvas.before:
            self._c = Color(*self.bg)
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._co = Color(0, 0, 0, 0)
            self._lo = Line(rounded_rectangle=(self.x, self.y, self.width, self.height,
                                               self.radius), width=1.2)
            self._cp = Color(1, 1, 1, 0)
            self._rp = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self.bind(pos=self._upd, size=self._upd, bg=self._upd, radius=self._upd,
                  outline=self._upd, state=self._on_state, disabled=self._on_disabled)
        self._upd()

    def _upd(self, *a):
        self._c.rgba = self.bg
        for r in (self._r, self._rp):
            r.pos = self.pos
            r.size = self.size
            r.radius = [self.radius]
        if self.outline:
            self._co.rgba = self.outline
        else:
            self._co.rgba = (0, 0, 0, 0)
        self._lo.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)

    def _on_state(self, *a):
        self._cp.rgba = (1, 1, 1, 0.16) if self.state == 'down' else (1, 1, 1, 0)

    def _on_disabled(self, *a):
        self.opacity = 0.45 if self.disabled else 1

    def on_press(self):
        if self.click_sound:
            from kivy.app import App
            app = App.get_running_app()
            sfx = getattr(app, 'sfx', None)
            if sfx:
                sfx.play('click')


def button(text, on_release=None, style='primary', height=None, size=15, icon=None, **kw):
    """Convenience factory. style: primary | soft | ghost | danger | success"""
    if style == 'primary':
        bg, fg, outline = C('primary'), C('on_primary'), []
    elif style == 'danger':
        bg, fg, outline = C('danger'), (1, 1, 1, 1), []
    elif style == 'success':
        bg, fg, outline = C('success'), (1, 1, 1, 1), []
    elif style == 'ghost':
        bg, fg, outline = [0, 0, 0, 0], C('text'), C('border')
    else:
        bg, fg, outline = C('card2'), C('text'), []
    kw.setdefault('size_hint_y', None)
    kw['height'] = height or dp(48)
    b = RButton(raw=text, bg=bg, color=fg, outline=outline, font_size=sp(size), **kw)
    if on_release:
        b.bind(on_release=lambda *_: on_release())
    return b


class Toggle(ButtonBehavior, Widget):
    """Pill switch."""

    active = BooleanProperty(False)
    _pos = NumericProperty(0.0)

    def __init__(self, **kw):
        kw.setdefault('size_hint', (None, None))
        kw.setdefault('size', (dp(50), dp(28)))
        super().__init__(**kw)
        self._pos = 1.0 if self.active else 0.0
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, _pos=self._trig, active=self._animate)
        self._trig()

    def _animate(self, *a):
        Animation(_pos=1.0 if self.active else 0.0, d=0.14).start(self)

    def on_release(self):
        self.active = not self.active

    def _draw(self, *a):
        self.canvas.clear()
        h = self.height
        r = h / 2.0
        with self.canvas:
            Color(*mix(C('chip'), C('primary'), self._pos))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            Color(1, 1, 1, 1)
            kr = r - dp(3)
            kx = self.x + dp(3) + (self.width - h) * self._pos
            Ellipse(pos=(kx, self.y + dp(3)), size=(2 * kr, 2 * kr))


class Segmented(BoxLayout):
    """Row of exclusive choices. options = [(value, label_text), ...]"""

    value = StringProperty('')

    def __init__(self, options, value, on_change=None, height=None, size=14, **kw):
        kw.setdefault('size_hint_y', None)
        kw['height'] = height or dp(42)
        kw.setdefault('spacing', dp(6))
        super().__init__(orientation='horizontal', **kw)
        self._options = options
        self._on_change = on_change
        self._size = size
        self._buttons = {}
        self.value = value
        btns = []
        for val, text in options:
            b = RButton(raw=text, font_size=sp(size), radius=dp(12), bold=True)
            b.bind(on_release=lambda inst, v=val: self.select(v))
            self._buttons[val] = b
            btns.append(b)
        add_row(self, btns)
        self._paint()

    def _paint(self):
        for val, b in self._buttons.items():
            if val == self.value:
                b.bg = C('primary')
                b.color = C('on_primary')
                b.outline = []
            else:
                b.bg = C('card2')
                b.color = C('sub')
                b.outline = []

    def select(self, val, fire=True):
        self.value = val
        self._paint()
        if fire and self._on_change:
            self._on_change(val)


class ColorDots(BoxLayout):
    """Row of colour swatches. colors = list of RGBA (None = 'no colour')."""

    selected = NumericProperty(0)

    def __init__(self, colors, selected=0, on_change=None, dot=dp(36), **kw):
        kw.setdefault('size_hint_y', None)
        kw['height'] = dot + dp(8)
        kw.setdefault('spacing', dp(8))
        super().__init__(orientation='horizontal', **kw)
        self.colors = colors
        self.selected = selected
        self._on_change = on_change
        self._dots = []
        items = []
        for i, col in enumerate(colors):
            d = _Dot(index=i, rgba=col, size_hint=(None, None), size=(dot, dot))
            d.bind(on_release=lambda inst: self._pick(inst.index))
            self._dots.append(d)
            items.append(d)
        add_row(self, items)
        self._paint()

    def _pick(self, i):
        self.selected = i
        self._paint()
        if self._on_change:
            self._on_change(i)

    def _paint(self):
        for d in self._dots:
            d.active = (d.index == self.selected)


class _Dot(ButtonBehavior, Widget):
    index = NumericProperty(0)
    rgba = ObjectProperty(None, allownone=True)
    active = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, active=self._trig, rgba=self._trig)
        self._trig()

    def _draw(self, *a):
        self.canvas.clear()
        s = min(self.width, self.height)
        cx, cy = self.center_x, self.center_y
        with self.canvas:
            if self.rgba is None:
                Color(*C('card2'))
                Ellipse(pos=(cx - s / 2, cy - s / 2), size=(s, s))
                Color(*C('sub'))
                Line(points=[cx - s * .22, cy - s * .22, cx + s * .22, cy + s * .22],
                     width=dp(1.6), cap='round')
                Line(points=[cx - s * .22, cy + s * .22, cx + s * .22, cy - s * .22],
                     width=dp(1.6), cap='round')
            else:
                Color(*self.rgba[:3], 1)
                Ellipse(pos=(cx - s * .42, cy - s * .42), size=(s * .84, s * .84))
            if self.active:
                Color(*C('text'))
                Line(circle=(cx, cy, s * .5 - dp(1)), width=dp(2))


# ======================================================================
# Flame (daily streak)
# ======================================================================
_FLAME_CTRL = [
    (.50, .02), (.78, .10), (.93, .30), (.89, .52), (.72, .68), (.63, .84),
    (.52, .99), (.43, .80), (.37, .64), (.27, .72), (.14, .52), (.09, .30),
    (.23, .10),
]

# streak days -> (outer colour, core colour)
_FLAME_STOPS = [
    (0, ((.38, .38, .40), (.62, .62, .64))),
    (1, ((1.0, .66, .05), (1.0, .96, .45))),
    (3, ((1.0, .45, .02), (1.0, .88, .25))),
    (7, ((.96, .24, .03), (1.0, .74, .12))),
    (14, ((.80, .08, .06), (1.0, .58, .10))),
    (30, ((.52, .02, .06), (1.0, .46, .10))),
]


def flame_colors(days):
    """Outer + core colour of the flame for a streak length (smooth gradient
    from yellow to dark red)."""
    if days <= 0:
        a = _FLAME_STOPS[0][1]
        return a[0], a[1]
    for i in range(len(_FLAME_STOPS) - 1):
        d0, c0 = _FLAME_STOPS[i]
        d1, c1 = _FLAME_STOPS[i + 1]
        if d0 <= days <= d1:
            t = (days - d0) / float(d1 - d0)
            outer = tuple(c0[0][k] + (c1[0][k] - c0[0][k]) * t for k in range(3))
            core = tuple(c0[1][k] + (c1[1][k] - c0[1][k]) * t for k in range(3))
            return outer, core
    return _FLAME_STOPS[-1][1][0], _FLAME_STOPS[-1][1][1]


def _catmull(points, seg=8):
    n = len(points)
    out = []
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        for s in range(seg):
            t = s / float(seg)
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    return out


_FLAME_OUTLINE = _catmull(_FLAME_CTRL)


class FlameWidget(Widget):
    """Fire icon: nested flame shapes interpolated from the outer colour to the
    glowing core give a real gradient. Colour depends on the streak days."""

    days = NumericProperty(0)
    layers = 8

    def __init__(self, **kw):
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trig, size=self._trig, days=self._trig)
        self._trig()

    def _draw(self, *a):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s <= 2:
            return
        ox = self.center_x - s / 2.0
        oy = self.center_y - s / 2.0
        outer, core = flame_colors(int(self.days))
        px, py = .50, .06
        with self.canvas:
            if self.days >= 7:
                Color(outer[0], outer[1], outer[2], 0.13)
                g = s * 1.0
                Ellipse(pos=(self.center_x - g / 2, self.center_y - g / 2), size=(g, g))
            for i in range(self.layers):
                t = i / float(self.layers - 1)
                scale = 1.0 - 0.72 * t
                col = [outer[k] + (core[k] - outer[k]) * (t ** 0.85) for k in range(3)]
                Color(col[0], col[1], col[2], 1)
                cont = []
                for (x, y) in _FLAME_OUTLINE:
                    sx = px + (x - px) * scale
                    sy = py + (y - py) * scale * (1.0 - 0.06 * t)
                    cont += [ox + sx * s, oy + sy * s]
                drawn = False
                if Tesselator is not None:
                    try:
                        tess = Tesselator()
                        tess.add_contour(cont)
                        if tess.tesselate(WINDING_ODD, TYPE_POLYGONS):
                            for vertices, indices in tess.meshes:
                                Mesh(vertices=vertices, indices=indices, mode='triangle_fan')
                            drawn = True
                    except Exception:                       # noqa: BLE001
                        drawn = False
                if not drawn:                               # simple fan from the centre
                    cx = ox + (px + (.5 - px) * scale) * s
                    cy = oy + (py + (.42 - py) * scale) * s
                    verts = [cx, cy, 0, 0]
                    for k in range(0, len(cont), 2):
                        verts += [cont[k], cont[k + 1], 0, 0]
                    verts += [cont[0], cont[1], 0, 0]
                    Mesh(vertices=verts, indices=list(range(len(verts) // 4)),
                         mode='triangle_fan')


# ======================================================================
# Text inputs
# ======================================================================
class ATextInput(TextInput):
    """Rounded text input.  Arabic hint text is shaped; use FormField to get a
    live, correctly-shaped preview of what is typed."""

    def __init__(self, hint='', **kw):
        kw.setdefault('multiline', False)
        kw.setdefault('background_normal', '')
        kw.setdefault('background_active', '')
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('foreground_color', C('text'))
        kw.setdefault('cursor_color', C('primary'))
        kw.setdefault('hint_text_color', alpha(C('sub'), 0.8))
        kw.setdefault('selection_color', alpha(C('primary'), 0.35))
        kw.setdefault('font_size', sp(17))
        kw.setdefault('padding', [dp(14), dp(13), dp(14), dp(13)])
        kw.setdefault('write_tab', False)
        kw.setdefault('size_hint_y', None)
        kw.setdefault('height', dp(50))
        kw['hint_text'] = rtl.display(hint) if hint else ''
        super().__init__(**kw)
        with self.canvas.before:
            self._c = Color(*C('input'))
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            self._cb = Color(*C('border'))
            self._lb = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(12)),
                            width=1.1)
        self.bind(pos=self._upd, size=self._upd, focus=self._upd)

    def _upd(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size
        self._cb.rgba = C('primary') if self.focus else C('border')
        self._lb.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(12))
        self._lb.width = 1.6 if self.focus else 1.1


class FormField(BoxLayout):
    """Caption + input + live Arabic preview (shown while typing Arabic)."""

    def __init__(self, caption, hint='', text='', multiline=False, height=None, **kw):
        kw.setdefault('size_hint_y', None)
        super().__init__(orientation='vertical', spacing=dp(5), **kw)
        self.bind(minimum_height=self.setter('height'))
        self.caption = label(caption, size=13, color='sub', bold=True)
        self.input = ATextInput(hint=hint, text=text, multiline=multiline)
        if height:
            self.input.height = height
        self.preview = ALabel(raw='', font_size=sp(19), color=C('primary'), wrap=True,
                              autoheight=True, size_hint_y=None, height=0, opacity=0,
                              padding=[dp(4), dp(2)])
        self.add_widget(self.caption)
        self.add_widget(self.input)
        self.add_widget(self.preview)
        self.input.bind(text=self._on_text)
        self._on_text(self.input, self.input.text)

    def _on_text(self, inst, text):
        if rtl.has_rtl(text):
            self.preview.raw = text
            self.preview.opacity = 1
            self.preview.size_hint_y = None
            self.preview.height = max(self.preview.height, dp(28))
        else:
            self.preview.raw = ''
            self.preview.opacity = 0
            self.preview.height = 0

    @property
    def text(self):
        return self.input.text.strip()


# ======================================================================
# Dialog / Toast
# ======================================================================
class Dialog(ModalView):
    """Modal card with a title, a body widget and a row of buttons.

    buttons = [(text, callback, style), ...]; the dialog closes after each
    button unless the callback returns False.
    """

    def __init__(self, title='', body=None, buttons=(), message='', body_max=None,
                 dismissable=True, **kw):
        extra = {}
        if hasattr(ModalView, 'overlay_color'):
            extra['overlay_color'] = (0, 0, 0, 0.62)
        else:                                   # old Kivy: dim through the background
            extra['background_color'] = (0, 0, 0, 0.62)
        kw.update(extra)
        kw.setdefault('background_color', (0, 0, 0, 0))
        super().__init__(size_hint=(None, None), background='',
                         auto_dismiss=dismissable, **kw)
        self.width = min(Window.width * 0.92, dp(420))
        card = Card(padding=[dp(18), dp(16), dp(18), dp(16)], spacing=dp(12),
                    size_hint_y=None, radius=dp(22), pos_hint={'x': 0, 'y': 0})
        card.bind(minimum_height=card.setter('height'))
        if title:
            card.add_widget(label(title, size=19, bold=True))
        if message:
            card.add_widget(label(message, size=15, color='sub'))
        if body is not None:
            max_h = body_max or Window.height * 0.58
            sv = ScrollView(size_hint_y=None, do_scroll_x=False, bar_width=dp(3),
                            bar_color=alpha(C('sub'), 0.5))
            body.size_hint_y = None
            sv.add_widget(body)

            def fit(*_):
                sv.height = min(body.height, max_h)
            body.bind(height=fit)
            fit()
            card.add_widget(sv)
        if buttons:
            row = hbox(dp(48), spacing=dp(10))
            btns = []
            for text, cb, style in buttons:
                b = button(text, None, style=style, height=dp(48))
                b.size_hint_x = 1
                b.bind(on_release=lambda inst, cb=cb: self._pressed(cb))
                btns.append(b)
            add_row(row, btns)
            card.add_widget(row)
        self.add_widget(card)
        self._card = card
        card.bind(height=self._fit_height)
        self._fit_height()

    def _fit_height(self, *a):
        self.height = min(self._card.height, Window.height * 0.94)

    def _pressed(self, cb):
        res = cb() if cb else None
        if res is not False:
            self.dismiss()


def confirm(title, message, on_yes, yes_text='OK', no_text='Cancel', danger=False):
    d = Dialog(title=title, message=message, buttons=[
        (no_text, None, 'soft'),
        (yes_text, on_yes, 'danger' if danger else 'primary')])
    d.open()
    return d


class Toast(BoxLayout):
    """Short message at the bottom of the screen."""

    _current = None

    @classmethod
    def show(cls, text, kind='info', duration=2.2):
        if cls._current is not None:
            try:
                Window.remove_widget(cls._current)
            except Exception:
                pass
        col = {'info': C('card2'), 'ok': C('success'), 'error': C('danger'),
               'warn': C('warn')}.get(kind, C('card2'))
        fg = C('text') if kind == 'info' else (1, 1, 1, 1)
        t = cls(col, fg, text)
        cls._current = t
        Window.add_widget(t)
        t.opacity = 0
        anim = Animation(opacity=1, d=0.15) + Animation(opacity=1, d=duration) + \
            Animation(opacity=0, d=0.3)
        anim.bind(on_complete=lambda *_: cls._remove(t))
        anim.start(t)

    @classmethod
    def _remove(cls, t):
        try:
            Window.remove_widget(t)
        except Exception:
            pass
        if cls._current is t:
            cls._current = None

    def __init__(self, bg, fg, text, **kw):
        super().__init__(orientation='vertical', size_hint=(None, None),
                         padding=[dp(16), dp(10)], **kw)
        w = min(Window.width * 0.9, dp(380))
        self.width = w
        self.lbl = ALabel(raw=text, font_size=sp(15), color=fg, wrap=True, autoheight=True,
                          size_hint_y=None, align='center')
        self.add_widget(self.lbl)
        self.lbl.bind(height=self._fit)
        self._fit()
        self.x = (Window.width - w) / 2.0
        self.y = dp(84)
        with self.canvas.before:
            Color(*C('shadow'))
            self._sh = RoundedRectangle(pos=(self.x, self.y - dp(2)), size=self.size,
                                        radius=[dp(16)])
            Color(*bg)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self._upd, size=self._upd)

    def _fit(self, *a):
        self.height = self.lbl.height + dp(20)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._sh.pos = (self.x, self.y - dp(2))
        self._sh.size = self.size

    def on_touch_down(self, touch):
        return False


# ======================================================================
# Top bar & navigation drawer
# ======================================================================
class TopBar(BoxLayout):
    """Title bar: menu / back button on the leading side, actions on the other."""

    def __init__(self, on_menu, on_back, **kw):
        super().__init__(orientation='horizontal', size_hint_y=None, height=dp(58),
                         padding=[dp(8), dp(4)], spacing=dp(4), **kw)
        with self.canvas.before:
            Color(*C('topbar'))
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*C('border'))
            self._ln = Rectangle(pos=self.pos, size=(self.width, 1))
        self.bind(pos=self._upd, size=self._upd)
        self._on_menu = on_menu
        self._on_back = on_back
        self.lead = IconButton(name='menu', color=C('text'), size_hint=(None, 1), width=dp(46))
        self.lead.bind(on_release=lambda *_: self._lead_pressed())
        self.title = ALabel(raw='', font_size=sp(20), bold=True, color=C('text'),
                            align='auto')
        self.actions = BoxLayout(orientation='horizontal', size_hint=(None, 1), width=0,
                                 spacing=dp(2))
        self.mode = 'menu'
        self._rebuild()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._ln.pos = self.pos
        self._ln.size = (self.width, 1)

    def _rebuild(self):
        self.clear_widgets()
        add_row(self, [self.lead, self.title, self.actions])

    def _lead_pressed(self):
        if self.mode == 'back':
            self._on_back()
        else:
            self._on_menu()

    def set(self, title, mode='menu', actions=()):
        self.title.raw = title
        self.mode = mode
        self.lead.name = 'back' if mode == 'back' else 'menu'
        self.lead.mirror = (mode == 'back' and rtl.UI_RTL)
        self.actions.clear_widgets()
        for icon, cb in actions:
            b = IconButton(name=icon, color=C('text'), size_hint=(None, 1), width=dp(46))
            b.bind(on_release=lambda inst, cb=cb: cb())
            self.actions.add_widget(b)
        self.actions.width = dp(46) * len(actions)


class DrawerItem(ButtonBehavior, BoxLayout):
    """One entry of the navigation drawer: icon + text."""

    def __init__(self, icon, text, active=False, **kw):
        super().__init__(orientation='horizontal', size_hint_y=None, height=dp(52),
                         padding=[dp(14), 0], spacing=dp(14), **kw)
        self.active = active
        with self.canvas.before:
            self._c = Color(*(alpha(C('primary'), 0.16) if active else (0, 0, 0, 0)))
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._upd, size=self._upd, state=self._state)
        col = C('primary') if active else C('text')
        holder = BoxLayout(orientation='vertical', size_hint=(None, 1), width=dp(28))
        holder.add_widget(Widget())
        holder.add_widget(Icon(name=icon, color=col, size_hint=(None, None),
                               size=(dp(26), dp(26))))
        holder.add_widget(Widget())
        add_row(self, [holder, ALabel(raw=text, font_size=sp(17), color=col, bold=active)])

    def _upd(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size

    def _state(self, *a):
        if self.state == 'down':
            self._c.rgba = alpha(C('primary'), 0.25)
        else:
            self._c.rgba = alpha(C('primary'), 0.16) if self.active else (0, 0, 0, 0)


class NavDrawer(FloatLayout):
    """Sliding side menu. Opens from the right in Arabic, from the left in English."""

    progress = NumericProperty(0.0)
    is_open = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.panel = BoxLayout(orientation='vertical', size_hint=(None, 1),
                               padding=[dp(14), dp(18), dp(14), dp(14)], spacing=dp(6))
        self.panel.width = min(Window.width * 0.82, dp(310))
        with self.panel.canvas.before:
            self._pc = Color(*C('card'))
            self._pr = Rectangle(pos=self.panel.pos, size=self.panel.size)
            self._pb = Color(*C('border'))
            self._pl = Rectangle(pos=self.panel.pos, size=(1, self.panel.height))
        self.panel.bind(pos=self._upd_panel, size=self._upd_panel)
        with self.canvas.before:
            self._sc = Color(0, 0, 0, 0)
            self._sr = Rectangle(pos=self.pos, size=self.size)
        self.add_widget(self.panel)
        self.bind(pos=self._layout, size=self._layout, progress=self._layout)
        Window.bind(size=self._on_window)
        self._layout()

    def _on_window(self, *a):
        self.panel.width = min(Window.width * 0.82, dp(310))
        self._layout()

    def _upd_panel(self, *a):
        self._pr.pos = self.panel.pos
        self._pr.size = self.panel.size
        edge_x = self.panel.x if rtl.UI_RTL else self.panel.right - 1
        self._pl.pos = (edge_x, self.panel.y)
        self._pl.size = (1, self.panel.height)

    def _layout(self, *a):
        w = self.panel.width
        p = self.progress
        if rtl.UI_RTL:
            self.panel.x = self.right - w * p
        else:
            self.panel.x = self.x - w + w * p
        self.panel.y = self.y
        self._sr.pos = self.pos
        self._sr.size = self.size
        self._sc.rgba = (0, 0, 0, 0.55 * p)
        self._upd_panel()

    # -- control ----------------------------------------------------------
    def open(self):
        self.is_open = True
        Animation.cancel_all(self, 'progress')
        Animation(progress=1.0, d=0.22, t='out_cubic').start(self)

    def close(self):
        self.is_open = False
        Animation.cancel_all(self, 'progress')
        Animation(progress=0.0, d=0.18, t='out_cubic').start(self)

    def toggle(self):
        self.close() if self.is_open else self.open()

    # -- touch handling ---------------------------------------------------
    def on_touch_down(self, touch):
        if self.is_open or self.progress > 0.02:
            if self.panel.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            self.close()
            return True
        edge = dp(18)
        at_edge = (touch.x >= Window.width - edge) if rtl.UI_RTL else (touch.x <= edge)
        if at_edge:
            touch.grab(self)
            touch.ud['drawer_x0'] = touch.x
            touch.ud['drawer_moved'] = False
        return False

    def on_touch_move(self, touch):
        if touch.grab_current is self and 'drawer_x0' in touch.ud:
            dx = touch.x - touch.ud['drawer_x0']
            if rtl.UI_RTL:
                dx = -dx
            if dx > dp(8) or touch.ud['drawer_moved']:
                touch.ud['drawer_moved'] = True
                self.progress = max(0.0, min(1.0, dx / self.panel.width))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if touch.ud.get('drawer_moved'):
                self.open() if self.progress > 0.35 else self.close()
            return True
        return super().on_touch_up(touch)
