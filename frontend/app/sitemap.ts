import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://chesster.app'
  // Ensure baseUrl ends with trailing slash for consistency
  const normalizedBaseUrl = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`
  
  // Keep sitemap minimal - only include public, indexable pages
  // Exclude app routes like /chess-board, /live-board, /app, /auth, etc.
  // These require authentication or are dynamic and shouldn't be indexed
  const routes: MetadataRoute.Sitemap = [
    {
      url: normalizedBaseUrl,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
  ]

  return routes
}
