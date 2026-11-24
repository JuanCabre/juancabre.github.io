# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: appointment committees for professorships (W3) and their reviewers.** They open the site while evaluating an application, often next to the written CV, and want to judge in a short visit whether Juan's research program, leadership, teaching, and output fit a professorship.
- **Secondary: students.** Prospective doctoral researchers and M.Sc. students who want to see who Juan is, what he works on, what he teaches, and whether to approach him.
- **Also served: peer researchers** looking for a paper, the publication list, or a contact for collaboration.

## Product Purpose

A public online CV that presents Juan A. Cabrera as a candidate for a professorship. It exists to advertise him: his research program, the systems it leads to, his leadership, teaching, and supervision, and his complete publication record.

Success: within about a minute a visitor understands the program (the task as the unit by which networks are designed and operated, in networks for physical AI where humans and embodied AI agents share one world) and sees that it ends in running systems and demonstrators. They can then reach a paper, the CV PDF, the publication list, or contact him without searching. The goal behind every visit is that he is hired as a professor.

## Positioning

One coherent research program, from information theory (post-Shannon communication, identification codes) and network coding to emulators, testbeds, and demonstrators that visitors interact with. The site shows this path from theory to systems with real papers, demonstrators, patents, funded projects, and a spin-off, rather than a list of topics.

## Operating Context

- Two pages: an About page drawn from the CV, and a Publications page with charts, a coauthor diagram, and a searchable library. A printable publication list is also produced as a PDF.
- The CV PDF is built from `CV-Web.tex` in the CV repository (JuanCabre/DFG-CV). The site and the three CVs must state the same facts.
- Committees read it alongside application documents, usually on a desktop; students and peers also arrive on phones.

## Capabilities and Constraints

- Static site built by `build.py` (Python 3.10+, no dependencies), deployed by GitHub Pages on every push to `main`.
- `data/publications.bib` is the single source for the publications page, the counts on the About page, and the downloadable `.bib`.
- Privacy by construction: no cookies and no requests to other servers. Fonts, scripts, and styles live in the repository. The only exception is the cookieless GoatCounter tag, guarded by a test.
- Content is general and CV-based: no details of specific applications and no funding amounts.
- English only, in American English, with no em dashes.
- Titles follow the verified CV wording. Juan leads CeTI's computing and communication area, but "Research Area Leader" is never used as a title.

## Brand Commitments

- Name as shown: Juan A. Cabrera. Affiliation: Junior Research Group Leader at CeTI, TU Dresden; company name "Ecologic-Computing" with a hyphen.
- First-person voice in the prose, factual and precise, with claims stated together with their limits (for example, what a study does not yet measure).

## Evidence on Hand

- Portrait, CV PDF (`static/cv/`), the complete bibliography (`data/publications.bib`), and the demonstrator, patent, funding, teaching, and supervision facts in `pages/index.html`.
- Awards: Best Demo Award (IEEE CCNC 2024) and Best Paper Award (TNT workshop at IEEE/IFIP NOMS 2022). Two granted German patents.
- No testimonials, quotes, or photos of demonstrators are on hand. Do not invent them.

## Product Principles

1. Serve the committee first: the program, leadership, and record must be clear without scrolling through everything.
2. Show, then prove: every claim leads to a paper, a demonstrator, or a document.
3. One set of facts: the site never contradicts the CVs.
4. Respect visitors: no tracking beyond the one cookieless counter, nothing loaded from elsewhere.
5. Stay general: the site works for every application without being rewritten for one.
