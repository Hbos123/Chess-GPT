import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  // Remove trailing slash from base URL
  const raw = (process.env.NEXT_PUBLIC_BASE_URL || 'https://www.chessterai.com').replace(/\/$/, '')
  const baseUrl = raw === 'https://chessterai.com' ? 'https://www.chessterai.com' : raw
  
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
