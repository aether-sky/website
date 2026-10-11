import { frontmatter } from './content/landing.md';

export const site = { title: frontmatter.title as string, description: frontmatter.description as string };
export const dateLabel = (date: Date) => date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
