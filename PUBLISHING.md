# Publishing an article across the websites

Use this runbook when bringing a new piece from Substack or a project repository into
The Margin of Error and the personal articles index. Preserve the author's prose, subtitle,
citations, captions, and footnotes, incorporating any edits explicitly requested by the author.
Do not replace the article with a generated summary.

## Repositories and destinations

| Repository | Branch | Responsibility |
|---|---|---|
| `margin_of_error` | `main` | Article, local images, homepage, archive, RSS, and publication deployment |
| `hanshanley.github.io` | `master` | Personal site's `/articles/` index, driven by `_data/writing.yml` |
| Project repository, when applicable | Check its current branch | Analysis code, datasets, figures, and interactive tools |

The publication is at `https://www.themarginoferror.com/`; the personal index is at
`https://www.hanshanley.com/articles/`. For the congressional-language project,
the code lives in `congressional_record` and the existing interactive dashboard is at
`https://www.themarginoferror.com/congressional_profanity/`.

The UK evidence project lives in `hanshanley/uk_decline` and is published at
`https://www.themarginoferror.com/uk_decline/`. Deployment checks out its `master`
branch, installs its small `requirements-site.txt`, and builds the saved figures,
downloads, and methodology directly into `public/uk_decline/`. The topic pages
embed their charts directly, without an iframe or a dependency on the personal site.
The UK project refreshes supported sources weekly; this publication picks up
successful saved updates during its twice-daily deployments.

The collective U.S.–China analysis is staged at `/china-us-relations/` from
`hanshanley/china-us-relation-change`. Deployment runs its offline
`scripts/build_exchange_publication.py` against the committed public snapshots.
It includes students, travel, immigration, goods/services trade, language, business and public
Weibo research aggregates, never raw posts or source PDFs/workbooks. For local
validation, stage the same export before `npm test`:

```bash
../china-us-relation-change/.venv/bin/python \
  ../china-us-relation-change/scripts/build_exchange_publication.py \
  --output public/china-us-relations
```

The public manifest records the source revision and complete-data checksums.
Travel keeps historical all-mode arrivals separate from recent NTTO air-survey
estimates; the 2026 air estimates cover January-June only. Immigration keeps UN
resident-stock benchmarks separate from fiscal-year permanent-resident grants,
and birthplace separate from nationality. Language defaults to actual
Chinese/Japanese/Korean college course enrollments, not global AP participation.
School enrollment estimates and reported high-school program availability are
separate dated snapshots, never a combined national learner count.
The exchange explorer has geography, direction, measure and display controls;
Travel & tourism has its own direct visitor-arrival view. Immigration has a
separate page for fiscal-year permanent-resident grants, not visas or visitor
trips; birthplace histories and the FY2025 nationality snapshot are not spliced.
The remaining topic pages have indicator selectors. Charts redraw for the screen rather
than requiring horizontal scrolling. Annual 2025 data and separate 2026
partial-year observations retain their actual periods; older series are not
extended artificially. Definitions, source restrictions and full tables remain
available, including without JavaScript. The website recolours
previews, while links marked `data-original-chart` retain the original Substack
and Margin of Error download backgrounds. Adding an analysis tool does not
create an article or require a personal-site writing-index entry.
Prepend new Interactive analysis entries; only the first preview loads eagerly.

Read each repository's instructions before editing. Work from the repository root unless a
command says otherwise. In this repository, `CLAUDE.md` is a symlink to `AGENTS.md`;
edit the shared instructions once, not through both filenames.

## 1. Establish the source and preserve existing work

In each repository being changed:

```bash
git status --short
git fetch origin
git branch --show-current
```

Inspect local edits and remote changes before proceeding. Do not discard another editor's work,
include unrelated changes in a commit, or force-push. If edits overlap, resolve them explicitly
and preserve the author's latest choices. Never resurrect text the author removed remotely.

Get the actual article from the author: a published URL, a reader-accessible preview link,
or an HTML/Markdown export. Record its title, subtitle, publication date, body, image order,
captions, source links, and footnotes.

Some Substack previews initially show only a loading silhouette. That alone does **not** mean
the article is inaccessible. Try the supplied link in an ordinary anonymous browser with
JavaScript enabled. The preview may also include its full article in `window._preloads.post`.
With the dependencies already installed in this repository, this reads that embedded data
without evaluating scripts:

```bash
node --input-type=module - "SUBSTACK_READER_URL" <<'JS'
const response = await fetch(process.argv[2]);
if (!response.ok) throw new Error(`Source request failed: ${response.status}`);
const html = await response.text();
const match = html.match(/window\._preloads\s*=\s*JSON\.parse\(("(?:[^"\\]|\\.)*")\)/);
if (!match) throw new Error("No embedded preview data; use the browser or an author export.");
const { post } = JSON.parse(JSON.parse(match[1]));
if (!post?.body_html) throw new Error("No article body; request an accessible source.");
console.log(JSON.stringify({
  title: post.title,
  subtitle: post.subtitle,
  date: post.post_date,
  isDraft: post.is_draft,
  body: post.body_html,
}, null, 2));
JS
```

Keep temporary source snapshots outside the repository. Do not persist the entire preload
object, cookies, login credentials, or unrelated account information. Do not bypass a login
or paywall. If the author-provided preview still has no body, request an export rather than
inventing the article.

A draft's `post_date` is not necessarily its final publication date. Confirm the intended
date from the author or the published edition, and do not label a preview as published on
Substack just because the independent website is being published.

## 2. Use the right figures

Prefer the project's existing corrected figures when the article uses project graphs.
For the congressional article, the three source images mapped to:

```text
congressional_record/outputs/figures/profanity_per_1k_last50.png
congressional_record/outputs/figures/slurs_per_1k.png
congressional_record/outputs/figures/formal_courtesy_per_1k_last50.png
```

Their local publication copies are under `public/artifacts/congressional-record/`.
Preserve image bytes when copying; measure real width and height with the existing `sharp`
dependency. Supply meaningful alt text, dimensions, `loading="lazy"` for inline figures,
and `decoding="async"`. A homepage thumbnail can reuse an inline graph.

The build generates website-only chart versions in `dist/`, matching the `--paper` colour
in `src/styles/global.css`. Original images in `public/` and the source projects remain
unchanged for Substack and research use. The export replaces only registered, exact
background colours; it preserves dimensions, plotted colours, transparency, and chart data.
Charts get lossless `.website.png` copies, and built pages link to those copies.
Original image URLs remain available with their original bytes.
Register new authored article charts in `src/data/website-chart-images.json`; do not add
photographs, screenshots, or third-party graphics. Staged UK and congressional chart
directories are handled automatically, and their pages use the publication background.

If an image is not available in the project, copy the author's image into a suitable
`public/artifacts/` directory. Do not leave dependencies on Substack image-CDN URLs or
placeholder images. Keep figure order and captions intact.

For congressional charts, check that:

- The data use the current word lists and any necessary historical rescoring has finished.
- Numeric rate axes start at zero.
- Year labels do not extend into the future.
- The final year follows actual recorded coverage, not the machine's clock.
- The latest Congress point is a Congress-to-date aggregate, not an invented annual total.

Do not reconstruct unavailable counts from a screenshot or substitute member-level counts
for the distinct historical series. Do not launch expensive backfills merely to copy images.
Article images are committed publication snapshots; they do not update themselves when the
project's figures change.

## 3. Add the article to Margin of Error

Create `src/content/posts/<slug>.mdx` using the schema in `src/content.config.ts` and an
existing post as a formatting reference. Use a stable, readable slug rather than the
Substack preview's UUID.

Important fields:

| Field | Rule |
|---|---|
| `title`, `subtitle` | Preserve the author's wording |
| `description` | Use the author's subtitle when there is one; do not add an invented promotional summary |
| `publishedAt` | Use the confirmed date in ISO format |
| `sortOrder` | Integer Unix seconds derived from the intended publication date; this controls newest-first ordering |
| `legacyPath` | `/<slug>`, matching the article's public route |
| `originalUrl` | The supplied reader URL or actual published source, not the editor URL |
| `thumbnail` | Local image path, useful alt text, and real dimensions; set `fit: "contain"` for charts that must not be cropped in previews |
| `draft` | `false` only when the author has authorized publication |

Compute the ordering value rather than guessing it:

```bash
node -e 'console.log(Math.floor(new Date("CONFIRMED_ISO_DATE").valueOf() / 1000))'
```

`featured` does not determine the homepage lead. Published entries are ordered by
`sortOrder`, alongside external articles.

Remove Substack subscription widgets, share buttons, image controls, and tracking clutter,
not the author's prose or citations. Keep profanity masking as supplied; never unmask an
already-censored quotation.

Use the existing footnote style with a `footnotes` section, stable note IDs, and working
reference/back links. Long source URLs must wrap on mobile.

Use `artifacts.code` and `artifacts.data` for the source repository and interactive
dashboard. Do not embed a second copy of the dashboard inside the article or introduce
an application server. Keep links to existing tools working.

The current templates intentionally:

- Show the original subtitle without an extra generated homepage summary.
- Omit a duplicate article-header description when it equals the subtitle.
- Avoid repeating that same description in archive and recent-post previews.
- Provide **View archive** after the homepage's recent pieces.

Add a migration record to `src/data/migration-manifest.json` with the source URL, title,
target route, platform, status, and a brief note on locally hosted images.

## 4. Validate the publication before pushing

Use the existing checks:

```bash
npm run check
npm test
git diff --check
```

`npm test` builds the site and runs `scripts/validate-build.mjs`. Update the assertions
for the new latest article rather than removing them: homepage lead/date/thumbnail,
archive order, RSS first item, AI index, article route, local figures, and footnotes.
The homepage keeps one lead story and four recent pieces.

Compare rendered article paragraphs against the source after whitespace normalization.
Confirm every citation and caption survived. Separately verify figure copies against the
project originals.

Check the homepage, article, archive navigation, and footnotes at desktop and mobile widths
(1360 and 390 pixels are the current test sizes). Verify that lazy-loaded images finish
loading, there is no horizontal overflow or JavaScript error, and keyboard navigation works.
Stop temporary preview servers after verification.

## 5. Commit and deploy Margin of Error

Stage only the intended files. Manual commits must be authored as `hanshanley`, with no
Copilot co-author or session trailers:

```bash
git add <intended-files>
git diff --cached --check
git -c user.name=hanshanley -c user.email=hwahhanley@gmail.com commit -m "Publish article title"
git push origin HEAD:main
```

A push to `main` automatically runs `.github/workflows/deploy.yml`. It also stages the
latest congressional dashboard from `hanshanley/congressional_record/site/`.
Do not dispatch a duplicate deploy while the push-triggered run is active.

The congressional and UK projects render their own publication mastheads. Navigation
changes must also update both projects' page generators and tests; regenerate the
committed congressional HTML before publishing. Updating Astro's header alone is not enough.

```bash
gh run list --repo hanshanley/margin_of_error --workflow deploy.yml \
  --limit 5 --json databaseId,headSha,status,conclusion,url
gh run watch RUN_ID --repo hanshanley/margin_of_error --exit-status
```

Match the deployment's `headSha` to the commit being published. On failure, inspect the
failed logs and fix the actual problem. Never force-push to solve concurrent edits, and
never overwrite a newer page with stale generated output.

After success, fetch the live homepage, article route, archive, RSS, images, and dashboard
destination. Verify real content and figure bytes, not just HTTP 200. Search or fetch tools
can serve stale cached pages; use a normal request with a commit-specific query parameter
when checking a just-deployed page.

## 6. Update the personal website

Only after the article's canonical Margin of Error URL works, edit the other repository:

```text
hanshanley.github.io/_data/writing.yml
```

Add the new entry at the top; `_pages/articles.md` groups entries by year and retains their
order within a year:

```yaml
- year: 2026
  date: "11 October 2026"
  short: "11 Oct"
  title: "Floor-Letter Words: The Rise of Congressional Profanity"
  blurb: "The author's original subtitle or approved description."
  url: "https://www.themarginoferror.com/floor-letter-words-the-rise-of-congressional-profanity/"
```

Use the new article's actual date, title, subtitle, and canonical URL. Do not link the
personal index to an opaque Substack draft link. Do not replace existing articles or
manually duplicate the listing in `_pages/articles.md`.

Consult `MAINTAINING.md` in that repository. Its local Jekyll command uses Homebrew Ruby
and bypasses the old Bundler setup:

```bash
export PATH="/opt/homebrew/lib/ruby/gems/4.0.0/bin:/opt/homebrew/opt/ruby/bin:$PATH"
export JEKYLL_NO_BUNDLER_REQUIRE=true
jekyll build --destination /tmp/personal-site-check
scripts/lint-style.sh /tmp/personal-site-check
```

Use a task-specific output directory, not one another process is using. If Jekyll is
unavailable, use the repository's documented installation path when practical. For a
data-only listing update, an alternative is to validate the YAML entry, its ordering,
and preservation of every existing entry, then verify the actual GitHub Pages build
and live rendered page after pushing. Do not claim a local Jekyll build ran when it did
not. `scripts/build-preview.py` only refreshes static preview styling and is **not** a
substitute for building the data-driven articles page.

Verify the built `/articles/` page places the new article first in its year, displays
the right date, and links to the live publication. Then commit only the intended update:

```bash
git add _data/writing.yml
git -c user.name=hanshanley -c user.email=hwahhanley@gmail.com commit -m "Add article to writing index"
git push origin HEAD:master
```

This repository currently uses GitHub Pages' legacy build from `master`, not Margin of
Error's Astro workflow. Confirm its actual configuration when publishing:

```bash
gh api repos/hanshanley/hanshanley.github.io/pages \
  --jq '{status,cname,build_type,source}'
gh run list --repo hanshanley/hanshanley.github.io \
  --limit 5 --json databaseId,headSha,status,conclusion,url
gh run watch RUN_ID --repo hanshanley/hanshanley.github.io --exit-status
```

Verify the live `https://www.hanshanley.com/articles/` listing after deployment. Leave
both worktrees clean except for pre-existing edits, remove only task-created temporary
files, and report completion only after both requested updates are persistent and live.
