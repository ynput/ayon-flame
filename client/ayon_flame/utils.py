import re
from typing import Union

def perl_style_sub(
    pattern: str,
    repl: str,
    text: str,
    flags: Union[re.RegexFlag, int] = 0
) -> str:
    r"""Do a regex replacement using perl-style replacement syntax.

    Perl-style replacement allows us to define changing of capture group
    case without needing to define a replacement function for `re.sub`.

    This is necessary so we can use the server settings to allow users to
    define string replacements that do more than just reference capture
    groups.

    Available notation:
        - `\U`: Uppercase
        - `\u`: Uppercase first letter
        - `\L`: Lowercase
        - `\l`: Lowercase first letter
        - `\E`: Prevent further case change

    Examples:

    .. code-block:: python

        perl_style_sub(r"(hello)", r"\U\1", "hello you")
        >>> 'HELLO you'
        perl_style_sub(r"(hello)", r"\u\1", "hello you")
        >>> 'Hello you'
        perl_style_sub(r"(hello)", r"\L\1", "HELLO YOU", flags=re.IGNORECASE)
        >>> 'hello YOU'
        perl_style_sub(r"(hello)", r"\l\1", "HELLO YOU", flags=re.IGNORECASE)
        >>> 'hELLO YOU'
        perl_style_sub(r"(hello) (you)", r"\U\1 \2", "hello you")
        >>> 'HELLO YOU'
        perl_style_sub(r"(hello) (you)", r"\U\1\E \2", "hello you")
        >>> 'HELLO you'

    Args:
        pattern (str): Regex pattern.
        repl (str): Replacement patter.
        text (str): Input string.
        flags (re.RegexFlag or int, optional): Optional regex flags you would
            pass to normal `re` calls. Defaults to 0.

    Returns:
        str: Substituted string.
    """
    regex = re.compile(pattern, flags)

    token_re = re.compile(r'(\\[uUlLE]|\\(\d+))')

    def apply_replacement(match):
        result = []
        mode = None
        pos = 0

        for m in token_re.finditer(repl):
            start, end = m.span()

            # literal text before token
            literal = repl[pos:start]
            if literal:
                result.append(apply_mode(literal, mode))

            token = m.group(0)

            if token == r'\u':
                mode = 'upper1'
            elif token == r'\U':
                mode = 'upper'
            elif token == r'\l':
                mode = 'lower1'
            elif token == r'\L':
                mode = 'lower'
            elif token == r'\E':
                mode = None
            else:
                group = match.group(int(m.group(2)))
                result.append(apply_mode(group, mode))
                mode = None if mode in ('upper1', 'lower1') else mode

            pos = end

        # trailing literal
        tail = repl[pos:]
        if tail:
            result.append(apply_mode(tail, mode))

        return ''.join(result)

    def apply_mode(text, mode):
        if mode == 'upper':
            return text.upper()
        if mode == 'lower':
            return text.lower()
        if mode == 'upper1':
            return text[:1].upper() + text[1:]
        if mode == 'lower1':
            return text[:1].lower() + text[1:]
        return text

    return regex.sub(apply_replacement, text)
