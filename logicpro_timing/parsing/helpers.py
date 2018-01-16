from collections import deque


BREAK_TYPE_MAPPING = {
    'Syllable': '•',
    'Line': '¬',
    'Page': '¶',
}


def text_with_break_type(text):
    if text and text[-1] in BREAK_TYPE_MAPPING.values():
        return text[:-1]
    elif text and text.endswith(BREAK_TYPE_MAPPING['Syllable']):
        return text[:-1]
    return text + ' '


def no_break(break_types, lyric):
    return not has_break(break_types, lyric)


def has_break(break_types, lyric):
    return any (lyric['text'].endswith(BREAK_TYPE_MAPPING[break_type])
                for break_type in break_types)


def groupwhile(predicate, iterable):
    inner = deque()
    for i in iterable:
        inner.append(i)
        if not predicate(i):
            yield inner
            inner.clear()
    yield inner
