"""Generate the README artwork in assets/ (dark + light variants).

    python scripts/build_assets.py

Text is outlined to glyph paths (Manrope, IBM Plex Mono, SIL OFL) because
GitHub serves SVGs under a CSP that can block embedded fonts. Each glyph is
defined once per file and placed with <use>. Every motion respects
prefers-reduced-motion.
"""
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
OUT = ROOT / "assets"

THEMES = {
    "dark": dict(bg="#070914", panel="#0b1020", panel2="#10172a", line="#1b2236", line2="#2a3350",
                 text="#e9edfb", soft="#b4bdd9", muted="#7d87a4", violet="#8b5cf6", violet2="#a78bfa",
                 cyan="#67e8f9", green="#4ade80", grid="#d2dcff", grid_op=".07", glow=".28", on_grad="#0b1020"),
    "light": dict(bg="#f5f7fb", panel="#ffffff", panel2="#eef1f8", line="#dfe4f0", line2="#c6cee2",
                  text="#151821", soft="#3d4559", muted="#68708a", violet="#7c3aed", violet2="#6d28d9",
                  cyan="#0e7490", green="#15803d", grid="#151821", grid_op=".07", glow=".12", on_grad="#ffffff"),
}

# ---------------------------------------------------------------- fonts
class Face:
    """One static font instance: glyph advances, pair kerning, outlines."""

    def __init__(self, key, font):
        self.key, self.font = key, font
        self.cmap, self.hmtx = font.getBestCmap(), font["hmtx"]
        self.upm = font["head"].unitsPerEm
        self.glyphs = font.getGlyphSet()
        self.pairs = []  # PairPos subtables, read lazily in kern()
        if "GPOS" in font:
            for lk in font["GPOS"].table.LookupList.Lookup:
                for st in lk.SubTable:
                    st = st.ExtSubTable if lk.LookupType == 9 else st
                    if getattr(st, "LookupType", lk.LookupType) == 2:
                        self.pairs.append(st)

    def kern(self, a, b):
        for st in self.pairs:
            cov = st.Coverage.glyphs
            if a not in cov:
                continue
            if st.Format == 1:
                for rec in st.PairSet[cov.index(a)].PairValueRecord:
                    if rec.SecondGlyph == b:
                        return getattr(rec.Value1, "XAdvance", 0) or 0
            else:
                c1 = st.ClassDef1.classDefs.get(a, 0)
                c2 = st.ClassDef2.classDefs.get(b, 0)
                v = st.Class1Record[c1].Class2Record[c2].Value1
                x = getattr(v, "XAdvance", 0) or 0
                if x:
                    return x
        return 0

    def layout(self, s):
        """[(glyph, x in font units)], total advance in font units."""
        missing = {c for c in s if ord(c) not in self.cmap}
        assert not missing, f"{self.key} lacks glyphs: {missing!r}"
        names = [self.cmap[ord(c)] for c in s]
        out, x = [], 0
        for i, g in enumerate(names):
            out.append((g, x))
            x += self.hmtx[g][0] + (self.kern(g, names[i + 1]) if i + 1 < len(names) else 0)
        return out, x

    def path(self, g, dx=0):
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{round(v)}")
        self.glyphs[g].draw(TransformPen(pen, (1, 0, 0, 1, dx, 0)) if dx else pen)
        return pen.getCommands()


_FACES = {}


def face(weight, mono):
    key = "plex" if mono else f"manrope{weight}"
    if key not in _FACES:
        if mono:
            f = TTFont(FONTS / "IBMPlexMono-Medium.woff2")
        else:
            f = instancer.instantiateVariableFont(TTFont(FONTS / "Manrope-Variable.woff2"), {"wght": weight})
        _FACES[key] = Face(key, f)
    return _FACES[key]


def text_width(s, size, weight=500, mono=False, ls=0.0):
    f = face(weight, mono)
    return f.layout(s)[1] * size / f.upm + ls * max(len(s) - 1, 0)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- document
CSS = """
.fx{transform-box:fill-box;transform-origin:center}
@keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}
@keyframes flow{to{stroke-dashoffset:-100}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes ring{0%{transform:scale(.35);opacity:.85}100%{transform:scale(1.7);opacity:0}}
@keyframes grow{from{transform:scaleX(0)}}
@keyframes wave{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
@keyframes lit{0%{opacity:0}3%,17%{opacity:1}22%,100%{opacity:0}}
@keyframes say{0%,4%{opacity:0;transform:translateY(8px)}10%,86%{opacity:1;transform:none}94%,100%{opacity:0}}
.pulse{animation:pulse 2.6s ease-in-out infinite}
.flow{stroke-dasharray:7 93;animation:flow 3.2s linear infinite}
.spin{animation:spin 26s linear infinite}
.ring{animation:ring 3s cubic-bezier(.16,1,.3,1) infinite}
.grow{transform-origin:left;transform-box:fill-box;animation:grow 1.8s cubic-bezier(.16,1,.3,1) both}
.wave{animation:wave 1.4s ease-in-out infinite}
.bob{animation:bob 6s ease-in-out infinite}
.caret{animation:blink 1.1s steps(1) infinite}
.lit{animation:lit 7.5s linear infinite}
.say{animation:say 9s cubic-bezier(.16,1,.3,1) infinite}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


class Doc:
    def __init__(self, w, h, theme, title, desc):
        self.w, self.h, self.c = w, h, THEMES[theme]
        self.title, self.desc = title, desc
        self.parts, self.css = [], ""
        self.glyph_ids, self.extra_defs = {}, []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size, fill, weight=500, mono=False, anchor="start", ls=0):
        """Outlined text; (x, y) is the baseline origin, like <text>."""
        f = face(weight, mono)
        run, adv = f.layout(s)
        k = size / f.upm
        lsu = ls / k
        total = adv + lsu * max(len(s) - 1, 0)
        x -= {"start": 0, "middle": total * k / 2, "end": total * k}[anchor]
        if fill == "url(#g)":
            # Gradients restart per <use>, so gradient runs get one path with offsets baked in.
            gid = f"tg{len(self.extra_defs)}"
            self.extra_defs.append(
                f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{total:.0f}" y2="0">'
                f'<stop stop-color="{self.c["violet2"]}"/><stop offset="1" stop-color="{self.c["cyan"]}"/></linearGradient>')
            d = "".join(f.path(g, gx + lsu * i) for i, (g, gx) in enumerate(run))
            self.add(f'<path fill="url(#{gid})" transform="translate({x:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})" d="{d}"/>')
            return
        uses = []
        for i, (g, gx) in enumerate(run):
            key = (f.key, g)
            if key not in self.glyph_ids:
                d = f.path(g)
                self.glyph_ids[key] = (f"q{len(self.glyph_ids)}" if d else None, d)
            gid = self.glyph_ids[key][0]
            if gid:
                uses.append(f'<use href="#{gid}" x="{gx + lsu * i:.0f}"/>')
        self.add(f'<g fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})">{"".join(uses)}</g>')

    def frame(self, r=26):
        c = self.c
        self.add(f'<rect x=".5" y=".5" width="{self.w-1}" height="{self.h-1}" rx="{r}" fill="{c["bg"]}" stroke="{c["line"]}"/>')
        self.add(f'<rect x=".5" y=".5" width="{self.w-1}" height="{self.h-1}" rx="{r}" fill="url(#dots)" mask="url(#fade)"/>')

    def chip(self, x, y, label, color, dot=True, pulse=True):
        """Mono pill. Returns its width."""
        w = text_width(label, 11, mono=True, ls=1.4) + (34 if dot else 22)
        c = self.c
        self.add(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="26" rx="13" fill="{color}" fill-opacity=".1" '
                 f'stroke="{color}" stroke-opacity=".35"/>')
        tx = x + 11
        if dot:
            self.add(f'<circle cx="{x+14}" cy="{y+13}" r="3.5" fill="{color}" class="{"pulse" if pulse else ""}"/>')
            tx = x + 24
        self.text(tx, y + 17.5, label, 11, color, 500, mono=True, ls=1.4)
        return w

    def arrow(self, x, y, color, s=14):
        self.add(f'<path d="M{x} {y+s}L{x+s} {y}M{x+4} {y}H{x+s}V{y+s-4}" fill="none" stroke="{color}" '
                 f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')

    def check(self, x, y, color):
        self.add(f'<path d="M{x} {y}l4 4 8-9" fill="none" stroke="{color}" stroke-width="2" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')

    def render(self):
        c = self.c
        defs = f"""<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{c['violet2']}"/><stop offset="1" stop-color="{c['cyan']}"/></linearGradient>
<linearGradient id="gv" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{c['violet']}" stop-opacity=".22"/><stop offset="1" stop-color="{c['violet']}" stop-opacity="0"/></linearGradient>
<radialGradient id="glow"><stop stop-color="{c['violet']}" stop-opacity="{c['glow']}"/><stop offset="1" stop-color="{c['violet']}" stop-opacity="0"/></radialGradient>
<radialGradient id="glowc"><stop stop-color="{c['cyan']}" stop-opacity=".22"/><stop offset="1" stop-color="{c['cyan']}" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{c['grid']}" fill-opacity="{c['grid_op']}"/></pattern>
<radialGradient id="fadeg" cx=".75" cy=".3" r=".8"><stop stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="fade"><rect width="{self.w}" height="{self.h}" fill="url(#fadeg)"/></mask>
<clipPath id="clip"><rect width="{self.w}" height="{self.h}" rx="20"/></clipPath>
</defs>"""
        glyphs = "".join(f'<path id="{i}" d="{d}"/>' for i, d in self.glyph_ids.values() if i)
        defs = defs.replace("</defs>", glyphs + "".join(self.extra_defs) + "</defs>")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-labelledby="t d"><title id="t">{esc(self.title)}</title><desc id="d">{esc(self.desc)}</desc>'
                f'<style>{CSS}{self.css}</style>{defs}' + "".join(self.parts) + "</svg>\n")


# ---------------------------------------------------------------- assets
def hero(d):
    c = d.c
    d.frame(30)
    d.add(f'<circle cx="790" cy="270" r="260" fill="url(#glow)"/>')
    # brand row
    d.add(f'<circle cx="58" cy="54" r="11" fill="none" stroke="{c["violet2"]}" stroke-width="2.5"/>'
          f'<circle cx="58" cy="54" r="4" fill="{c["cyan"]}" class="pulse"/>')
    d.text(80, 58.5, "OSAMA IFTIKHAR", 12, c["text"], mono=True, ls=2.2)
    d.chip(944 - text_width("AVAILABLE · DUBAI, UAE", 11, mono=True, ls=1.4) - 34, 41, "AVAILABLE · DUBAI, UAE", c["green"])
    # headline
    d.text(56, 160, "GENAI & LLM ENGINEER", 13, c["violet2"], mono=True, ls=2.6)
    d.text(53, 232, "LLM systems that", 64, c["text"], 800, ls=-2)
    d.text(53, 304, "finish the job.", 64, "url(#g)", 800, ls=-2)
    d.add(f'<rect x="{56 + text_width("finish the job.", 64, 800, ls=-2) + 6:.1f}" y="256" width="5" height="52" rx="2" fill="{c["cyan"]}" class="caret"/>')
    d.text(56, 354, "Fine-tuned models, RAG, multi-agent and voice systems,", 18, c["soft"])
    d.text(56, 380, "shipped to production for teams across the EU, UAE & US.", 18, c["soft"])
    x = 56
    for label in ["4+ YRS SHIPPING", "500+ LIVE CALLS", "4 MARKETS"]:
        d.add(f'<rect x="{x}" y="424" width="3" height="18" rx="1.5" fill="{c["violet"]}"/>')
        d.text(x + 12, 438, label, 12, c["muted"], mono=True, ls=1.6)
        x += text_width(label, 12, mono=True, ls=1.6) + 38
    mesh(d, 612, 104, 336, 352)


def mesh(d, px, py, pw, ph):
    """The PRODUCTION TOPOLOGY panel: an agent core wired to six satellites."""
    c = d.c
    sx, sy = pw / 336, (ph - 90) / 262
    d.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="22" fill="{c["panel"]}" fill-opacity=".72" stroke="{c["line2"]}"/>')
    d.text(px + 20, py + 30, "PRODUCTION TOPOLOGY", 10, c["muted"], mono=True, ls=1.6)
    d.text(px + pw - 20, py + 30, "AGENT.MESH", 10, c["violet2"], mono=True, ls=1.6, anchor="end")
    d.add(f'<path d="M{px} {py+46}H{px+pw}" stroke="{c["line"]}"/>')
    cx, cy = px + pw / 2, py + 46 + (ph - 90) / 2 + 4
    nodes = [(n, round(dx * sx), round(dy * sy)) for n, dx, dy in
             [("voice", -108, -84), ("rag", 108, -84), ("tools", 128, 14), ("crm", 74, 92),
              ("evals", -74, 92), ("guard", -128, 14)]]
    for i, (_, dx, dy) in enumerate(nodes):
        d.add(f'<path d="M{cx} {cy}L{cx+dx} {cy+dy}" stroke="{c["line2"]}" stroke-width="1.2"/>')
        d.add(f'<path d="M{cx+dx} {cy+dy}L{cx} {cy}" pathLength="100" stroke="{c["cyan"] if i % 2 else c["violet2"]}" '
              f'stroke-width="2.4" stroke-linecap="round" class="flow" style="animation-delay:-{i*0.55:.2f}s"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="74" fill="none" stroke="{c["line2"]}" stroke-dasharray="2 7" class="spin fx"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="40" fill="{c["violet"]}" fill-opacity=".16" class="ring fx"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="34" fill="{c["panel2"]}" stroke="url(#g)" stroke-width="2"/>')
    d.text(cx, cy + 4.5, "agent", 13, c["text"], 700, anchor="middle")
    for i, (name, dx, dy) in enumerate(nodes):
        w = text_width(name, 11, mono=True) + 22
        d.add(f'<g class="bob" style="animation-delay:-{i*1.1:.1f}s"><rect x="{cx+dx-w/2:.1f}" y="{cy+dy-13}" width="{w:.1f}" height="26" rx="8" '
              f'fill="{c["panel2"]}" stroke="{c["line2"]}"/>')
        d.text(cx + dx, cy + dy + 4, name, 11, c["soft"], mono=True, anchor="middle")
        d.add("</g>")
    d.add(f'<path d="M{px} {py+ph-44}H{px+pw}" stroke="{c["line"]}"/>')
    d.add(f'<circle cx="{px+24}" cy="{py+ph-22}" r="4" fill="{c["green"]}" class="pulse"/>')
    d.text(px + 36, py + ph - 18, "ONLINE", 10, c["green"], mono=True, ls=1.6)
    d.text(px + pw - 20, py + ph - 18, "retries · evals · rollback", 10, c["muted"], mono=True, anchor="end")


def metrics(d):
    c = d.c
    data = [("92%", .92, "task completion on live voice calls", "500+ calls · Global Health"),
            ("~50%", .50, "faster average time-to-answer", "Fine-tuned search · Hatzs"),
            ("~3 in 4", .75, "routine inbound calls, no human", "Aerlou front desk")]
    w, gap = 316, 26
    for i, (big, frac, cap, src) in enumerate(data):
        x = i * (w + gap) + 1
        d.add(f'<rect x="{x}" y="1" width="{w-2}" height="{d.h-2}" rx="20" fill="{c["panel"]}" stroke="{c["line"]}"/>')
        d.add(f'<circle cx="{x+w-60}" cy="50" r="50" fill="url(#glow)"/>')
        d.text(x + 24, 38, f"0{i+1}", 11, c["muted"], mono=True, ls=1.4)
        d.check(x + 50, 31, c["green"])
        d.text(x + 70, 38, "VERIFIED", 11, c["green"], mono=True, ls=1.4)
        d.text(x + 22, 102, big, 52, "url(#g)", 800, ls=-1.5)
        d.text(x + 24, 132, cap, 15, c["soft"])
        d.text(x + 24, 156, src, 11, c["muted"], mono=True, ls=.6)
        d.add(f'<rect x="{x+24}" y="174" width="{w-50}" height="4" rx="2" fill="{c["line"]}"/>')
        d.add(f'<rect x="{x+24}" y="174" width="{(w-50)*frac:.1f}" height="4" rx="2" fill="url(#g)" class="grow" '
              f'style="animation-delay:{.2+i*.25:.2f}s"/>')


def pipeline(d):
    c = d.c
    d.frame(26)
    d.text(36, 50, "LIVE CALL TRACE", 12, c["violet2"], mono=True, ls=2)
    d.text(36, 82, "One call, five hops, a finished task.", 26, c["text"], 800, ls=-.6)
    d.text(964, 50, "illustrative · not live data", 11, c["muted"], mono=True, anchor="end", ls=.6)
    stages = [("call.in", "Twilio · ElevenLabs"), ("intent.detected", "multilingual LLM"),
              ("retrieve()+tool()", "RAG + calendar, CRM"), ("guard", "confidence check"),
              ("crm.synced", "task completed")]
    x0, y0, bw, bh, gap = 36, 118, 166, 120, 23
    lane_y = y0 + bh / 2
    d.add(f'<path d="M{x0} {lane_y}H{x0+5*bw+4*gap}" stroke="{c["line2"]}" stroke-dasharray="3 6"/>')
    for i, (name, sub) in enumerate(stages):
        x = x0 + i * (bw + gap)
        d.add(f'<rect x="{x}" y="{y0}" width="{bw}" height="{bh}" rx="16" fill="{c["panel"]}" stroke="{c["line2"]}"/>')
        d.add(f'<rect x="{x}" y="{y0}" width="{bw}" height="{bh}" rx="16" fill="url(#gv)" stroke="url(#g)" stroke-width="2" '
              f'opacity="0" class="lit" style="animation-delay:{i*1.5:.1f}s"/>')
        d.text(x + 16, y0 + 28, f"0{i+1}", 10, c["muted"], mono=True, ls=1.2)
        d.text(x + 16, y0 + 84, name, 12.5 if len(name) > 14 else 14, c["text"], mono=True)
        d.text(x + 16, y0 + 104, sub, 12.5, c["muted"])
        if i == 0:
            for k in range(9):
                h = [10, 22, 34, 18, 28, 14, 30, 20, 12][k]
                d.add(f'<rect x="{x+16+k*7}" y="{y0+56-h/2}" width="3.5" height="{h}" rx="1.75" fill="{c["cyan"]}" '
                      f'class="wave fx" style="animation-delay:-{k*.17:.2f}s"/>')
        elif i == 3:
            d.add(f'<path d="M{x+16} {y0+44}h112" stroke="{c["line"]}" stroke-width="5" stroke-linecap="round"/>'
                  f'<path d="M{x+16} {y0+44}h92" stroke="url(#g)" stroke-width="5" stroke-linecap="round" class="grow"/>'
                  f'<path d="M{x+122} {y0+36}v16" stroke="{c["muted"]}" stroke-width="1.5"/>')
        elif i == 4:
            d.add(f'<circle cx="{x+30}" cy="{y0+50}" r="13" fill="{c["green"]}" fill-opacity=".14"/>')
            d.check(x + 24, y0 + 50, c["green"])
        else:
            for k in range(3):
                d.add(f'<rect x="{x+16}" y="{y0+40+k*9}" width="{[96, 70, 84][k] if i == 1 else [60, 104, 78][k]}" height="4" rx="2" '
                      f'fill="{c["violet2"] if k == 0 else c["line2"]}"/>')
    span = 5 * bw + 4 * gap
    d.css += f"@keyframes travel{{from{{transform:translateX(0)}}to{{transform:translateX({span}px)}}}}" \
             ".packet{animation:travel 7.5s linear infinite}"
    d.add(f'<path d="M{x0} {y0+bh+26}H{x0+span}" stroke="{c["line"]}"/>')
    d.add(f'<g class="packet"><circle cx="{x0}" cy="{y0+bh+26}" r="9" fill="url(#glowc)" transform="scale(1)"/>'
          f'<circle cx="{x0}" cy="{y0+bh+26}" r="4" fill="{c["cyan"]}"/></g>')
    d.text(x0, y0 + bh + 62, "low confidence  →  escalate to a human, never guess on medical-adjacent questions", 12,
           c["muted"], mono=True, ls=.3)


# project cards ----------------------------------------------------------
def motif(d, kind, x, y):
    """Small animated emblem in a 96x96 box at (x, y)."""
    c = d.c
    d.add(f'<rect x="{x}" y="{y}" width="96" height="96" rx="20" fill="{c["panel2"]}" stroke="{c["line"]}"/>')
    cx, cy = x + 48, y + 48
    if kind == "voice":
        for k in range(7):
            h = [16, 34, 52, 40, 56, 30, 18][k]
            d.add(f'<rect x="{x+20+k*8.5}" y="{cy-h/2}" width="4.5" height="{h}" rx="2.25" fill="url(#g)" '
                  f'class="wave fx" style="animation-delay:-{k*.21:.2f}s"/>')
    elif kind == "docs":
        for k in range(3):
            d.add(f'<rect x="{x+26+k*6}" y="{y+18+k*6}" width="38" height="50" rx="5" fill="{c["panel"]}" stroke="{c["line2"]}"/>')
        for k in range(4):
            d.add(f'<rect x="{x+44}" y="{y+42+k*8}" width="{[22, 16, 20, 12][k]}" height="3" rx="1.5" fill="{c["line2"]}"/>')
        d.css += "@keyframes sweep{0%,100%{transform:translateY(0)}50%{transform:translateY(42px)}}.sweep{animation:sweep 3.4s ease-in-out infinite}"
        d.add(f'<rect x="{x+34}" y="{y+32}" width="46" height="2.5" rx="1.25" fill="{c["cyan"]}" class="sweep"/>')
    elif kind == "fanout":
        d.add(f'<circle cx="{x+24}" cy="{cy}" r="7" fill="url(#g)"/>')
        for k, dy in enumerate((-26, 0, 26)):
            d.add(f'<path d="M{x+30} {cy}C{x+50} {cy} {x+52} {cy+dy} {x+70} {cy+dy}" fill="none" stroke="{c["line2"]}" stroke-width="1.5"/>')
            d.add(f'<path d="M{x+30} {cy}C{x+50} {cy} {x+52} {cy+dy} {x+70} {cy+dy}" pathLength="100" fill="none" stroke="{c["cyan"]}" '
                  f'stroke-width="2.4" stroke-linecap="round" class="flow" style="animation-delay:-{k*1:.1f}s"/>')
            d.add(f'<circle cx="{x+74}" cy="{cy+dy}" r="5" fill="{c["panel"]}" stroke="{c["violet2"]}" stroke-width="2"/>')
    elif kind == "gauge":
        d.add(f'<path d="M{x+20} {cy+14}A28 28 0 0 1 {x+76} {cy+14}" fill="none" stroke="{c["line2"]}" stroke-width="7" stroke-linecap="round"/>')
        d.add(f'<path d="M{x+20} {cy+14}A28 28 0 0 1 {x+76} {cy+14}" pathLength="100" fill="none" stroke="url(#g)" stroke-width="7" '
              f'stroke-linecap="round" stroke-dasharray="78 100"/>')
        d.css += "@keyframes needle{0%,100%{transform:rotate(-70deg)}55%{transform:rotate(48deg)}}" \
                 f".needle{{transform-origin:{cx}px {cy+14}px;animation:needle 4s cubic-bezier(.16,1,.3,1) infinite}}"
        d.add(f'<path d="M{cx} {cy+14}V{cy-10}" stroke="{c["text"]}" stroke-width="2.5" stroke-linecap="round" class="needle"/>')
        d.add(f'<circle cx="{cx}" cy="{cy+14}" r="4" fill="{c["text"]}"/>')
    elif kind == "search":
        for k in range(4):
            d.add(f'<rect x="{x+18}" y="{y+22+k*10}" width="{[44, 30, 50, 36][k]}" height="4" rx="2" fill="{c["line2"]}"/>')
        d.css += "@keyframes lens{0%,100%{transform:translate(0,0)}33%{transform:translate(-14px,-12px)}66%{transform:translate(-4px,-22px)}}" \
                 ".lens{animation:lens 5s ease-in-out infinite}"
        d.add(f'<g class="lens"><circle cx="{x+56}" cy="{y+56}" r="14" fill="{c["cyan"]}" fill-opacity=".12" stroke="url(#g)" stroke-width="3"/>'
              f'<path d="M{x+66} {y+66}l12 12" stroke="{c["violet2"]}" stroke-width="4" stroke-linecap="round"/></g>')
    elif kind == "pin":
        d.add(f'<path d="M{x+16} {y+74}h64" stroke="{c["line2"]}" stroke-width="2"/>')
        for k, (bx, bh) in enumerate(((22, 22), (38, 36), (56, 28))):
            d.add(f'<rect x="{x+bx}" y="{y+74-bh}" width="14" height="{bh}" rx="2" fill="{c["panel"]}" stroke="{c["line2"]}"/>')
        d.add(f'<g class="bob"><path d="M{cx+16} {y+40}c0-8 -6-13 -12-13s-12 5 -12 13c0 9 12 18 12 18s12-9 12-18z" fill="url(#g)"/>'
              f'<circle cx="{cx+4}" cy="{y+39}" r="4" fill="{c["panel2"]}"/></g>')


def card(d, p):
    c = d.c
    d.add(f'<rect x=".5" y=".5" width="{d.w-1}" height="{d.h-1}" rx="22" fill="{c["panel"]}" stroke="{c["line"]}"/>')
    d.add(f'<circle cx="{d.w-60}" cy="60" r="130" fill="url(#glow)" clip-path="url(#clip)"/>')
    live = p["status"] == "LIVE"
    w = d.chip(28, 28, p["status"], c["green"] if live else c["violet2"], pulse=live)
    d.text(28 + w + 12, 45.5, p["dates"], 11, c["muted"], mono=True, ls=.8)
    motif(d, p["motif"], d.w - 124, 28)
    d.text(27, 166, p["name"], 34, c["text"], 800, ls=-1)
    d.text(28, 192, p["kicker"], 11, c["violet2"], mono=True, ls=1.4)
    for k, line in enumerate(p["lines"]):
        d.text(28, 222 + k * 22, line, 15, c["soft"])
    d.add(f'<path d="M28 {d.h-52}H{d.w-28}" stroke="{c["line"]}"/>')
    d.text(28, d.h - 24, p["role"], 11, c["muted"], mono=True, ls=1)
    d.text(d.w - 52, d.h - 24, "open", 11, c["text"], mono=True, ls=1, anchor="end")
    d.arrow(d.w - 44, d.h - 36, c["cyan"], 12)


def flagship(d):
    c = d.c
    d.frame(26)
    d.add(f'<circle cx="760" cy="170" r="240" fill="url(#glowc)"/>')
    d.chip(36, 32, "FLAGSHIP SYSTEM · LIVE NOW", c["green"])
    d.text(36, 116, "Global Health", 48, c["text"], 800, ls=-1.6)
    d.text(38, 144, "AI ENGINEER – TEAM LEAD, AGENT DEVELOPMENT · JUN 2025 – NOW", 11, c["violet2"], mono=True, ls=1.2)
    d.text(38, 180, "LLM agents that run patient intake, scheduling and FAQs", 17, c["soft"])
    d.text(38, 204, "across four country clinic portals, in chat and on the phone.", 17, c["soft"])
    x = 38
    for tag in ["LLM agents", "RAG", "Tool calling", "ElevenLabs", "Twilio"]:
        w = text_width(tag, 12, mono=True) + 22
        d.add(f'<rect x="{x}" y="226" width="{w:.1f}" height="26" rx="8" fill="{c["panel2"]}" stroke="{c["line2"]}"/>')
        d.text(x + 11, 243.5, tag, 12, c["soft"], mono=True)
        x += w + 8
    d.text(38, 296, "92% task completion · 500+ live calls · EN ES PT CS", 12, c["muted"], mono=True, ls=.8)
    d.text(570, 296, "open live", 12, c["text"], mono=True, ls=1, anchor="end")
    d.arrow(578, 284, c["cyan"], 12)
    transcript(d, 616, 32, 348, 276)


def transcript(d, px, py, pw, ph):
    """Illustrative call: question, tool call, answer, CRM sync, revealed in turn."""
    c = d.c
    d.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="20" fill="{c["panel"]}" stroke="{c["line2"]}"/>')
    d.add(f'<circle cx="{px+22}" cy="{py+24}" r="4" fill="#f87171" class="pulse"/>')
    d.text(px + 34, py + 28, "CALL · 00:41 · ES → EN", 10, c["muted"], mono=True, ls=1.2)
    for k in range(5):
        h = [8, 16, 12, 18, 9][k]
        d.add(f'<rect x="{px+pw-60+k*7}" y="{py+24-h/2}" width="3.5" height="{h}" rx="1.75" fill="{c["cyan"]}" class="wave fx" '
              f'style="animation-delay:-{k*.2:.1f}s"/>')
    d.add(f'<path d="M{px} {py+44}H{px+pw}" stroke="{c["line"]}"/>')

    def bubble(y, lines, mine, delay):
        w = max(text_width(s, 13) for s in lines) + 28
        h = 18 * len(lines) + 16
        bx = px + pw - 18 - w if mine else px + 18
        d.add(f'<g class="say" style="animation-delay:{delay}s"><rect x="{bx:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="12" '
              f'fill="{"url(#g)" if mine else c["panel2"]}" {"" if mine else f"stroke={chr(34)}{c["line2"]}{chr(34)}"}/>')
        for i, s in enumerate(lines):
            d.text(bx + 14, y + 22 + i * 18, s, 13, c["on_grad"] if mine else c["text"], 600 if mine else 500)
        d.add("</g>")

    bubble(py + 60, ["Can I move my appointment", "to Friday morning?"], False, 0)
    d.add(f'<g class="say" style="animation-delay:1.4s">')
    d.text(px + 18, py + 150, "tool  calendar.reschedule()", 11, c["violet2"], mono=True)
    d.check(px + pw - 34, py + 145, c["green"])
    d.add("</g>")
    bubble(py + 166, ["Done – Friday 10:30 is booked.", "Confirmation is on its way."], True, 2.4)
    d.add(f'<g class="say" style="animation-delay:3.6s">')
    d.text(px + 18, py + ph - 20, "crm.synced  ·  handoff: none", 11, c["green"], mono=True)
    d.add("</g>")


def stack(d):
    c = d.c
    d.frame(26)
    d.text(36, 50, "CAPABILITY MATRIX", 12, c["violet2"], mono=True, ls=2)
    d.text(36, 82, "One engineer across the whole LLM stack.", 26, c["text"], 800, ls=-.6)
    d.text(964, 50, "67 tools · each shipped in something real", 11, c["muted"], mono=True, anchor="end", ls=.6)
    x0, y0, w, gap, h = 36, 112, 214, 16, 250
    for i, col in enumerate(STACK_COLS):
        x = x0 + i * (w + gap)
        stack_col(d, x, y0, w, h, col)
        if i < 3:
            ax = x + w + gap / 2
            d.add(f'<path d="M{ax-5} {y0+h/2-6}l6 6-6 6" fill="none" stroke="{c["muted"]}" stroke-width="1.6" stroke-linecap="round"/>')
    d.css += f"@keyframes scan{{0%{{transform:translateY(0);opacity:0}}10%,90%{{opacity:1}}100%{{transform:translateY({h-4}px);opacity:0}}}}" \
             ".scan{animation:scan 6s cubic-bezier(.65,0,.35,1) infinite}"
    d.add(f'<rect x="{x0}" y="{y0+2}" width="{4*w+3*gap}" height="2" fill="url(#g)" opacity=".7" class="scan"/>')


def connect(d):
    c = d.c
    d.frame(28)
    cx, cy = 840, 130
    for k in range(3):
        d.add(f'<circle cx="{cx}" cy="{cy}" r="60" fill="none" stroke="{c["violet2"]}" stroke-width="1.5" class="ring fx" '
              f'style="animation-delay:{k}s"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="30" fill="{c["panel2"]}" stroke="url(#g)" stroke-width="2"/>')
    d.add(f'<path d="M{cx-12} {cy-8}h24v16h-24z M{cx-12} {cy-8}l12 9 12-9" fill="none" stroke="{c["text"]}" stroke-width="2" stroke-linejoin="round"/>')
    d.chip(40, 36, "AVAILABLE FOR THE RIGHT BUILD", c["green"])
    d.text(38, 116, "Need someone who can carry AI", 36, c["text"], 800, ls=-1.2)
    d.text(38, 158, "from first sketch to production?", 36, "url(#g)", 800, ls=-1.2)
    w = text_width("osamaifti@gmail.com", 14, mono=True) + 64
    d.add(f'<rect x="40" y="186" width="{w:.1f}" height="44" rx="22" fill="{c["text"]}"/>')
    d.text(62, 213, "osamaifti@gmail.com", 14, c["bg"], mono=True)
    d.arrow(40 + w - 34, 201, c["bg"], 12)
    d.text(40 + w + 22, 213, "Dubai, UAE · EU / UAE / US timezones", 12, c["muted"], mono=True, ls=.4)


STACK_COLS = [
    ("MODEL", "26", "AI systems", ["Llama · Mistral · GPT", "LoRA / PEFT fine-tuning", "RAG pipeline design",
                                   "Multi-agent orchestration", "LangChain · LlamaIndex", "ElevenLabs · Whisper"]),
    ("DATA", "18", "Data & ML", ["PyTorch · TensorFlow", "Hugging Face", "scikit-learn", "Pandas · NumPy · SQL",
                                 "OCR & document intake", "Power BI · Tableau"]),
    ("APP", "16", "Production", ["MLflow · Kubeflow · DVC", "Docker · Kubernetes", "Azure ML · Functions",
                                 "Evals: hallucination rate", "A/B testing", "Token-usage monitoring"]),
    ("SHIP", "07", "Cloud & infra", ["Microsoft Azure", "Twilio", "n8n", "Salesforce", "MySQL · Hadoop", "Postman"]),
]


def stack_col(d, x, y, w, h, col):
    c = d.c
    tag, n, title, tools = col
    d.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{c["panel"]}" stroke="{c["line"]}"/>')
    d.text(x + 18, y + 30, tag, 11, c["violet2"], mono=True, ls=1.8)
    d.text(x + w - 18, y + 30, f"{n} TOOLS", 11, c["muted"], mono=True, ls=1, anchor="end")
    d.text(x + 18, y + 62, title, 19, c["text"], 700, ls=-.3)
    for k, t in enumerate(tools):
        ty = y + 98 + k * 27
        d.add(f'<circle cx="{x+22}" cy="{ty-4}" r="2.5" fill="{c["cyan"] if k == 0 else c["line2"]}"/>')
        d.text(x + 34, ty, t, 13, c["soft"])


# mobile layouts (served below 600px) --------------------------------------
def hero_m(d):
    c = d.c
    d.frame(26)
    d.add(f'<circle cx="300" cy="520" r="240" fill="url(#glow)"/>')
    d.add(f'<circle cx="40" cy="44" r="10" fill="none" stroke="{c["violet2"]}" stroke-width="2.5"/>'
          f'<circle cx="40" cy="44" r="3.5" fill="{c["cyan"]}" class="pulse"/>')
    d.text(60, 48.5, "OSAMA IFTIKHAR", 12, c["text"], mono=True, ls=2)
    d.chip(452 - text_width("DUBAI", 11, mono=True, ls=1.4) - 34, 31, "DUBAI", c["green"])
    d.text(30, 112, "GENAI & LLM ENGINEER", 13, c["violet2"], mono=True, ls=2.4)
    d.text(27, 172, "LLM systems", 56, c["text"], 800, ls=-2)
    d.text(27, 234, "that finish", 56, c["text"], 800, ls=-2)
    d.text(27, 296, "the job.", 56, "url(#g)", 800, ls=-2)
    d.add(f'<rect x="{30 + text_width("the job.", 56, 800, ls=-2) + 6:.1f}" y="254" width="5" height="46" rx="2" fill="{c["cyan"]}" class="caret"/>')
    for k, s in enumerate(["Fine-tuned models, RAG, multi-agent and", "voice systems, shipped for teams across", "the EU, UAE & US."]):
        d.text(30, 342 + k * 26, s, 18, c["soft"])
    mesh(d, 24, 438, 432, 300)


def metrics_m(d):
    c = d.c
    data = [("92%", .92, "task completion on", "live voice calls", "500+ calls · Global Health"),
            ("~50%", .50, "faster average", "time-to-answer", "Fine-tuned search"),
            ("~3 in 4", .75, "routine inbound calls", "with no human", "Aerlou front desk")]
    for i, (big, frac, l1, l2, src) in enumerate(data):
        y = i * 132 + 1
        d.add(f'<rect x="1" y="{y}" width="{d.w-2}" height="120" rx="20" fill="{c["panel"]}" stroke="{c["line"]}"/>')
        d.add(f'<circle cx="80" cy="{y+60}" r="60" fill="url(#glow)"/>')
        d.text(22, y + 74, big, 48 if len(big) < 5 else 40, "url(#g)", 800, ls=-1.5)
        d.check(232, y + 28, c["green"])
        d.text(252, y + 35, "VERIFIED", 11, c["green"], mono=True, ls=1.4)
        d.text(232, y + 62, l1, 16, c["soft"])
        d.text(232, y + 84, l2, 16, c["soft"])
        d.add(f'<rect x="22" y="{y+98}" width="{d.w-46}" height="4" rx="2" fill="{c["line"]}"/>')
        d.add(f'<rect x="22" y="{y+98}" width="{(d.w-46)*frac:.1f}" height="4" rx="2" fill="url(#g)" class="grow" '
              f'style="animation-delay:{.2+i*.25:.2f}s"/>')


def flagship_m(d):
    c = d.c
    d.frame(26)
    d.add(f'<circle cx="360" cy="440" r="220" fill="url(#glowc)"/>')
    d.chip(24, 24, "FLAGSHIP · LIVE NOW", c["green"])
    d.text(23, 104, "Global Health", 46, c["text"], 800, ls=-1.6)
    d.text(25, 132, "AI ENGINEER – TEAM LEAD, AGENTS", 11, c["violet2"], mono=True, ls=1.2)
    for k, s in enumerate(["Patient intake, scheduling and FAQs across", "four clinic portals, in chat and on the phone."]):
        d.text(25, 166 + k * 24, s, 17, c["soft"])
    transcript(d, 24, 222, 432, 268)
    d.text(25, 522, "92% COMPLETION · 500+ LIVE CALLS", 12, c["text"], mono=True, ls=1)
    d.text(25, 546, "EN ES PT CS", 12, c["muted"], mono=True, ls=1)
    d.text(430, 546, "open live", 12, c["text"], mono=True, ls=1, anchor="end")
    d.arrow(438, 534, c["cyan"], 12)


def pipeline_m(d):
    c = d.c
    d.frame(26)
    d.text(28, 44, "LIVE CALL TRACE", 12, c["violet2"], mono=True, ls=2)
    d.text(28, 80, "One call, five hops,", 28, c["text"], 800, ls=-.8)
    d.text(28, 114, "a finished task.", 28, "url(#g)", 800, ls=-.8)
    stages = [("call.in", "Twilio · ElevenLabs"), ("intent.detected", "multilingual LLM"),
              ("retrieve()+tool()", "RAG + calendar, CRM"), ("guard", "confidence check"),
              ("crm.synced", "task completed")]
    x, y0, bw, bh, step = 64, 142, 392, 72, 84
    lane = 38
    d.add(f'<path d="M{lane} {y0+bh/2}V{y0+4*step+bh/2}" stroke="{c["line2"]}" stroke-dasharray="3 6"/>')
    for i, (name, sub) in enumerate(stages):
        y = y0 + i * step
        d.add(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="16" fill="{c["panel"]}" stroke="{c["line2"]}"/>')
        d.add(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="16" fill="url(#gv)" stroke="url(#g)" stroke-width="2" '
              f'opacity="0" class="lit" style="animation-delay:{i*1.5:.1f}s"/>')
        d.add(f'<circle cx="{lane}" cy="{y+bh/2}" r="5" fill="{c["panel2"]}" stroke="{c["line2"]}" stroke-width="1.5"/>')
        d.text(x + 18, y + 31, name, 16, c["text"], mono=True)
        d.text(x + 18, y + 54, sub, 14, c["muted"])
        d.text(x + bw - 18, y + 31, f"0{i+1}", 11, c["muted"], mono=True, anchor="end", ls=1.2)
    span = 4 * step
    d.css += f"@keyframes travelY{{0%{{transform:translateY(0)}}80%,100%{{transform:translateY({span}px)}}}}" \
             ".packetY{animation:travelY 7.5s linear infinite}"
    d.add(f'<g class="packetY"><circle cx="{lane}" cy="{y0+bh/2}" r="11" fill="url(#glowc)"/>'
          f'<circle cx="{lane}" cy="{y0+bh/2}" r="5" fill="{c["cyan"]}"/></g>')
    d.text(28, d.h - 40, "low confidence  →  escalate to a human", 12, c["muted"], mono=True, ls=.3)
    d.text(28, d.h - 20, "illustrative · not live data", 11, c["muted"], mono=True, ls=.6)


def stack_m(d):
    c = d.c
    d.frame(26)
    d.text(24, 44, "CAPABILITY MATRIX", 12, c["violet2"], mono=True, ls=2)
    d.text(24, 80, "One engineer across", 28, c["text"], 800, ls=-.8)
    d.text(24, 114, "the whole LLM stack.", 28, c["text"], 800, ls=-.8)
    w, h, gap = 208, 268, 16
    for i, col in enumerate(STACK_COLS):
        tag, n, title, tools = col
        x, y = 24 + (i % 2) * (w + gap), 140 + (i // 2) * (h + gap)
        stack_col(d, x, y, w, h, (tag, n, title, [t.replace(" · ", ", ") if len(t) > 22 else t for t in tools]))


def connect_m(d):
    c = d.c
    d.frame(26)
    cx, cy = 404, 60
    for k in range(3):
        d.add(f'<circle cx="{cx}" cy="{cy}" r="34" fill="none" stroke="{c["violet2"]}" stroke-width="1.5" class="ring fx" '
              f'style="animation-delay:{k}s"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="22" fill="{c["panel2"]}" stroke="url(#g)" stroke-width="2"/>')
    d.add(f'<path d="M{cx-9} {cy-6}h18v12h-18z M{cx-9} {cy-6}l9 7 9-7" fill="none" stroke="{c["text"]}" stroke-width="1.8" stroke-linejoin="round"/>')
    d.chip(24, 28, "AVAILABLE", c["green"])
    for k, (s, fill) in enumerate([("Need someone who", c["text"]), ("can carry AI from", c["text"]),
                                   ("first sketch to", "url(#g)"), ("production?", "url(#g)")]):
        d.text(23, 120 + k * 44, s, 38, fill, 800, ls=-1.2)
    w = d.w - 48
    d.add(f'<rect x="24" y="276" width="{w}" height="52" rx="26" fill="{c["text"]}"/>')
    d.text(48, 307, "osamaifti@gmail.com", 17, c["bg"], mono=True)
    d.arrow(24 + w - 38, 295, c["bg"], 14)
    d.text(24, 360, "Dubai, UAE · EU / UAE / US timezones", 12, c["muted"], mono=True, ls=.4)


def card_m(d, p):
    c = d.c
    d.add(f'<rect x=".5" y=".5" width="{d.w-1}" height="{d.h-1}" rx="18" fill="{c["panel"]}" stroke="{c["line"]}"/>')
    d.add(f'<circle cx="{d.w-40}" cy="70" r="100" fill="url(#glow)" clip-path="url(#clip)"/>')
    live = p["status"] == "LIVE"
    d.chip(16, 16, "LIVE" if live else "CASE", c["green"] if live else c["violet2"], pulse=live)
    d.text(16, 70, p["dates"], 11, c["muted"], mono=True, ls=.6)
    motif(d, p["motif"], d.w - 112, 16)
    size = 30
    while text_width(p["name"], size, 800, ls=-1) > d.w - 32:
        size -= 1
    d.text(15, 172, p["name"], size, c["text"], 800, ls=-1)
    kicker = p["kicker"].split(" · ")[0]
    while text_width(kicker, 11, mono=True, ls=1) > d.w - 32:
        kicker = kicker.rsplit(" ", 1)[0]
    d.text(16, 198, kicker, 11, c["violet2"], mono=True, ls=1)
    d.add(f'<path d="M16 {d.h-54}H{d.w-16}" stroke="{c["line"]}"/>')
    role = p["role"]
    d.text(16, d.h - 24, role if len(role) <= 18 else role.split(" ")[-1], 11, c["muted"], mono=True, ls=.8)
    d.arrow(d.w - 32, d.h - 36, c["cyan"], 14)


PROJECTS = [
    dict(slug="aerlou", status="LIVE", dates="2024 – NOW", name="Aerlou", kicker="AI ASSISTANT & FRONT DESK",
         lines=["Voice notes and texts become reminders,", "meetings and memory. Calls get booked."],
         role="PRODUCT LEAD", motif="voice",
         alt="Aerlou. AI assistant and front desk. Turns voice notes and texts into reminders, meetings and memory, plus a call and SMS front desk that books into the CRM."),
    dict(slug="aertonic", status="CASE STUDY", dates="2024 – NOW", name="Aertonic", kicker="AI CONSTRUCTION OPS",
         lines=["RFIs drafted and chased, submittals", "checked, inside Procore and Aconex."],
         role="CO-FOUNDER & CTO", motif="docs",
         alt="Aertonic. AI construction operations assistant. RFI drafting and auto-chasing, submittal review and compliance checks inside Procore, Aconex and email."),
    dict(slug="jordy", status="LIVE", dates="2024 – NOW", name="Jordy", kicker="AUTONOMOUS AI SALES AGENT",
         lines=["A plain-language ICP becomes a multi-", "channel campaign that adapts to replies."],
         role="AI / BACKEND ENGINEER", motif="fanout",
         alt="Jordy. Autonomous AI sales agent. Turns a plain-language ideal customer description into a LinkedIn, email and X campaign that adapts to replies."),
    dict(slug="dealeriq", status="LIVE", dates="2023 – 2024", name="DealerIQ", kicker="DEALERSHIP AUTOMATION",
         lines=["Agents score leads, value vehicles live", "and run first-pass outreach."],
         role="LED DEVELOPMENT", motif="gauge",
         alt="DealerIQ. Automation platform for car dealerships. Multi-agent flows score leads, value vehicles in real time and run first-pass outreach."),
    dict(slug="knowledge-search", status="CASE STUDY", dates="2023 – 2024", name="Knowledge search", kicker="FINE-TUNED LLM · AZURE ML",
         lines=["Open-source LLM tuned on internal docs,", "with web retrieval and OCR. ~50% faster."],
         role="AI TEAM LEAD", motif="search",
         alt="Knowledge search. An open-source LLM fine-tuned on internal documents with web retrieval and OCR, in production on Azure ML. About 50 percent faster time-to-answer."),
    dict(slug="sbre", status="CASE STUDY", dates="2024 – 2025", name="SBRE", kicker="REAL ESTATE LEAD AGENTS",
         lines=["Agents answer property questions, check", "inventory and book viewings over SMS."],
         role="AI ENGINEER", motif="pin",
         alt="SBRE. Lead-qualification agents for real estate. Conversational and SMS agents answer property questions, check live inventory and book viewings."),
]

ASSETS = [
    ("hero", 1000, 500, hero, "Osama Iftikhar. LLM systems that finish the job.",
     "Animated agent mesh: an agent core connected to voice, RAG, tools, CRM, evals and guard nodes. Illustrative motion."),
    ("metrics", 1000, 196, metrics, "92% task completion, ~50% faster time-to-answer, ~3 in 4 calls resolved without a human.",
     "Three verified production metrics with animated progress bars."),
    ("global-health", 1000, 340, flagship, "Global Health. Flagship LLM voice and chat agents.",
     "Illustrative call transcript: a patient reschedules, the agent calls a calendar tool, confirms and syncs the CRM."),
    ("pipeline", 1000, 330, pipeline, "Live call trace: call in, intent detected, retrieve and tool, guard, CRM synced.",
     "A packet travels through five pipeline stages, lighting each in turn. Illustrative, not live data."),
    ("stack", 1000, 386, stack, "Capability matrix across model, data, app and ship layers.",
     "Four columns of tools with a scanning highlight."),
    ("connect", 1000, 262, connect, "Need someone who can carry AI from first sketch to production? osamaifti@gmail.com",
     "Contact card with pulsing rings around a mail icon."),
]


MOBILE = {"hero": (480, 760, hero_m), "metrics": (480, 386, metrics_m), "global-health": (480, 580, flagship_m),
          "pipeline": (480, 640, pipeline_m), "stack": (480, 720, stack_m), "connect": (480, 390, connect_m)}


def main():
    OUT.mkdir(exist_ok=True)
    total = 0
    jobs = list(ASSETS)
    jobs += [(f"{slug}-mobile", w, h, fn, a[4], a[5]) for a in ASSETS for slug, (w, h, fn) in [(a[0], MOBILE[a[0]])]]
    for p in PROJECTS:
        jobs.append((p["slug"], 490, 320, lambda d, p=p: card(d, p), p["alt"], "Project card with an animated emblem."))
        jobs.append((f'{p["slug"]}-mobile', 240, 280, lambda d, p=p: card_m(d, p), p["alt"], "Project card with an animated emblem."))
    for slug, w, h, fn, title, desc in jobs:
        for theme in THEMES:
            d = Doc(w, h, theme, title, desc)
            fn(d)
            path = OUT / f"{slug}-{theme}.svg"
            path.write_text(d.render(), encoding="utf-8")
            total += path.stat().st_size
    print(f"wrote {len(jobs) * 2} files, {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
