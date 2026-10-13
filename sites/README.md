# Sites

Each folder is the source for one claude.ai artifact. To change a site, edit the files and republish to the same URL, until that site launches on its own web host: then the rule for it changes (Full Bars: see below).

| Site | Business | Artifact |
|---|---|---|
| `full-bars/` | Full Bars: refurbished phones, trade-ins, repairs (56 pages) | https://claude.ai/artifact/HEK3scAViRCuUpxaqYHggT |
| `chainline/` | Chainline Cycles: refurbished bikes, e-bikes, workshop (one page) | https://claude.ai/artifact/XYbfVPYMWfnf7nN511v8iN |

Both are dark only, on purpose. Stock, prices and contact details are placeholders in [square brackets]. Checkout and forms aren't connected to anything, and each page says so.

## Publishing Full Bars

Full Bars is a multi-page site. `index.html` is the artifact's page; every other file in the folder goes up with it as a supporting file, keeping its path. Leave `404.html` out: it uses root-relative links meant for a real web host.

The site is set to `noindex` and `robots.txt` blocks crawlers while it's a preview. At launch, `launch/full-bars/go_live.py` switches both (and everything else) on a copy, and that switched copy goes on Full Bars' own web host at www.fullbars.co.uk (`launch/full-bars/GO-LIVE.md`, section 7). The artifact stays a preview copy: never publish the switched site to it.

**After launch**, `sites/full-bars` holds the switched, live site (GO-LIVE section 7 copies it back), so changes to it go to the web host, not to the artifact. Republish the artifact only from a preview copy (for example the folder as it was before `go_live.py` ran), or stop updating it. Never republish it from `sites/full-bars` once that folder is the live site.

## Other shops

Grace & Bloom (`grace-and-bloom/`) and Second Rail (`site/`) live on their own pull requests until they're merged.
