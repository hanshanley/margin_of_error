// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
	site: 'https://www.themarginoferror.com',
	output: 'static',
	trailingSlash: 'always',
	integrations: [
		mdx(),
		react(),
		sitemap({
			filter: (page) => page !== 'https://www.themarginoferror.com/home/',
		}),
	],
});
