# Bug Hunter report

**Summary: 0 HIGH, 2 MEDIUM, 3 LOW**

## Resolution

All five findings were approved and fixed. Sorting now uses one required key; migrated images carry
intrinsic dimensions and loading/decoding hints; calculator values are normalized; thumbnail links
are hidden from assistive technology; and only sandboxed Datawrapper iframes are accepted.

## Medium

### Logic consistency

1. `src/lib/posts.ts:7-14` — The mixed sorting rule puts every dated post ahead of every undated
   legacy post, regardless of actual age. Adding a confirmed 2021 date to one legacy post would move
   it above undated 2022 posts.  
   **Suggested fix:** give every post one required sortable date/order key, or keep all legacy posts
   on the explicit archive order until every legacy date is known.

### Performance

2. `scripts/migrate-google-sites.mjs:101-109`,
   `scripts/migrate-substack.mjs:136-160` — Migrated article images are emitted as ordinary Markdown
   images without intrinsic dimensions or lazy-loading metadata. Image-heavy posts can eagerly fetch
   up to eleven images and shift the layout as they decode.  
   **Suggested fix:** emit an approved image component/HTML element with `loading="lazy"`,
   `decoding="async"`, and known width/height, or add a build transform that supplies them.

## Low

### Correctness / bugs

3. `src/components/explorations/MarginOfErrorCalculator.tsx:17-20,28-48` — Negative and out-of-range
   values remain visible in the controlled inputs while the calculation silently clamps them. The
   displayed input and computed result can therefore disagree.  
   **Suggested fix:** normalize values when updating state or display an explicit validation error
   and suppress the result until values are valid.

4. `src/components/PostCard.astro:22-30`, `src/pages/archive.astro:21-31` — Thumbnail links duplicate
   the adjacent title link for assistive technology, even though they are removed from keyboard tab
   order.  
   **Suggested fix:** mark decorative thumbnail links `aria-hidden="true"` and use empty image alt
   text, leaving the title as the single accessible link.

### Security

5. `scripts/migrate-substack.mjs:127-133` — Every remote iframe found during migration is copied into
   MDX without a host allowlist or sandbox. A future source-page change could introduce an
   unintended embed.  
   **Suggested fix:** accept only known Datawrapper HTTPS URLs and add an appropriate `sandbox`
   policy, rejecting all other iframe hosts.

## Files reviewed

- `.github/workflows/deploy.yml`
- `astro.config.mjs`
- `package.json`
- `README.md`
- `scripts/migrate-google-sites.mjs`
- `scripts/migrate-substack.mjs`
- `scripts/validate-build.mjs`
- `src/components/explorations/Exploration.astro`
- `src/components/explorations/MarginOfErrorCalculator.tsx`
- `src/components/Footer.astro`
- `src/components/Header.astro`
- `src/components/PostCard.astro`
- `src/components/PostWorkspace.astro`
- `src/content.config.ts`
- `src/data/external-articles.json`
- `src/data/migration-manifest.json`
- `src/layouts/BaseLayout.astro`
- `src/lib/posts.ts`
- `src/pages/[...slug].astro`
- `src/pages/404.astro`
- `src/pages/about.astro`
- `src/pages/archive.astro`
- `src/pages/home.astro`
- `src/pages/index.astro`
- `src/pages/rss.xml.js`

Dimensions run: correctness, logic consistency, comments/documentation, readability/maintainability,
security, and performance.
