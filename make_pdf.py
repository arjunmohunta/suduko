"""Render FINAL_REPORT.md to a print-formatted PDF.

Requires WeasyPrint and its native dependencies:

    brew install pango
    pip3 install weasyprint markdown

On macOS WeasyPrint needs Homebrew's libraries on the loader path, which this
script sets for itself before importing, so a plain `python3 make_pdf.py` works:

Layout follows the structure the CS 175 final-report handout asks for:
a cover page with names / net IDs / student numbers, then the four required
sections, with figures and tables placed inline.
"""
import base64, datetime, os, re, sys

# WeasyPrint's native libs live under Homebrew on macOS; put them on the loader
# path before the import so this runs without an env-var prefix.
if sys.platform == "darwin":
    _brew = "/opt/homebrew/lib"
    if os.path.isdir(_brew) and _brew not in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", ""):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
            _brew + ":" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", ""))

import markdown
from weasyprint import HTML

REPO = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, "CS175_Final_Report_Group3.pdf")

md_src = open(os.path.join(REPO, "FINAL_REPORT.md"), encoding="utf-8").read()
body_md = md_src[md_src.index("## 1. Project Summary"):]

html = markdown.markdown(body_md, extensions=["tables", "fenced_code"])

# ---- embed figures as data URIs ------------------------------------------- #
def embed(m):
    alt, path = m.group(1), m.group(2)
    with open(os.path.join(REPO, path), "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}">'
html = re.sub(r'<img alt="([^"]*)" src="([^"]+)"\s*/?>', embed, html)

# image paragraph + following italic line -> a real figure with a caption
html = re.sub(
    r'<p>(<img src="data:image/png;base64,[^"]+" alt="[^"]*"[^>]*>)</p>\s*<p><em>(.*?)</em></p>',
    r'<figure>\1<figcaption>\2</figcaption></figure>',
    html, flags=re.S)

# ---- anchors + numbering -------------------------------------------------- #
# One pass in document order, so the table of contents lists headings in the
# order they actually appear rather than all h2s followed by all h3s.
toc_entries = []
_plain = [0]

def heading(m):
    level = int(m.group(1))
    text = m.group(2).strip()
    nm = re.match(r'^(\d+(?:\.\d+)*)\.?\s+(.*)$', text)
    if nm:
        num, rest = nm.group(1), nm.group(2)
        anchor = "sec" + num.replace(".", "_")
    else:
        num, rest = "", text
        _plain[0] += 1
        anchor = f"h{level}x{_plain[0]}"
    toc_entries.append((level, num, rest, anchor))
    numspan = f'<span class="num">{num}</span>' if num else ""
    if level == 2:
        return (f'<h2 id="{anchor}">{numspan}'
                f'<span class="txt">{rest}</span></h2>')
    return f'<h3 id="{anchor}">{numspan}{rest}</h3>'

html = re.sub(r'<h([23])>(.*?)</h\1>', heading, html, flags=re.S)

# ---- wide/prose tables ---------------------------------------------------- #
PROSE_COLS = ("Character", "Outcome", "Shows")
def wrap_table(m):
    inner = m.group(0)
    ncols = inner.count("<th>")
    cls = ["data"]
    if any(f"<th>{c}" in inner for c in PROSE_COLS):
        cls.append("prose")
    if ncols >= 7:
        cls.append("tight")
    return inner.replace("<table>", f'<table class="{" ".join(cls)}">', 1)
html = re.sub(r'<table>.*?</table>', wrap_table, html, flags=re.S)

# ---- table of contents ---------------------------------------------------- #
toc_rows = []
for level, num, title, anchor in toc_entries:
    if level == 2:
        toc_rows.append(
            f'<li class="l1"><a href="#{anchor}">'
            f'<span class="tnum">{num}</span>'
            f'<span class="ttitle">{title}</span></a></li>')
    else:
        label = f'<span class="tnum">{num}</span>' if num else '<span class="tnum"></span>'
        toc_rows.append(
            f'<li class="l2"><a href="#{anchor}">{label}'
            f'<span class="ttitle">{title}</span></a></li>')
toc_html = "\n".join(toc_rows)

CSS = """
@page{
  size: Letter;
  margin: 0.95in 0.9in 0.85in 0.9in;
  @top-left{
    content: "Solving and Generating Sudoku as a Constraint Satisfaction Problem";
    font-family: "Helvetica Neue", Helvetica, sans-serif; font-size: 7.6pt;
    color: #7a828d; padding-bottom: 5pt;
  }
  @top-right{
    content: "CS 175 · Group 3";
    font-family: "Helvetica Neue", Helvetica, sans-serif; font-size: 7.6pt;
    color: #7a828d; padding-bottom: 5pt;
  }
  @bottom-center{
    content: counter(page) " of " counter(pages);
    font-family: "Helvetica Neue", Helvetica, sans-serif; font-size: 8.2pt;
    color: #7a828d; padding-top: 7pt;
  }
}
@page cover{ margin: 1.5in 1.1in 1in 1.1in;
  @top-left{content:""} @top-right{content:""} @bottom-center{content:""} }
@page :first{ margin: 1.5in 1.1in 1in 1.1in;
  @top-left{content:""} @top-right{content:""} @bottom-center{content:""} }

html{ font-size: 10.5pt; }
body{
  font-family: Charter, Georgia, "Times New Roman", serif;
  color:#1c2027; line-height:1.5; margin:0;
  hyphens:auto; text-align:justify;
}

/* ---------------- cover ---------------- */
.cover{ page: cover; page-break-after: always; }
.cover .kicker{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:8.6pt; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:#2b6cb0;
  margin-bottom:26pt; text-align:left;
}
.cover h1{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:23pt; font-weight:600;
  line-height:1.2; letter-spacing:-.01em; color:#111418;
  margin:0 0 8pt; text-align:left;
}
.cover .subtitle{
  font-size:11pt; color:#4d566380; color:#4d5663; font-style:italic;
  margin:0 0 34pt; text-align:left;
}
.cover .rule{ border-top:1.6pt solid #111418; margin:0 0 20pt; }
.cover .meta{ text-align:left; font-size:10pt; }
.cover .meta .row{ margin-bottom:13pt; }
.cover .meta .lbl{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:7.8pt; font-weight:600;
  letter-spacing:.12em; text-transform:uppercase; color:#7a828d;
  display:block; margin-bottom:3pt;
}
.cover table.team{ width:100%; border-collapse:collapse; font-size:9.6pt; }
.cover table.team td{
  padding:3.5pt 0; border:0; text-align:left; vertical-align:baseline;
}
.cover table.team td.nm{ width:42%; }
.cover table.team td.id,.cover table.team td.sn{
  font-family:Menlo,"Courier New",monospace; font-size:8.8pt; color:#4d5663;
}
.cover .repo{
  font-family:Menlo,"Courier New",monospace; font-size:8.6pt; color:#2b6cb0;
  margin-top:4pt;
}
.cover .abstract{
  margin-top:30pt; padding:13pt 15pt; background:#f4f7fa;
  border-left:2.5pt solid #2b6cb0; font-size:9.6pt; line-height:1.5;
  text-align:left;
}
.cover .abstract b{ color:#111418; }

/* ---------------- contents ---------------- */
.toc{ page-break-after: always; }
.toc h2.tochead{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:13pt; font-weight:600;
  color:#111418; border-top:1.6pt solid #111418; padding-top:9pt;
  margin:0 0 14pt; text-align:left;
}
.toc ul{ list-style:none; margin:0; padding:0; }
.toc li{ margin:0; }
.toc a{
  text-decoration:none; color:#1c2027; display:block;
  font-family:"Helvetica Neue",Helvetica,sans-serif;
}
.toc a::after{
  content: target-counter(attr(href), page);
  float:right; font-size:8.8pt; color:#7a828d;
  font-family:Menlo,"Courier New",monospace;
}
.toc li.l1 a{
  font-size:10.4pt; font-weight:600; padding:7.5pt 0 3pt;
  border-bottom:.4pt solid #e2e7ed;
}
.toc li.l2 a{ font-size:9.3pt; color:#4d5663; padding:3pt 0 3pt 20pt; }
.toc .tnum{
  font-family:Menlo,"Courier New",monospace; font-size:8.6pt; color:#2b6cb0;
  display:inline-block; min-width:26pt;
}
.toc li.l2 .tnum{ min-width:30pt; }

/* ---------------- headings ---------------- */
h2{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:15pt; font-weight:600;
  color:#111418; letter-spacing:-.008em; line-height:1.22;
  margin:0 0 13pt; padding-top:10pt; border-top:1.6pt solid #111418;
  page-break-before: always; page-break-after: avoid; text-align:left;
}
h2 .num{ font-family:Menlo,"Courier New",monospace; font-size:9.6pt;
  color:#2b6cb0; margin-right:9pt; }
h3{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:11pt; font-weight:600;
  color:#111418; margin:19pt 0 7pt; line-height:1.3;
  page-break-after: avoid; text-align:left;
}
h3 .num{ font-family:Menlo,"Courier New",monospace; font-size:9pt;
  color:#2b6cb0; margin-right:7pt; }

p{ margin:0 0 8.5pt; orphans:3; widows:3; }
strong{ color:#111418; font-weight:600; }
a{ color:#2b6cb0; text-decoration:none; }

ul,ol{ margin:0 0 10pt; padding-left:17pt; }
li{ margin-bottom:4pt; text-align:left; }
ol li::marker{ font-family:Menlo,monospace; font-size:8.6pt; color:#2b6cb0; }

/* the two display equations */
blockquote{
  margin:11pt 0 13pt; padding:0; border:0; background:none;
  font-family:Charter,Georgia,serif; font-size:11pt; line-height:1.5;
  color:#111418; text-align:center; page-break-inside:avoid;
}
blockquote p{ margin:0; }
blockquote em{ font-style:italic; }
sub{ font-size:.72em; vertical-align:-.28em; font-style:italic; }

hr{ border:0; border-top:.5pt solid #e2e7ed; margin:14pt 0; }

code{ font-family:Menlo,"Courier New",monospace; font-size:8.7pt;
  background:#f2f5f8; padding:.5pt 2.5pt; color:#111418; }
pre{
  background:#f7f9fb; border:.5pt solid #e2e7ed; border-left:2pt solid #2b6cb0;
  padding:9pt 11pt; margin:0 0 11pt; font-size:7.9pt; line-height:1.42;
  page-break-inside:avoid; text-align:left; overflow:hidden;
}
pre code{ background:none; padding:0; font-size:7.9pt; }

/* ---------------- tables ---------------- */
table.data{
  border-collapse:collapse; width:100%; margin:0 0 12pt;
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:8.6pt;
  page-break-inside:avoid; text-align:left;
}
table.data.tight{ font-size:7.7pt; }
table.data th{
  font-size:7.2pt; font-weight:600; letter-spacing:.05em; text-transform:uppercase;
  color:#5b6675; text-align:left; padding:5pt 5pt; background:#f2f5f8;
  border-bottom:1pt solid #b9c2ce; border-top:.5pt solid #b9c2ce;
  vertical-align:bottom;
}
table.data.tight th{ font-size:6.6pt; padding:4pt 3.5pt; }
table.data td{
  padding:4.5pt 5pt; border-bottom:.4pt solid #e2e7ed; color:#1c2027;
  vertical-align:top; font-variant-numeric:tabular-nums;
}
table.data.tight td{ padding:3.5pt 3.5pt; }
table.data th:not(:first-child), table.data td:not(:first-child){ text-align:right; }
table.data td:first-child{
  font-family:Menlo,"Courier New",monospace; font-size:7.9pt; color:#111418;
}
table.data.tight td:first-child{ font-size:7.2pt; }
table.data.prose th, table.data.prose td{ text-align:left; }
table.data.prose td:first-child{
  font-family:Charter,Georgia,serif; font-size:8.8pt; color:#1c2027;
}
table.data.prose td:first-child strong{ color:#111418; }

/* ---------------- figures ---------------- */
figure{
  margin:13pt 0 15pt; padding:0; page-break-inside:avoid;
  border:.5pt solid #e2e7ed;
}
figure img{ display:block; width:100%; height:auto; }
figcaption{
  font-family:"Helvetica Neue",Helvetica,sans-serif; font-size:7.9pt;
  line-height:1.45; color:#5b6675; padding:6pt 8pt;
  border-top:.5pt solid #e2e7ed; background:#f7f9fb; text-align:left;
}
"""

COVER = """
<section class="cover">
  <div class="kicker">CS 175 · Project in Artificial Intelligence · Summer 10w 2026</div>
  <h1>Solving and Generating Sudoku as a Constraint Satisfaction Problem</h1>
  <p class="subtitle">Final Project Report</p>
  <div class="rule"></div>
  <div class="meta">
    <div class="row">
      <span class="lbl">Group Number</span>
      3
    </div>
    <div class="row">
      <span class="lbl">Team Members</span>
      <table class="team">
        <tr><td class="nm">Arjun Mohunta</td><td class="id">amohunta</td><td class="sn">80654131</td></tr>
        <tr><td class="nm">Haoyang Ding</td><td class="id">haoyad6</td><td class="sn">44024972</td></tr>
        <tr><td class="nm">Rajat Choudhary</td><td class="id">rajatc1</td><td class="sn">37222868</td></tr>
      </table>
    </div>
    <div class="row">
      <span class="lbl">Instructor</span>
      Kalev Kask
    </div>
    <div class="row">
      <span class="lbl">Date</span>
      __BUILD_DATE__
    </div>
    <div class="row">
      <span class="lbl">Source Code</span>
      <span class="repo">github.com/arjunmohunta/suduko</span>
    </div>
  </div>
  <div class="abstract">
    <b>Summary of results.</b> We model Sudoku as a CSP over 81 variables with 27 all-different
    constraints, and implement three solvers of increasing inferential strength: plain
    backtracking as a baseline, forward checking with the Minimum Remaining Values heuristic,
    and a third adding naked- and hidden-single propagation to a fixpoint. Over 5,946 puzzles
    drawn from six public benchmark sets, the informed solver reaches a <b>verified 100% solve
    rate</b>, while the baseline fails to solve a 17-clue instance after ten million search
    nodes. All 2,000 sampled Kaggle puzzles are solved with a <b>maximum of zero backtracks</b>.
    A generator produces puzzles that are unique by construction (90 of 90 verified). Stronger
    propagation cuts search by up to <b>12,827&times;</b> on minimal 17-clue puzzles &mdash; yet
    runs <b>1.45&times; slower</b> on easy puzzles, a cost/benefit crossover we quantify in
    Section&nbsp;3.3.
  </div>
</section>
"""

TOC_SECTION = f"""
<section class="toc">
  <h2 class="tochead">Contents</h2>
  <ul>{toc_html}</ul>
</section>
"""

COVER = COVER.replace("__BUILD_DATE__",
                      datetime.date.today().strftime("%B %-d, %Y"))

page = f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>CS 175 Final Report — Group 3</title>
<style>{CSS}</style>
</head><body>
{COVER}
{TOC_SECTION}
{html}
</body></html>"""

tmp_html = os.path.join(REPO, "results", "report_print.html")
os.makedirs(os.path.join(REPO, "results"), exist_ok=True)
open(tmp_html, "w", encoding="utf-8").write(page)
HTML(filename=tmp_html, base_url=REPO).write_pdf(OUT)
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1e6:.2f} MB)")
