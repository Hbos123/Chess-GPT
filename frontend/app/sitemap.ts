import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  // Base URL without trailing slash for constructing URLs
  const raw = (process.env.NEXT_PUBLIC_BASE_URL || 'https://www.chessterai.com').replace(/\/$/, '')
  const baseUrl = raw === 'https://chessterai.com' ? 'https://www.chessterai.com' : raw
  
  // Keep sitemap minimal - only include public, indexable pages
  // Exclude app routes like /chess-board, /live-board, /app, /auth, etc.
  // These require authentication or are dynamic and shouldn't be indexed
  // Root URL should have trailing slash for Google Search Console compatibility
  const routes: MetadataRoute.Sitemap = [
    {
      url: `${baseUrl}/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
  ]

  return routes
}
