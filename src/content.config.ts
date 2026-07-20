import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const linkSchema = z.object({
	label: z.string(),
	url: z.url(),
});

const codeSchema = z.object({
	description: z.string(),
	repository: z.url(),
	revision: z.string().optional(),
	path: z.string().optional(),
	language: z.string().optional(),
	license: z.string().optional(),
	links: z.array(linkSchema).default([]),
});

const dataItemSchema = z.object({
	title: z.string(),
	description: z.string(),
	url: z.url(),
	source: z.string(),
	format: z.string().optional(),
	size: z.string().optional(),
	version: z.string().optional(),
	license: z.string().optional(),
	checksum: z.string().optional(),
});

const outputSchema = z.object({
	title: z.string(),
	description: z.string(),
	url: z.url(),
	kind: z.enum(['figure', 'table', 'report', 'model', 'download']),
	format: z.string().optional(),
});

const localExploreSchema = z.object({
	kind: z.literal('local'),
	module: z.enum(['margin-of-error-calculator']),
	title: z.string(),
	description: z.string(),
	fallback: z.string(),
});

const externalExploreSchema = z.object({
	kind: z.literal('external'),
	url: z.url(),
	title: z.string(),
	description: z.string(),
	fallback: z.string(),
});

const postSchema = z.object({
	title: z.string(),
	description: z.string(),
	publishedAt: z.coerce.date().optional(),
	updatedAt: z.coerce.date().optional(),
	author: z.string().default('Hans W. A. Hanley'),
	tags: z.array(z.string()).default([]),
	featured: z.boolean().default(false),
	draft: z.boolean().default(false),
	sortOrder: z.number().int(),
	legacyPath: z.string().startsWith('/').optional(),
	originalUrl: z.url().optional(),
	thumbnail: z
		.object({
			src: z.string(),
			alt: z.string(),
			width: z.number().int().positive().optional(),
			height: z.number().int().positive().optional(),
		})
		.optional(),
	hero: z
		.object({
			src: z.string(),
			alt: z.string(),
			caption: z.string().optional(),
		})
		.optional(),
	artifacts: z
		.object({
			code: codeSchema.optional(),
			data: z.array(dataItemSchema).optional(),
			outputs: z.array(outputSchema).optional(),
			explore: z.discriminatedUnion('kind', [localExploreSchema, externalExploreSchema]).optional(),
		})
		.optional(),
});

const posts = defineCollection({
	loader: glob({ base: './src/content/posts', pattern: '**/*.{md,mdx}' }),
	schema: postSchema,
});

const fixtures = defineCollection({
	loader: glob({ base: './src/content/fixtures', pattern: '**/*.{md,mdx}' }),
	schema: postSchema,
});

export const collections = { posts, fixtures };
