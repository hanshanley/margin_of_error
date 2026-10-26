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
	devToolbar: {
		enabled: false,
	},
	integrations: [
		mdx(),
		react(),
		sitemap({
			filter: (page) => page !== 'https://www.themarginoferror.com/home/',
			customPages: [
				'https://www.themarginoferror.com/political-ads/',
				'https://www.themarginoferror.com/congressional_profanity/',
				'https://www.themarginoferror.com/congressional_profanity/activity/',
				'https://www.themarginoferror.com/uk_decline/',
				'https://www.themarginoferror.com/china-us-relations/',
				'https://www.themarginoferror.com/china-us-relations/travel.html',
				'https://www.themarginoferror.com/china-us-relations/immigration.html',
				'https://www.themarginoferror.com/china-us-relations/comparisons.html',
				'https://www.themarginoferror.com/china-us-relations/language-learning.html',
				'https://www.themarginoferror.com/china-us-relations/business-presence.html',
				'https://www.themarginoferror.com/china-us-relations/weibo.html',
			],
		}),
	],
});
