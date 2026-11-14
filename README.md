# Personal website of Juan A. Cabrera

A static site with two pages: an About page drawn from the CV, and a Publications page
with charts, a coauthor diagram, and a searchable library. It is built by one Python
script without any dependencies and published with GitHub Pages.

The publications page reuses the data pipeline and the visual language of the
[Publication Observatory](https://github.com/JuanCabre/publication-observatory),
restricted to one author.

## Build it locally

```
python build.py                      # writes _site/
python -m http.server -d _site 8000  # then open http://localhost:8000
python -m unittest discover -s tests -v
```

Python 3.10 or newer is enough.

The publication list is also offered as a PDF. The build prints it from
`publications/list/` with a Chromium-based browser if it finds one (Chrome, Chromium,
Edge, or the path in the `CHROME` environment variable). Without a browser the button
leads to the printable page instead. The deployment always makes the PDF.

## Where things live

| Path | What it is |
|---|---|
| `site.json` | Name, public address, description, optional custom domain |
| `data/publications.bib` | The complete publication list. The only source of the publications page |
| `data/venues.json` | Spellings of conference and journal names that count as one venue |
| `pages/` | The text of the pages (HTML with a few `@@PLACEHOLDERS@@`) |
| `templates/base.html` | The frame shared by all pages: navigation rail, footer |
| `templates/list.html` | The printable publication list, the source of the PDF |
| `static/` | Copied as it is: styles, scripts, fonts, portrait, the CV PDF |
| `pipeline/` | BibTeX parsing, duplicate removal, venue and name matching |
| `tests/` | Checks on the bibliography and on the built pages |

## Add or change a publication

Edit `data/publications.bib` and push. Everything on the publications page, the
counts on the About page, and the downloadable `.bib` follow from that file.

A few conventions decide how an entry is counted:

- `@article` is a journal article, `@inproceedings` a conference paper, `@incollection` a book chapter.
- `keywords = {preprint}`, `{dataset}`, `{patent}`, `{demo}` or `{workshop-abstract}` marks the other kinds.
- An award goes into `note`, for example `note = {Best Paper Award}`. The entry then gets a badge.
- When a preprint is published, replace its entry with the published one.
- Entries with the same DOI count once.

Coauthors named under `professors` in `site.json` are shown with "Prof." in the
coauthor diagram. Use the name exactly as the site shows it.

To show a paper on the About page, write `@@PUB:bibtexkey@@` in `pages/index.html`.
The build stops with a clear message if the key does not exist.

### New venue names

Conference names come in many spellings. After adding entries, run

```
python -m pipeline.venues --new      # lists names that have not been reviewed
python -m pipeline.venues --accept   # marks them as reviewed
```

If a new name is another spelling of a venue that is already listed, add it as an alias
in `data/venues.json` before accepting. The tests fail while unreviewed names remain.

## The CV

The site links to `static/cv/Juan-Cabrera-CV.pdf`. This PDF is the public CV variant
(`CV-Web.tex` in the CV repository), which leaves out contract details.

There are two ways to keep it current:

1. **By hand.** Compile `CV-Web.tex`, replace the PDF, push.
2. **Automatically.** The workflow compiles the CV from its LaTeX source on every
   deployment and once a week. To switch this on:
   1. Create an SSH key pair without a passphrase: `ssh-keygen -t ed25519 -f cv_key -N ""`.
   2. In the CV repository, add `cv_key.pub` under Settings → Deploy keys (read-only).
   3. In this repository, add the content of `cv_key` under Settings → Secrets and
      variables → Actions as `CV_REPO_DEPLOY_KEY`.

   The workflow refuses to publish if the compiled PDF contains contract details, and
   the site then stays as it was.

## Deployment

`.github/workflows/deploy.yml` tests, builds, and deploys on every push to `main`.
One setting is needed once: Settings → Pages → Build and deployment → Source →
**GitHub Actions**. Until that is set, nothing is published.

Pull requests are tested and built but not deployed.

## Use a custom domain

1. Set `custom_domain` (for example `"juancabrera.net"`) and `site_url`
   (`"https://juancabrera.net/"`) in `site.json`. The build then writes the `CNAME` file.
2. At the domain registrar, point the domain to GitHub Pages. For an apex domain these are
   `A` records to `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`;
   for a subdomain such as `www`, a `CNAME` record to `juancabre.github.io`.
3. In Settings → Pages, enter the domain and tick "Enforce HTTPS" once the certificate is issued.

## Privacy by construction

The pages set no cookies and load nothing from other servers: fonts, scripts, and styles
are part of the repository. A test guards this. The one exception is the cookieless
[GoatCounter](https://www.goatcounter.com/) counter (`templates/base.html` and
`templates/list.html`), described on the legal page; the test allows exactly that tag and
checks that every page carries it once. Dashboard: https://quitapesares.goatcounter.com/ The e-mail address is assembled in the
browser so that it does not sit in the page source as one string.
