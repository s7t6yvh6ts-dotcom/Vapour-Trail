# Sites

Each folder is the source for one claude.ai artifact. To change a site, edit the files and republish to the same URL.

| Site | Business | Artifact |
|---|---|---|
| `full-bars/` | Full Bars: refurbished phones, trade-ins, repairs (56 pages) | https://claude.ai/artifact/HEK3scAViRCuUpxaqYHggT |
| `chainline/` | Chainline Cycles: refurbished bikes, e-bikes, workshop (one page) | https://claude.ai/artifact/XYbfVPYMWfnf7nN511v8iN |

Both are dark only, on purpose. Stock, prices and contact details are placeholders in [square brackets]. Checkout and forms aren't connected to anything, and each page says so.

## Publishing Full Bars

Full Bars is a multi-page site. `index.html` is the artifact's page; every other file in the folder goes up with it as a supporting file, keeping its path. Leave `404.html` out: it uses root-relative links meant for a real web host.

The site is set to `noindex` and `robots.txt` blocks crawlers while it's a preview. At launch, swap both back (the comment in `robots.txt` says how).

## Other shops

Grace & Bloom (`grace-and-bloom/`) and Second Rail (`site/`) live on their own pull requests until they're merged.
