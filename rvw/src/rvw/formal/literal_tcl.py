"""Literal Tcl command words only. No evaluation or substitution."""
import re


def commands(source):
    # Tcl's backslash-newline prepass also applies inside braces and comments.
    source = re.sub(r'\\\r?\n[ \t]*', ' ', source)
    result, words, word = [], [], []
    mode, line, start, index = None, 1, 1, 0
    while index < len(source):
        char = source[index]
        if mode in ('brace', 'quote'):
            close = '}' if mode == 'brace' else '"'
            if char == close:
                words.append(''.join(word)); word = []; mode = 'closed'
            elif char in '$[]\\' or (mode == 'brace' and char == '{'):
                raise ValueError(f'line {line}: only literal flat Tcl words are supported')
            else:
                word.append(char)
        elif char in '\n;' or char.isspace():
            if mode == 'bare': words.append(''.join(word)); word = []
            mode = None
            if char in '\n;' and words:
                result.append((start, words)); words = []
        elif mode == 'closed':
            raise ValueError(f'line {line}: word needs a separator after closing quote or brace')
        elif char == '#' and not words and mode is None:
            end = source.find('\n', index)
            if end < 0: break
            index = end
            continue
        elif char in '$[]\\}' or (mode == 'bare' and char in '{"'):
            raise ValueError(f'line {line}: only literal flat Tcl words are supported')
        else:
            if not words and mode is None: start = line
            if mode is None and char in '{"':
                mode = 'brace' if char == '{' else 'quote'
            else:
                mode = 'bare'; word.append(char)
        if char == '\n': line += 1
        index += 1
    if mode in ('brace', 'quote'):
        raise ValueError(f'line {line}: unterminated Tcl word')
    if mode == 'bare': words.append(''.join(word))
    if words: result.append((start, words))
    return result
