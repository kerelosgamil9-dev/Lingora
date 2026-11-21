# -*- coding: utf-8 -*-
"""
rtl.py - Arabic text support for pure Kivy (no external dependencies).

Kivy's default text renderer on many Android builds (and Pydroid 3) does not
join Arabic letters and does not reorder right-to-left text.  This module
implements:

  * reshape()  : converts Arabic letters to their joined presentation forms
  * to_visual(): a compact version of the Unicode bidi algorithm that returns
                 the string in *visual* (left-to-right drawing) order
  * display()  : reshape + bidi in one call
  * wrap()     : word wrapping that is aware of shaping and direction

Text is always stored *logically* (as typed) in the database.  Only the very
last step before drawing converts it with display().
"""

ENABLED = True      # global switch, controlled from the Settings screen
UI_RTL = True       # default paragraph direction when a text has no strong char

# --------------------------------------------------------------------------
# Joining table : letter -> (isolated, final, initial, medial)
# --------------------------------------------------------------------------
_F = {
    'ء': ('ﺀ', None, None, None),
    'آ': ('ﺁ', 'ﺂ', None, None),
    'أ': ('ﺃ', 'ﺄ', None, None),
    'ؤ': ('ﺅ', 'ﺆ', None, None),
    'إ': ('ﺇ', 'ﺈ', None, None),
    'ئ': ('ﺉ', 'ﺊ', 'ﺋ', 'ﺌ'),
    'ا': ('ﺍ', 'ﺎ', None, None),
    'ب': ('ﺏ', 'ﺐ', 'ﺑ', 'ﺒ'),
    'ة': ('ﺓ', 'ﺔ', None, None),
    'ت': ('ﺕ', 'ﺖ', 'ﺗ', 'ﺘ'),
    'ث': ('ﺙ', 'ﺚ', 'ﺛ', 'ﺜ'),
    'ج': ('ﺝ', 'ﺞ', 'ﺟ', 'ﺠ'),
    'ح': ('ﺡ', 'ﺢ', 'ﺣ', 'ﺤ'),
    'خ': ('ﺥ', 'ﺦ', 'ﺧ', 'ﺨ'),
    'د': ('ﺩ', 'ﺪ', None, None),
    'ذ': ('ﺫ', 'ﺬ', None, None),
    'ر': ('ﺭ', 'ﺮ', None, None),
    'ز': ('ﺯ', 'ﺰ', None, None),
    'س': ('ﺱ', 'ﺲ', 'ﺳ', 'ﺴ'),
    'ش': ('ﺵ', 'ﺶ', 'ﺷ', 'ﺸ'),
    'ص': ('ﺹ', 'ﺺ', 'ﺻ', 'ﺼ'),
    'ض': ('ﺽ', 'ﺾ', 'ﺿ', 'ﻀ'),
    'ط': ('ﻁ', 'ﻂ', 'ﻃ', 'ﻄ'),
    'ظ': ('ﻅ', 'ﻆ', 'ﻇ', 'ﻈ'),
    'ع': ('ﻉ', 'ﻊ', 'ﻋ', 'ﻌ'),
    'غ': ('ﻍ', 'ﻎ', 'ﻏ', 'ﻐ'),
    'ـ': ('ـ', 'ـ', 'ـ', 'ـ'),
    'ف': ('ﻑ', 'ﻒ', 'ﻓ', 'ﻔ'),
    'ق': ('ﻕ', 'ﻖ', 'ﻗ', 'ﻘ'),
    'ك': ('ﻙ', 'ﻚ', 'ﻛ', 'ﻜ'),
    'ل': ('ﻝ', 'ﻞ', 'ﻟ', 'ﻠ'),
    'م': ('ﻡ', 'ﻢ', 'ﻣ', 'ﻤ'),
    'ن': ('ﻥ', 'ﻦ', 'ﻧ', 'ﻨ'),
    'ه': ('ﻩ', 'ﻪ', 'ﻫ', 'ﻬ'),
    'و': ('ﻭ', 'ﻮ', None, None),
    'ى': ('ﻯ', 'ﻰ', None, None),
    'ي': ('ﻱ', 'ﻲ', 'ﻳ', 'ﻴ'),
    # Persian / Urdu extras
    'پ': ('ﭖ', 'ﭗ', 'ﭘ', 'ﭙ'),
    'چ': ('ﭺ', 'ﭻ', 'ﭼ', 'ﭽ'),
    'ژ': ('ﮊ', 'ﮋ', None, None),
    'ک': ('ﮎ', 'ﮏ', 'ﮐ', 'ﮑ'),
    'گ': ('ﮒ', 'ﮓ', 'ﮔ', 'ﮕ'),
    'ی': ('ﯼ', 'ﯽ', 'ﯾ', 'ﯿ'),
}

# Lam + Alef ligatures : alef -> (isolated, final)
_LAM_ALEF = {
    'آ': ('ﻵ', 'ﻶ'),
    'أ': ('ﻷ', 'ﻸ'),
    'إ': ('ﻹ', 'ﻺ'),
    'ا': ('ﻻ', 'ﻼ'),
}

_MIRROR = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{',
           '<': '>', '>': '<', '«': '»', '»': '«'}


def is_mark(ch):
    """Arabic diacritics / combining marks (they never take part in joining)."""
    o = ord(ch)
    return (0x064B <= o <= 0x065F) or o == 0x0670 or (0x06D6 <= o <= 0x06ED)


def _is_rtl_char(ch):
    o = ord(ch)
    if 0x0660 <= o <= 0x0669 or 0x06F0 <= o <= 0x06F9:
        return False
    return ((0x0590 <= o <= 0x08FF) or (0xFB1D <= o <= 0xFDFF)
            or (0xFE70 <= o <= 0xFEFF))


def has_rtl(text):
    """True if the text contains at least one Arabic / Hebrew letter."""
    for ch in text:
        if _is_rtl_char(ch):
            return True
    return False


def base_is_rtl(text, default=None):
    """Paragraph direction: direction of the first strong character."""
    for ch in text:
        if _is_rtl_char(ch):
            return True
        if ch.isalpha():
            return False
    return UI_RTL if default is None else default


# --------------------------------------------------------------------------
# Shaping
# --------------------------------------------------------------------------
def _prev_base(chars, i):
    j = i - 1
    while j >= 0 and is_mark(chars[j]):
        j -= 1
    return chars[j] if j >= 0 else None


def _next_base(chars, i):
    n = len(chars)
    j = i + 1
    while j < n and is_mark(chars[j]):
        j += 1
    return chars[j] if j < n else None


def reshape(text):
    """Replace Arabic letters with their contextual presentation forms."""
    if not text:
        return text
    chars = list(text)
    n = len(chars)
    out = []
    i = 0
    while i < n:
        c = chars[i]
        forms = _F.get(c)
        if forms is None:
            out.append(c)
            i += 1
            continue
        prev_c = _prev_base(chars, i)
        pf = _F.get(prev_c) if prev_c is not None else None
        joins_prev = bool(pf and pf[2] is not None and forms[1] is not None)

        # Lam + Alef ligature
        if c == 'ل' and i + 1 < n and chars[i + 1] in _LAM_ALEF:
            lig = _LAM_ALEF[chars[i + 1]]
            out.append(lig[1] if joins_prev else lig[0])
            i += 2
            continue

        next_c = _next_base(chars, i)
        nf = _F.get(next_c) if next_c is not None else None
        joins_next = bool(forms[2] is not None and nf and nf[1] is not None)

        if joins_prev and joins_next:
            out.append(forms[3])
        elif joins_prev:
            out.append(forms[1])
        elif joins_next:
            out.append(forms[2])
        else:
            out.append(forms[0])
        i += 1
    return ''.join(out)


# --------------------------------------------------------------------------
# Bidi (simplified Unicode Bidirectional Algorithm)
# --------------------------------------------------------------------------
def _cls(ch):
    if is_mark(ch):
        return 'NSM'
    o = ord(ch)
    if 0x0660 <= o <= 0x0669 or 0x06F0 <= o <= 0x06F9:
        return 'AN'
    if _is_rtl_char(ch):
        return 'R'
    if '0' <= ch <= '9':
        return 'EN'
    if ch.isalpha():
        return 'L'
    return 'N'


def _clusters(text):
    """Split into [base char + following marks] clusters."""
    res = []
    for ch in text:
        if is_mark(ch) and res:
            res[-1] += ch
        else:
            res.append(ch)
    return res


def to_visual(text, base_rtl):
    """Return *text* reordered into visual order (what we draw left->right)."""
    if not text:
        return text
    cl = _clusters(text)
    n = len(cl)
    types = [_cls(c[0]) for c in cl]
    base_dir = 'R' if base_rtl else 'L'
    base_level = 1 if base_rtl else 0

    # --- weak types: digits following Latin letters behave like Latin ------
    last_strong = base_dir
    eff = []
    for t in types:
        if t == 'L':
            last_strong = 'L'
            eff.append('L')
        elif t == 'R':
            last_strong = 'R'
            eff.append('R')
        elif t == 'EN':
            eff.append('L' if last_strong == 'L' else 'EN')
        else:
            eff.append(t)

    # --- number related punctuation stays with the digits (W4 / W5) --------
    ET = set('%$#+\u00A3\u20AC\u00B0')
    SEP = set('.,:/')
    chars0 = [c[0] for c in cl]
    for i in range(n):                          # 60%  $5  +3
        if eff[i] == 'N' and chars0[i] in ET:
            j = i + 1
            while j < n and eff[j] == 'N' and chars0[j] in ET:
                j += 1
            k = i - 1
            while k >= 0 and eff[k] == 'N' and chars0[k] in ET:
                k -= 1
            if (j < n and eff[j] == 'EN') or (k >= 0 and eff[k] == 'EN'):
                for m in range(k + 1, j):
                    if chars0[m] in ET:
                        eff[m] = 'EN'
    for i in range(1, n - 1):                   # 10:30  1.5  3/4
        if eff[i] == 'N' and chars0[i] in SEP and eff[i - 1] == 'EN' and eff[i + 1] == 'EN':
            eff[i] = 'EN'

    def context(t):
        if t in ('R', 'EN', 'AN'):
            return 'R'
        if t == 'L':
            return 'L'
        return None

    # --- resolve neutrals --------------------------------------------------
    levels = [0] * n
    i = 0
    while i < n:
        t = eff[i]
        if t in ('N', 'NSM'):
            j = i
            while j < n and eff[j] in ('N', 'NSM'):
                j += 1
            before = base_dir
            k = i - 1
            while k >= 0:
                cx = context(eff[k])
                if cx:
                    before = cx
                    break
                k -= 1
            after = base_dir
            k = j
            while k < n:
                cx = context(eff[k])
                if cx:
                    after = cx
                    break
                k += 1
            d = before if before == after else base_dir
            for m in range(i, j):
                levels[m] = _level_for(d, base_level)
            i = j
            continue
        if t == 'R':
            levels[i] = 1
        elif t == 'L':
            levels[i] = 0 if base_level == 0 else 2
        else:                       # EN / AN
            levels[i] = 2
        i += 1

    # --- reorder (rule L2) ---------------------------------------------------
    odd = [lv for lv in levels if lv % 2 == 1]
    if odd:
        lo = min(odd)
        hi = max(levels)
        order = list(range(n))
        for lvl in range(hi, lo - 1, -1):
            a = 0
            while a < n:
                if levels[order[a]] >= lvl:
                    b = a
                    while b < n and levels[order[b]] >= lvl:
                        b += 1
                    order[a:b] = reversed(order[a:b])
                    a = b
                else:
                    a += 1
        out = []
        for idx in order:
            c = cl[idx]
            if levels[idx] % 2 == 1 and len(c) == 1 and c in _MIRROR:
                c = _MIRROR[c]
            out.append(c)
        return ''.join(out)
    return ''.join(cl)


def _level_for(direction, base_level):
    if direction == 'R':
        return 1
    return 0 if base_level == 0 else 2


# --------------------------------------------------------------------------
# Public helpers
# --------------------------------------------------------------------------
def display(text, rtl=None):
    """Logical text -> text that Kivy can draw correctly (single line)."""
    if not text or not ENABLED:
        return text
    if not has_rtl(text):
        return text
    if rtl is None:
        rtl = base_is_rtl(text)
    return to_visual(reshape(text), rtl)


def wrap(text, max_width, measure, rtl=None):
    """Greedy word wrap on *logical* text. Returns a list of logical lines."""
    lines = []
    for para in text.split('\n'):
        words = para.split(' ')
        cur = ''
        for w in words:
            cand = w if not cur else cur + ' ' + w
            if not cur or measure(display(cand, rtl)) <= max_width:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def wrap_display(text, max_width, measure, rtl=None):
    """Wrap logical text and return the visual multi-line string."""
    return '\n'.join(display(l, rtl) for l in wrap(text, max_width, measure, rtl))
