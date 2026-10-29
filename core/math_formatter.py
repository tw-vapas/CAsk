"""LaTeX mathematical formula formatter for CAsk HUD.

Converts AI-generated LaTeX math expressions ($...$, $$...$$, \\[...\\], \\(...\\))
into high-fidelity Unicode mathematical representations rendered cleanly in Qt Markdown/HTML.
"""

from __future__ import annotations

import re

# Unicode Superscript Mapping
_SUPERSCRIPTS: dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ",
    "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ",
    "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
    "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
    "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ",
    "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ",
    "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ",
    "T": "ᵀ", "U": "ᵁ", "W": "ᵂ",
}

# Unicode Subscript Mapping
_SUBSCRIPTS: dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
}

# LaTeX Greek Letters
_GREEKS: list[tuple[str, str]] = [
    (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"), (r"\Gamma", "Γ"),
    (r"\delta", "δ"), (r"\Delta", "Δ"), (r"\epsilon", "ε"), (r"\varepsilon", "ε"),
    (r"\zeta", "ζ"), (r"\eta", "η"), (r"\theta", "θ"), (r"\Theta", "Θ"),
    (r"\vartheta", "θ"), (r"\iota", "ι"), (r"\kappa", "κ"), (r"\lambda", "λ"),
    (r"\Lambda", "Λ"), (r"\mu", "μ"), (r"\nu", "ν"), (r"\xi", "ξ"),
    (r"\Xi", "Ξ"), (r"\pi", "π"), (r"\Pi", "Π"), (r"\rho", "ρ"),
    (r"\sigma", "σ"), (r"\Sigma", "Σ"), (r"\tau", "τ"), (r"\upsilon", "υ"),
    (r"\phi", "φ"), (r"\Phi", "Φ"), (r"\varphi", "φ"), (r"\chi", "χ"),
    (r"\psi", "ψ"), (r"\Psi", "Ψ"), (r"\omega", "ω"), (r"\Omega", "Ω"),
]

# LaTeX Operators and Symbols
_SYMBOLS: list[tuple[str, str]] = [
    (r"\pm", "±"), (r"\mp", "∓"), (r"\times", "×"), (r"\cdot", "·"),
    (r"\div", "÷"), (r"\neq", "≠"), (r"\ne", "≠"), (r"\leq", "≤"),
    (r"\le", "≤"), (r"\geq", "≥"), (r"\ge", "≥"), (r"\approx", "≈"),
    (r"\equiv", "≡"), (r"\sim", "∼"), (r"\propto", "∝"), (r"\infty", "∞"),
    (r"\int", "∫"), (r"\iint", "∬"), (r"\iiint", "∭"), (r"\oint", "∮"),
    (r"\sum", "∑"), (r"\prod", "∏"), (r"\partial", "∂"), (r"\nabla", "∇"),
    (r"\in", "∈"), (r"\notin", "∉"), (r"\subset", "⊂"), (r"\subseteq", "⊆"),
    (r"\supset", "⊃"), (r"\supseteq", "⊇"), (r"\cap", "∩"), (r"\cup", "∪"),
    (r"\vee", "∨"), (r"\wedge", "∧"), (r"\forall", "∀"), (r"\exists", "∃"),
    (r"\neg", "¬"), (r"\to", "→"), (r"\rightarrow", "→"), (r"\leftarrow", "←"),
    (r"\Rightarrow", "⇒"), (r"\Leftarrow", "⇐"), (r"\Leftrightarrow", "⇔"),
    (r"\iff", "⟺"), (r"\parallel", "∥"), (r"\perp", "⊥"), (r"\circ", "∘"),
    (r"\bullet", "•"), (r"\hbar", "ℏ"), (r"\ell", "ℓ"),
]

_COMMON_FUNCS = [
    "sin", "cos", "tan", "cot", "sec", "csc",
    "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
    "ln", "log", "exp", "lim", "max", "min", "sup", "inf",
    "det", "gcd", "deg"
]


def _extract_braced(s: str, start_idx: int) -> tuple[str | None, int]:
    """Extract content of balanced curly braces starting at or after start_idx."""
    pos = s.find("{", start_idx)
    if pos == -1:
        return None, -1
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[pos + 1 : i], i + 1
    return None, -1


def _extract_bracketed(s: str, start_idx: int) -> tuple[str | None, int]:
    """Extract content of balanced square brackets starting at or after start_idx."""
    pos = s.find("[", start_idx)
    if pos == -1:
        return None, -1
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == "[":
            depth += 1
        elif s[i] == "]":
            depth -= 1
            if depth == 0:
                return s[pos + 1 : i], i + 1
    return None, -1


def format_math_expression(expr: str) -> str:
    """Transform a raw LaTeX math string into a readable Unicode formula."""
    s = expr.strip()
    if not s:
        return ""

    # Remove font / text styling wrappers
    s = re.sub(r"\\text\{([^}]+)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^}]+)\}", r"\1", s)
    s = re.sub(r"\\mathbf\{([^}]+)\}", r"\1", s)
    s = re.sub(r"\\mathit\{([^}]+)\}", r"\1", s)
    s = re.sub(r"\\operatorname\{([^}]+)\}", r"\1", s)

    # Brackets normalization
    s = re.sub(r"\\left\(", "(", s)
    s = re.sub(r"\\right\)", ")", s)
    s = re.sub(r"\\left\[", "[", s)
    s = re.sub(r"\\right\]", "]", s)
    s = re.sub(r"\\left\\\{", "{", s)
    s = re.sub(r"\\right\\\}", "}", s)
    s = re.sub(r"\\left\|", "|", s)
    s = re.sub(r"\\right\|", "|", s)
    s = re.sub(r"\\left\.", "", s)
    s = re.sub(r"\\right\.", "", s)

    # Spacing commands
    s = re.sub(r"\\[,;:!]", " ", s)
    s = re.sub(r"\\quad", "   ", s)
    s = re.sub(r"\\qquad", "      ", s)

    # Convert fractions with balanced brace support
    while True:
        idx = s.find(r"\frac")
        if idx == -1:
            break
        num, end1 = _extract_braced(s, idx + 5)
        if num is None:
            break
        den, end2 = _extract_braced(s, end1)
        if den is None:
            break
        formatted_num = format_math_expression(num)
        formatted_den = format_math_expression(den)
        num_str = formatted_num if (len(formatted_num) == 1 and formatted_num.isalnum()) else f"({formatted_num})"
        den_str = formatted_den if (len(formatted_den) == 1 and formatted_den.isalnum()) else f"({formatted_den})"
        s = s[:idx] + f"{num_str} / {den_str}" + s[end2:]

    # Convert roots with balanced brace support: \sqrt[n]{x} or \sqrt{x}
    while True:
        idx = s.find(r"\sqrt")
        if idx == -1:
            break
        after = s[idx + 5:].lstrip()
        if after.startswith("["):
            deg_raw, end1 = _extract_bracketed(s, idx + 5)
            deg = "".join(_SUPERSCRIPTS.get(c, c) for c in format_math_expression(deg_raw or "").strip())
            val, end2 = _extract_braced(s, end1)
            formatted_val = format_math_expression(val or "")
            s = s[:idx] + f"{deg}√({formatted_val})" + s[end2:]
        else:
            val, end = _extract_braced(s, idx + 5)
            if val is None:
                break
            formatted_val = format_math_expression(val)
            s = s[:idx] + f"√({formatted_val})" + s[end:]

    # Greek letters
    for pattern, rep in _GREEKS:
        s = re.sub(re.escape(pattern) + r"(?![a-zA-Z])", rep, s)

    # Math operators and symbols
    for pattern, rep in _SYMBOLS:
        s = re.sub(re.escape(pattern) + r"(?![a-zA-Z])", rep, s)

    # Standard function names
    for fn in _COMMON_FUNCS:
        s = re.sub(rf"\\{fn}(?![a-zA-Z])", fn, s)

    # Vectors \vec{F} -> F⃗
    s = re.sub(r"\\vec\{([a-zA-Z0-9])\}", r"\1⃗", s)

    # Overline / bars \bar{x} -> x̄
    s = re.sub(r"\\bar\{([a-zA-Z0-9])\}", r"\1̄", s)

    # Superscripts: ^{abc} or ^x
    while True:
        idx = s.find("^{")
        if idx == -1:
            break
        val, end = _extract_braced(s, idx + 1)
        if val is None:
            break
        sup_val = "".join(_SUPERSCRIPTS.get(c, c) for c in val)
        s = s[:idx] + sup_val + s[end:]

    # Single char superscripts ^2, ^n, etc.
    def _sup_single(match: re.Match) -> str:
        ch = match.group(1)
        return _SUPERSCRIPTS.get(ch, f"^{ch}")

    s = re.sub(r"\^([0-9a-zA-Z+\-])", _sup_single, s)

    # Subscripts: _{abc} or _x
    while True:
        idx = s.find("_{")
        if idx == -1:
            break
        val, end = _extract_braced(s, idx + 1)
        if val is None:
            break
        sub_val = "".join(_SUBSCRIPTS.get(c, c) for c in val)
        s = s[:idx] + sub_val + s[end:]

    def _sub_single(match: re.Match) -> str:
        ch = match.group(1)
        return _SUBSCRIPTS.get(ch, f"_{ch}")

    s = re.sub(r"\_([0-9a-zA-Z+\-])", _sub_single, s)

    # Clean double spaces
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def format_math_in_markdown(content: str) -> str:
    """Parse and transform all LaTeX math blocks and inline formulas in Markdown text."""
    if not content:
        return ""

    # 1. Block formulas: $$...$$ or \[...\]
    def _block_replacer(match: re.Match) -> str:
        raw_formula = match.group(1)
        formatted = format_math_expression(raw_formula)
        return f"\n\n> 📐 **Formula:**  \n> `{formatted}`\n\n"

    text = re.sub(r"\$\$(.*?)\$\$", _block_replacer, content, flags=re.DOTALL)
    text = re.sub(r"\\\[(.*?)\\\]", _block_replacer, text, flags=re.DOTALL)

    # 2. Inline formulas: $...$ or \(...\)
    def _inline_replacer(match: re.Match) -> str:
        raw_formula = match.group(1)
        # Avoid treating currency (e.g. $100 or $5) as math
        if re.match(r"^\d+([.,]\d+)?$", raw_formula.strip()):
            return match.group(0)
        formatted = format_math_expression(raw_formula)
        return f"`{formatted}`"

    text = re.sub(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", _inline_replacer, text)
    text = re.sub(r"\\\((.*?)\\\)", _inline_replacer, text)

    return text
