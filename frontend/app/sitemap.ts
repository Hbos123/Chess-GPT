import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  // Remove trailing slash from base URL (Next.js handles URL construction)
  const baseUrl = (process.env.NEXT_PUBLIC_BASE_URL || 'https://chesster.app').replace(/\/$/, '')
  
  // Keep sitemap minimal - only include public, indexable pages
  // Exclude app routes like /chess-board, /live-board, /app, /auth, etc.
  // These require authentication or are dynamic and shouldn't be indexed
  const routes: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
  ]

  return routes
}
