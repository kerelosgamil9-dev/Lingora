# -*- coding: utf-8 -*-
"""
data_bank.py - Built-in vocabulary for Lingora.

Two tracks of progressive levels:
    group 'main'  : levels 1-24 + an automatic review level (25)
    group 'extra' : a from-zero beginner track (26-42) + an automatic review (43)
Every level has
    words     : (english, arabic, example sentence, arabic translation)
    sentences : (english sentence, arabic translation)
The text of this file is plain data - nothing here touches Kivy.
"""
import random

from _levels_A import LEVELS_PART as _A
from _levels_B import LEVELS_PART as _B
from _levels_C import LEVELS_PART as _C
from _levels_D import LEVELS_PART as _D
from _levels_E import LEVELS_PART as _E
from _levels_F import LEVELS_PART as _F
from _levels_patch import PATCH as _PATCH

MAIN_REVIEW_ID = 25
EXTRA_REVIEW_ID = 43
GROUPS = ('main', 'extra')


def _build():
    levels = []
    for part in (_A, _B, _C, _D, _E, _F):
        levels.extend(part)
    levels.sort(key=lambda l: l['id'])
    seen = set()
    out = []
    for lv in levels:
        words = []
        for w in lv['words']:
            key = w[0].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            words.append(tuple(w))
        for w in _PATCH.get(lv['id'], []):
            key = w[0].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            words.append(tuple(w))
        out.append({'id': lv['id'], 'group': lv['group'], 'title_en': lv['title_en'],
                    'title_ar': lv['title_ar'], 'words': words,
                    'sentences': [tuple(s) for s in lv['sentences']]})
    return out


def _review(level_id, group, title_en, title_ar, sources, per_level):
    """Automatic review level: a fixed (seeded) sample of earlier levels."""
    rnd = random.Random(level_id * 7919)
    words, sents = [], []
    for lv in sources:
        ws = list(lv['words'])
        rnd.shuffle(ws)
        words.extend(ws[:per_level])
        ss = list(lv['sentences'])
        rnd.shuffle(ss)
        sents.extend(ss[:1])
    rnd.shuffle(words)
    rnd.shuffle(sents)
    return {'id': level_id, 'group': group, 'title_en': title_en, 'title_ar': title_ar,
            'words': words[:50], 'sentences': sents[:10]}


LEVELS = _build()
_main = [l for l in LEVELS if l['group'] == 'main']
_extra = [l for l in LEVELS if l['group'] == 'extra']
LEVELS.append(_review(MAIN_REVIEW_ID, 'main', 'Review', 'مراجعة', _main, 2))
LEVELS.append(_review(EXTRA_REVIEW_ID, 'extra', 'Beginner Review', 'مراجعة المبتدئين',
                      _extra, 3))
LEVELS.sort(key=lambda l: l['id'])
_BY_ID = {l['id']: l for l in LEVELS}

# Example folder created by the "Add sample folder" button (Folders screen).
SAMPLE_FOLDER = {
    'name_en': 'Fruits',
    'name_ar': 'فواكه',
    'color': 3,
    'items': [
        ('apple', 'تفاحة', 'I eat an apple every day.', 'آكل تفاحة كل يوم.'),
        ('banana', 'موزة', 'A banana is yellow.', 'الموزة صفراء.'),
        ('orange', 'برتقالة', 'She drinks orange juice.', 'هي تشرب عصير البرتقال.'),
        ('grapes', 'عنب', 'These grapes are sweet.', 'هذا العنب حلو.'),
        ('strawberry', 'فراولة', 'I love strawberry cake.', 'أحب كعكة الفراولة.'),
        ('watermelon', 'بطيخ', 'Watermelon is great in summer.', 'البطيخ رائع في الصيف.'),
        ('lemon', 'ليمون', 'Add a slice of lemon.', 'أضف شريحة ليمون.'),
        ('mango', 'مانجو', 'Mango is my favorite fruit.', 'المانجو فاكهتي المفضلة.'),
    ],
}


def level_count():
    return len(LEVELS)


def level_ids():
    return [l['id'] for l in LEVELS]


def get_level(n):
    """Return the level dict with id n (None when unknown)."""
    return _BY_ID.get(n)


def group_ids(group):
    return [l['id'] for l in LEVELS if l['group'] == group]


def group_of(n):
    lv = _BY_ID.get(n)
    return lv['group'] if lv else None


def prev_in_group(n):
    """Id of the level that must be passed before n (None for a group's first)."""
    ids = group_ids(group_of(n))
    if n not in ids or ids.index(n) == 0:
        return None
    return ids[ids.index(n) - 1]


def next_in_group(n):
    ids = group_ids(group_of(n))
    if n not in ids or ids.index(n) == len(ids) - 1:
        return None
    return ids[ids.index(n) + 1]


def total_words():
    return sum(len(l['words']) for l in LEVELS)


def total_sentences():
    return sum(len(l['sentences']) for l in LEVELS)
