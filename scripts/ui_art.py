"""3D-style SVG objects for TrueTick (blue, tone-on-tone). Each takes an id prefix so several can live on one page."""

SH = "M0 -62 C14 -55 30 -50 48 -48 C49 -12 47 10 40 26 C31 46 15 58 0 66 C-15 58 -31 46 -40 26 C-47 10 -49 -12 -48 -48 C-30 -50 -14 -55 0 -62 Z"


def grads(p):
    return f'''<defs>
  <linearGradient id="{p}a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9dbcff"/><stop offset=".5" stop-color="#4f84ff"/><stop offset="1" stop-color="#1b3fc0"/></linearGradient>
  <linearGradient id="{p}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".55"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
  <linearGradient id="{p}c" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a55e0"/><stop offset="1" stop-color="#132f9a"/></linearGradient>
</defs>'''


def disc(p="d", cls="art"):
    """A thick glass-and-silver coin, tilted, with a raised blue shield outline and tick."""
    edge = ""
    for k in range(14, 0, -1):
        edge += f'<ellipse rx="104" ry="104" fill="url(#{p}edge)" transform="translate({k*1.5:.1f} {k*1.1:.1f})"/>'
    def raised(d, sw, n):
        out = ""
        for k in range(n, 0, -1):
            out += f'<path d="{d}" fill="none" stroke="#1a3fb8" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" transform="translate({k*0.9:.1f} {k*0.8:.1f})"/>'
        out += f'<path d="{d}" fill="none" stroke="url(#{p}sh)" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"/>'
        out += f'<path d="{d}" fill="none" stroke="#ffffff" stroke-opacity=".55" stroke-width="{sw*0.22:.1f}" stroke-linejoin="round" stroke-linecap="round" transform="translate(-{sw*0.18:.1f} -{sw*0.2:.1f})"/>'
        return out
    tick = "M-22 3 L-6 19 L24 -14"
    return f'''<svg class="{cls}" viewBox="-150 -150 300 300">
  <defs>
    <radialGradient id="{p}face" cx="32%" cy="28%" r="80%"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#eef2f9"/><stop offset="1" stop-color="#cdd6e6"/></radialGradient>
    <linearGradient id="{p}edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7f9fc"/><stop offset=".3" stop-color="#b7c1d4"/><stop offset=".55" stop-color="#f2f5fa"/><stop offset=".8" stop-color="#97a3bb"/><stop offset="1" stop-color="#dfe5ef"/></linearGradient>
    <linearGradient id="{p}rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#aeb9cf"/></linearGradient>
    <linearGradient id="{p}sh" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7ea6ff"/><stop offset=".55" stop-color="#3a72ff"/><stop offset="1" stop-color="#2353e6"/></linearGradient>
    <filter id="{p}blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
  </defs>
  <ellipse cx="14" cy="128" rx="96" ry="12" fill="#0b1020" opacity=".10" filter="url(#{p}blur)"/>
  <g transform="rotate(-16) scale(.9 1)">
    {edge}
    <ellipse rx="104" ry="104" fill="url(#{p}face)"/>
    <ellipse rx="92" ry="92" fill="none" stroke="url(#{p}rim)" stroke-width="5"/>
    <ellipse rx="92" ry="92" fill="none" stroke="#ffffff" stroke-width="1.5" transform="translate(-1.5 -1.5)"/>
    <ellipse cx="-30" cy="-44" rx="54" ry="30" fill="#ffffff" opacity=".55" filter="url(#{p}blur)"/>
    <g transform="translate(2 4) scale(1.02)">{raised(SH, 13, 9)}{raised(tick, 12, 7)}</g>
  </g>
</svg>'''


def rings(p="r", cls="obj"):
    body = ""
    for r, w in [(96, 22), (68, 20), (42, 18)]:
        body += f'<ellipse rx="{r}" ry="{r}" fill="none" stroke="url(#{p}c)" stroke-width="{w}" transform="translate(3 6)"/>'
        body += f'<ellipse rx="{r}" ry="{r}" fill="none" stroke="url(#{p}a)" stroke-width="{w}"/>'
        body += f'<ellipse rx="{r}" ry="{r}" fill="none" stroke="url(#{p}b)" stroke-width="{w*0.35:.1f}" transform="translate(-2 -{w*0.25:.1f})"/>'
    body += f'<circle r="18" fill="url(#{p}a)"/><circle r="18" fill="url(#{p}b)"/>'
    return f'<svg class="{cls}" viewBox="-120 -120 240 240">{grads(p)}<g transform="translate(10 10) scale(1 .9) rotate(-18)">{body}</g></svg>'


def bubbles(p="b", cls="obj"):
    def bub(x, y, w, h, flip=False):
        tail = f'M{x+24} {y+h-2} l-6 22 l26 -20 z' if not flip else f'M{x+w-24} {y+h-2} l6 22 l-26 -20 z'
        shape = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="30"/><path d="{tail}"/>'
        out = "".join(f'<g fill="url(#{p}c)" transform="translate({k*1.2:.1f} {k*1.4:.1f})">{shape}</g>' for k in range(8, 0, -1))
        out += f'<g fill="url(#{p}a)">{shape}</g><rect x="{x+10}" y="{y+8}" width="{w-20}" height="{h*0.42:.0f}" rx="22" fill="url(#{p}b)"/>'
        return out
    dots = "".join(f'<circle cx="{-55+i*30}" cy="58" r="7" fill="#ffffff" opacity=".85"/>' for i in range(3))
    return f'<svg class="{cls}" viewBox="-120 -120 240 240">{grads(p)}<g transform="rotate(-8) translate(10 0)">{bub(-70,-80,150,96,True)}{bub(-100,10,160,96)}{dots}</g></svg>'


def chain(p="c", cls="obj"):
    def link(tx, ty, rot):
        a = 'x="-62" y="-30" width="124" height="60" rx="30"'
        return (f'<g transform="translate({tx} {ty}) rotate({rot})">'
                f'<rect {a} fill="none" stroke="url(#{p}c)" stroke-width="22" transform="translate(3 6)"/>'
                f'<rect {a} fill="none" stroke="url(#{p}a)" stroke-width="22"/>'
                f'<rect x="-56" y="-34" width="100" height="16" rx="8" fill="url(#{p}b)" opacity=".7"/></g>')
    return (f'<svg class="{cls}" viewBox="-120 -120 240 240">{grads(p)}{link(-34,26,-38)}{link(34,-26,-38)}'
            f'<g transform="translate(-34 26) rotate(-38)"><path d="M30 -30 a30 30 0 0 1 30 30" fill="none" stroke="url(#{p}a)" stroke-width="22"/></g></svg>')


def flag(p="f", cls="obj"):
    pole = (f'<rect x="-70" y="-100" width="14" height="210" rx="7" fill="url(#{p}c)"/>'
            f'<rect x="-68" y="-100" width="5" height="210" rx="2.5" fill="#ffffff" opacity=".35"/><circle cx="-63" cy="-104" r="12" fill="url(#{p}a)"/>')
    wave = 'M-56 -88 C-20 -108 10 -66 50 -86 C70 -96 86 -94 96 -88 L96 6 C86 0 70 -2 50 8 C10 28 -20 -14 -56 6 Z'
    fl = "".join(f'<path d="{wave}" fill="url(#{p}c)" transform="translate({k*1.1:.1f} {k*1.3:.1f})"/>' for k in range(7, 0, -1))
    fl += (f'<path d="{wave}" fill="url(#{p}a)"/><path d="M-56 -88 C-20 -108 10 -66 50 -86 C70 -96 86 -94 96 -88 L96 -60 '
           f'C70 -66 40 -50 10 -60 C-20 -70 -40 -60 -56 -56 Z" fill="url(#{p}b)"/>')
    return f'<svg class="{cls}" viewBox="-120 -120 240 240">{grads(p)}<g transform="rotate(8) translate(0 10)">{fl}{pole}</g></svg>'


def mic(p="m", cls="obj"):
    cap = 'x="-38" y="-100" width="76" height="130" rx="38"'
    body = "".join(f'<rect {cap} fill="url(#{p}c)" transform="translate({k*1.3:.1f} {k*1.1:.1f})"/>' for k in range(9, 0, -1))
    body += f'<rect {cap} fill="url(#{p}a)"/><rect x="-28" y="-92" width="30" height="96" rx="15" fill="url(#{p}b)"/>'
    body += "".join(f'<rect x="-22" y="{-70+i*16}" width="44" height="5" rx="2.5" fill="#ffffff" opacity=".28"/>' for i in range(4))
    holder = f'<path d="M-62 -6 a62 62 0 0 0 124 0" fill="none" stroke="url(#{p}c)" stroke-width="14" stroke-linecap="round" transform="translate(3 5)"/>'
    holder += f'<path d="M-62 -6 a62 62 0 0 0 124 0" fill="none" stroke="url(#{p}a)" stroke-width="14" stroke-linecap="round"/>'
    stand = f'<rect x="-7" y="56" width="14" height="40" rx="7" fill="url(#{p}c)"/><ellipse cy="98" rx="44" ry="12" fill="url(#{p}c)"/><ellipse cy="94" rx="44" ry="12" fill="url(#{p}a)"/>'
    return f'<svg class="{cls}" viewBox="-120 -120 240 240">{grads(p)}<g transform="rotate(-12) translate(0 -4)">{stand}{holder}{body}</g></svg>'
