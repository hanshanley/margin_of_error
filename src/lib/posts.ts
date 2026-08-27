import type { CollectionEntry } from 'astro:content';

export function comparePostsNewestFirst(
	a: CollectionEntry<'posts'>,
	b: CollectionEntry<'posts'>,
) {
	return b.data.sortOrder - a.data.sortOrder;
}

export function getPostPath(post: CollectionEntry<'posts'>) {
	const path = post.data.legacyPath ?? `/${post.id}`;
	return `/${path.replace(/^\/|\/$/g, '')}/`;
}
