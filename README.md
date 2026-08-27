<div align="center">
  <img src="public/favicon.svg" width="96" alt="The Margin of Error mark">
  <h1>The Margin of Error</h1>
  <p><strong>Essays on computer science, disinformation, statistics, and world events.</strong></p>
  <p>An independent data-journalism publication by Hans W. A. Hanley.</p>
  <p>
    <a href="https://www.themarginoferror.com">Read the publication</a> ·
    <a href="https://www.themarginoferror.com/archive/">Browse the archive</a>
  </p>
  <p>
    <a href="https://github.com/hanshanley/margin_of_error/actions/workflows/deploy.yml">
      <img src="https://github.com/hanshanley/margin_of_error/actions/workflows/deploy.yml/badge.svg" alt="GitHub Pages deployment status">
    </a>
  </p>
</div>

---

## An editorial notebook with the work attached

The Margin of Error combines long-form writing with the evidence behind it.
Articles can expose source code, datasets, generated outputs, and interactive
explorations alongside the narrative instead of treating them as detached
supplements.

The homepage presents the five latest pieces. The complete publication,
including migrated Google Sites and Substack work, remains available through
the archive.

### Durable, local publication assets

Article text is stored as MDX, while publication artwork and supporting files
are kept in `public/artifacts`. The deployed site does not depend on Google
Sites or Substack to render migrated articles or their cover images.

### Evidence-aware articles

Optional frontmatter groups—`code`, `data`, `outputs`, and `explore`—add
matching resource links and workspace panels to an article. Narrative-only
posts omit those groups and retain a focused reading view.

### Static by design

Astro generates the publication as static HTML with an RSS feed, sitemap,
canonical metadata, and a custom 404 page. GitHub Actions publishes the
finished artifact to GitHub Pages at
[www.themarginoferror.com](https://www.themarginoferror.com).

## Authoring

Posts live in [`src/content/posts`](src/content/posts) and are validated by
[`src/content.config.ts`](src/content.config.ts). Each post requires a unique
numeric `sortOrder`; higher values appear first without inventing dates for
legacy articles whose publication dates have not been confirmed.

Interactive component names must be registered in
[`src/components/explorations/Exploration.astro`](src/components/explorations/Exploration.astro).
Keep small supporting files in `public/artifacts`. Use an authoritative
external host or a GitHub Release for large datasets and generated outputs.

## Migrated publications

[`src/data/migration-manifest.json`](src/data/migration-manifest.json) records
legacy routes and migration status.

```bash
npm run migrate:substack
```

The migration tools copy publication images into the repository and rewrite
article references to local paths. DFRLab work remains linked to its original
publisher and is indexed in
[`src/data/external-articles.json`](src/data/external-articles.json).

The historical Google Sites importer is retained for reproducibility. It
requires `GOOGLE_SITES_ORIGIN` to point to the published Google Sites source;
pass `-- --all` to refresh every eligible legacy article.

Confirm licensing and attribution before publishing newly migrated media.

## Development

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Astro development server |
| `npm run check` | Run Astro and TypeScript diagnostics |
| `npm test` | Build and validate the production artifact |
| `npm run build` | Generate the static site in `dist/` |
| `npm run preview` | Serve the production build locally |

Application code lives in `src/`, publication assets in `public/`, migration
tools in `scripts/`, and deployment configuration in
`.github/workflows/deploy.yml`.

## Visual language

The site uses a typography-led statistical-broadsheet design: ruled margins,
restrained ink colors, asymmetrical editorial composition, and
article-specific graphics. Changes should preserve that identity rather than
introducing generic dashboard patterns, ornamental charts, or interchangeable
card layouts.

## Deployment

Every push to `main` runs the production build and publishes it through GitHub
Pages. The repository is assigned the custom domain
`www.themarginoferror.com`; DNS for `hanshanley.com` is managed separately and
is not part of this deployment.
