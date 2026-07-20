# The Margin of Error

An editorial data-journalism site by Hans W. A. Hanley. The site is built with Astro, authored in
MDX, and published to GitHub Pages at
[www.themarginoferror.com](https://www.themarginoferror.com).

## Development

```sh
npm install
npm run dev
```

Run `npm run check` before opening a pull request and `npm run build` to inspect the production
output.

## Authoring

Posts live in `src/content/posts` and are validated by `src/content.config.ts`. Every post has an
Article view. Add any of the `code`, `data`, `outputs`, or `explore` artifact groups to expose the
matching workspace tab; leave them out for narrative-only posts.

The interactive component name in frontmatter must exist in the allowlist in
`src/components/explorations/Exploration.astro`. Keep small supporting files in `public/artifacts`.
Use an authoritative external host or GitHub Release for large datasets and generated outputs.

`src/data/migration-manifest.json` tracks the Google Sites migration and legacy paths.

The migration can be reproduced with `npm run migrate:legacy`. Pass `-- --all` to refresh every
legacy article after changing the converter. Before publishing, confirm original dates and the
license/attribution for every migrated image.

## Visual language

This is a typography-led statistical broadsheet, not a generic application dashboard. Preserve the
ruled margins, restrained ink palette, asymmetrical editorial composition, and post-specific
graphics. Avoid stock gradient heroes, glass panels, bento/card grids, excessive pills, ornamental
charts, and other interchangeable "AI-generated website" motifs.

## Deployment

Pushes to `main` are built and published by `.github/workflows/deploy.yml`. GitHub Pages must use
**GitHub Actions** as its source. `public/CNAME` keeps `www.themarginoferror.com` as the canonical
domain.
