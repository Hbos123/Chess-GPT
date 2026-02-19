import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  // Remove trailing slash from base URL
  const baseUrl = (process.env.NEXT_PUBLIC_BASE_URL || 'https://www.chessterai.com').replace(/\/$/, '')
  
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/api/',
          '/app/',
          '/admin/',
          '/dev/',
          '/auth/',
          '/chess-board/',
          '/live-board/',
          '/settings/',
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  }
}
