import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
	const posts = (await getCollection('posts', ({ data }) => !data.draft)).sort(
		(a, b) => (b.data.publishedAt?.valueOf() ?? 0) - (a.data.publishedAt?.valueOf() ?? 0),
	);

	return rss({
		title: 'The Margin of Error',
		description: 'Essays, evidence, and computational detours by Hans W. A. Hanley.',
		site: context.site,
		items: posts.map((post) => ({
			title: post.data.title,
			description: post.data.description,
			pubDate: post.data.publishedAt,
			link: post.data.legacyPath ?? `/${post.id}/`,
		})),
	});
}
