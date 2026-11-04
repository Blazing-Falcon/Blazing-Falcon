"""Render the profile README images from config.json and stats.json.

Writes assets/{terminal,tech-stack,commits,button}-{dark,light}.svg.
Standard library only, so it runs on a bare GitHub Actions runner.
"""
import base64
import json
from datetime import date
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "assets"

W = 1000
CW = 9.0      # JetBrains Mono advance is 600/1000 em at 15px
LH = 19
PAD = 32
LOGO_W = 360  # 40 text columns

# Layer letters used in logos/*.txt and the palette colour each one takes.
LAYER_FILL = {"f": "fg", "e": "fg", "1": "t2", "2": "t2", "3": "t3", "4": "t3", "5": "t4", "d": "border"}
BLOCKS = {"█": (0, 1), "▀": (0, 0.5), "▄": (0.5, 1), "░": (0, 1)}


def load_json(name):
    return json.loads((HERE / name).read_text())


def font_css():
    out = ""
    for weight, name in ((400, "Regular"), (800, "ExtraBold")):
        b64 = base64.b64encode((HERE / "fonts" / f"JetBrainsMono-{name}.subset.woff2").read_bytes()).decode()
        out += f'@font-face{{font-family:"JBM";font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format("woff2")}}'
    return out


def css_vars(v):
    out = [f"--{k}:{v[k]}" for k in ("bg", "bar", "border", "fg", "sub", "dim", "user", "host", "path", "prompt", "key", "accent", "warm")]
    out += [f"--a{i}:{c}" for i, c in enumerate(v["ansi"])]
    out += [f"--b{i}:{c}" for i, c in enumerate(v["bright"])]
    out += [f"--t{i}:{c}" for i, c in enumerate(v["tint"])]
    return ":root{" + ";".join(out) + "}"


class Renderer:
    def __init__(self, cfg, stats, palette):
        self.cfg, self.stats = cfg, stats
        self.vars = css_vars(palette["v"])
        self.fonts = font_css()
        self.user, self.host = cfg["user"], cfg["host"]

    def svg(self, width, height, title, body):
        css = (
            self.vars + self.fonts +
            "text{font-family:JBM,ui-monospace,Menlo,Consolas,monospace;font-size:15px;fill:var(--fg);white-space:pre}"
            ".b{font-weight:800}.sub{fill:var(--sub)}.dim{fill:var(--dim)}.user{fill:var(--user)}.host{fill:var(--host)}"
            ".path{fill:var(--path)}.prompt{fill:var(--prompt)}.key{fill:var(--key)}.accent{fill:var(--accent)}"
            + "".join(f".a{i}{{fill:var(--a{i})}}.b{i}{{fill:var(--b{i})}}" for i in range(8)) +
            ".cur{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
            "@media (prefers-reduced-motion:reduce){.cur{animation:none}}"
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t"><title id="t">{escape(title)}</title>'
            f"<style>{css}</style>{body}</svg>\n"
        )

    def window(self, height, title):
        return (
            f'<rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="14" fill="var(--bg)" stroke="var(--border)" stroke-width="2"/>'
            f'<path d="M15 1h{W - 30}a14 14 0 0 1 14 14v25H1V15A14 14 0 0 1 15 1z" fill="var(--bar)"/>'
            f'<line x1="1" y1="40" x2="{W - 1}" y2="40" stroke="var(--border)" stroke-width="2"/>'
            '<circle cx="26" cy="21" r="6.5" fill="var(--a1)"/><circle cx="48" cy="21" r="6.5" fill="var(--a3)"/>'
            '<circle cx="70" cy="21" r="6.5" fill="var(--a2)"/>'
            f'<text x="{W / 2}" y="26" text-anchor="middle" class="sub" style="font-size:13px">{escape(title)}</text>'
        )

    def prompt(self, y, cmd):
        return (
            f'<text x="{PAD}" y="{y}"><tspan class="user b">{self.user}</tspan><tspan class="sub">@</tspan>'
            f'<tspan class="host b">{self.host}</tspan><tspan class="path"> ~ </tspan><tspan class="prompt b">❯</tspan> {escape(cmd)}</text>'
        )

    def languages(self):
        skip = set(self.cfg["skip_language_names"])
        return [name.lower() for name, _ in self.stats["languages"] if name not in skip]

    def logo(self, y0):
        lines = (HERE / "logos" / f'{self.cfg["logo"]}.txt').read_text().rstrip("\n").split("\n")
        split = lines.index("----")
        art, lay = lines[:split], lines[split + 1:]
        lay += [""] * (len(art) - len(lay))
        x0 = PAD + max(0, (LOGO_W - max(len(a) for a in art) * CW) / 2)
        out = []
        for r, (a, l) in enumerate(zip(art, lay)):
            l = l.ljust(len(a))
            base = y0 + r * LH
            fill = lambda c: LAYER_FILL.get(l[c], "fg")
            c = 0
            while c < len(a):
                # One rect per run of identical block characters, so no seams show between cells.
                if a[c] in BLOCKS:
                    ch, f, s = a[c], fill(c), c
                    while c < len(a) and a[c] == ch and fill(c) == f:
                        c += 1
                    top, bot = BLOCKS[ch]
                    out.append(f'<rect x="{x0 + s * CW:.1f}" y="{base + top * LH:.1f}" width="{(c - s) * CW:.1f}" '
                               f'height="{(bot - top) * LH + 0.5:.1f}" fill="var(--{f})"/>')
                elif a[c] != " ":
                    f, s = fill(c), c
                    while c < len(a) and a[c] not in BLOCKS and a[c] != " " and fill(c) == f:
                        c += 1
                    out.append(f'<text x="{x0 + s * CW:.1f}" y="{base + 14}" style="fill:var(--{f})">{escape(a[s:c])}</text>')
                else:
                    c += 1
        return "".join(out), len(art) * LH

    def terminal(self):
        st = self.stats
        y = 72
        parts = [self.prompt(y, "fastfetch")]
        top = y + 18
        logo, logo_h = self.logo(top)
        parts.append(logo)
        values = {
            "uptime": uptime(date.fromisoformat(st["since"]), date.fromisoformat(st["today"])),
            "repos": st["repos"],
            "languages": ", ".join(self.languages()[: self.cfg["fetch_languages"]]),
            "website": self.cfg["website"],
        }
        rows = [(k, v.format(**values)) for k, v in self.cfg["fetch"]]
        ix = PAD + LOGO_W + 40
        ty = top + 14
        parts.append(f'<text x="{ix}" y="{ty}"><tspan class="user b">{self.user}</tspan><tspan class="sub">@</tspan>'
                     f'<tspan class="host b">{self.host}</tspan></text>')
        ty += LH
        parts.append(f'<text x="{ix}" y="{ty}" class="sub">{"-" * (len(self.user) + 1 + len(self.host))}</text>')
        for k, v in rows:
            ty += LH
            parts.append(f'<text x="{ix}" y="{ty}"><tspan class="key b">{escape(k)}</tspan><tspan class="sub">: </tspan>{escape(v)}</text>')
        ty += LH
        for r, prefix in enumerate(("a", "b")):
            for i in range(8):
                parts.append(f'<rect x="{ix + i * 3 * CW}" y="{ty + 6 + r * LH}" width="{3 * CW}" height="{LH}" fill="var(--{prefix}{i})"/>')
        y = top + max(logo_h, ty + 2 * LH + 6 - top) + 34
        parts.append(self.prompt(y, ""))
        cx = PAD + (len(self.user) + len(self.host) + 6) * CW
        parts.append(f'<rect class="cur" x="{cx}" y="{y - 13}" width="{CW}" height="17" fill="var(--fg)"/>')
        height = y + 30
        title = "Terminal running fastfetch, an FK logo next to system info. " + "; ".join(f"{k}: {v}" for k, v in rows)
        return self.svg(W, height, title, self.window(height, f"{self.user}@{self.host}: ~") + "".join(parts))

    def tech_stack(self):
        y = 72
        parts = [self.prompt(y, "tree ~/tech-stack")]
        y += 28
        parts.append(f'<text x="{PAD}" y="{y}" class="path b">~/tech-stack</text>')
        groups = [(n, cls, self.languages() if items == "{languages}" else items) for n, cls, items in self.cfg["tech_stack"]]
        for i, (name, cls, items) in enumerate(groups):
            y += 26
            branch = "└── " if i == len(groups) - 1 else "├── "
            line = "  ".join(f'<tspan class="{cls}">{escape(it)}</tspan>' for it in items)
            parts.append(f'<text x="{PAD}" y="{y}"><tspan class="dim">{branch}</tspan><tspan class="path b">{escape(name)}/</tspan></text>')
            parts.append(f'<text x="{PAD + 18 * CW}" y="{y}">{line}</text>')
        y += 38
        files = sum(len(items) for _, _, items in groups)
        parts.append(f'<text x="{PAD}" y="{y}" class="sub">{len(groups)} directories, {files} files</text>')
        height = y + 30
        title = "Tech stack as a directory tree. " + "; ".join(f"{n}: {', '.join(it)}" for n, _, it in groups)
        return self.svg(W, height, title, self.window(height, f"{self.user}@{self.host}: ~/tech-stack") + "".join(parts))

    def commits(self):
        st = self.stats
        y = 72
        parts = [self.prompt(y, "git stats --by-year")]
        years = st["commits_by_year"]
        most = max([n for _, n in years] + [1])
        bar_x, bar_w = PAD + 6 * CW, 64 * CW
        for yr, n in years:
            y += 26
            w = 0 if n == 0 else max(CW * 0.5, bar_w * n / most)
            parts.append(f'<text x="{PAD}" y="{y}" class="sub">{yr}</text>')
            parts.append(f'<rect x="{bar_x}" y="{y - 12}" width="{bar_w}" height="14" rx="2" fill="var(--border)"/>')
            if w:
                parts.append(f'<rect x="{bar_x}" y="{y - 12}" width="{w:.1f}" height="14" rx="2" fill="var(--key)"/>')
            parts.append(f'<text x="{bar_x + bar_w + 2 * CW}" y="{y}" class="b">{n:,}</text>')
        total = sum(n for _, n in years)
        y += 32
        parts.append(f'<text x="{PAD}" y="{y}"><tspan class="key b">{total:,}</tspan><tspan class="sub"> commits · </tspan>'
                     f'<tspan class="key b">{st["streak"]}</tspan><tspan class="sub">-day streak (best {st["best"]}) · </tspan>'
                     f'<tspan class="key b">{st["contributions"]:,}</tspan><tspan class="sub"> contributions</tspan></text>')
        y += 40
        recent = st["recent_commits"]
        parts.append(self.prompt(y, f"git log --oneline -{len(recent)}"))
        name_w = max([len(c["repo"]) for c in recent] + [1])
        for c in recent:
            y += 24
            d = date.fromisoformat(c["date"])
            msg = c["message"] if len(c["message"]) <= 52 else c["message"][:51] + "…"
            parts.append(f'<text x="{PAD}" y="{y}"><tspan class="a3">{escape(c["sha"])}</tspan>  <tspan class="sub">{d.day:>2} {d:%b}</tspan>  '
                         f'<tspan class="path">{escape(c["repo"].ljust(name_w))}</tspan>  {escape(msg)}</text>')
        height = y + 30
        title = (f"Commits per year: " + ", ".join(f"{yr}: {n}" for yr, n in years) +
                 f". {total} commits, {st['streak']}-day streak, best {st['best']}. Latest: " +
                 "; ".join(f"{c['repo']}: {c['message']}" for c in recent))
        return self.svg(W, height, title, self.window(height, f"{self.user}@{self.host}: ~/commits") + "".join(parts))

    def button(self):
        w, h = 340, 56
        body = (
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="12" fill="var(--bg)" stroke="var(--border)" stroke-width="2"/>'
            f'<text x="{w / 2}" y="34" text-anchor="middle" style="font-size:17px"><tspan class="prompt b">❯ </tspan>'
            f'<tspan class="b">{escape(self.cfg["website"])}</tspan><tspan class="sub"> ↗</tspan></text>'
        )
        return self.svg(w, h, f'Visit {self.cfg["website"]}', body)


def uptime(since, today):
    months = (today.year - since.year) * 12 + today.month - since.month - (today.day < since.day)
    y, m = divmod(months, 12)
    return f"{y} year{'s' * (y != 1)}, {m} month{'s' * (m != 1)}"


def main():
    cfg, stats, pals = load_json("config.json"), load_json("stats.json"), load_json("palettes.json")
    dark = pals[cfg["palette"]]
    light = pals[dark["light"]] if dark["light"] else dark
    OUT.mkdir(exist_ok=True)
    for suffix, palette in (("dark", dark), ("light", light)):
        r = Renderer(cfg, stats, palette)
        for name, build in (("terminal", r.terminal), ("tech-stack", r.tech_stack), ("commits", r.commits), ("button", r.button)):
            (OUT / f"{name}-{suffix}.svg").write_text(build())


if __name__ == "__main__":
    main()
