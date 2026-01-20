/** @type {import('next').NextConfig} */
const webpack = require('webpack');

const nextConfig = {
  reactStrictMode: true,
  /**
   * Capacitor-friendly static output.
   *
   * When CAPACITOR_EXPORT=1:
   * - Next will emit a static site into `frontend/out`
   * - Capacitor `webDir` should point at `out`
   *
   * Note: Next "export" mode does NOT run Next server features (API routes, headers()).
   * This app is primarily client-side and talks to the Python backend directly.
   */
  ...(process.env.CAPACITOR_EXPORT === "1"
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
  // Enable SharedArrayBuffer for stockfish.wasm
  // Disable source maps in production to avoid CORS issues
  productionBrowserSourceMaps: false,
  
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'require-corp',
          },
        ],
      },
      {
        source: '/stockfish-lite.wasm',
        headers: [
          {
            key: 'Content-Type',
            value: 'application/wasm',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
        ],
      },
      {
        source: '/stockfish-lite.js',
        headers: [
          {
            key: 'Content-Type',
            value: 'application/javascript',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
        ],
      },
      {
        // Allow source maps to load (for development)
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value: '*',
          },
        ],
      },
    ];
  },
  // Use webpack explicitly since we have custom webpack config
  // Add empty turbopack config to silence Next.js 16 warning
  turbopack: {},
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Prevent node built-ins from breaking browser bundles
      config.resolve.fallback = {
        ...(config.resolve.fallback || {}),
        fs: false,
        path: false,
        crypto: false,
        perf_hooks: false,
        worker_threads: false,
        module: false,
        os: false,
        child_process: false,
      };
      
      // Exclude stockfish.wasm from webpack processing since we use it as a Worker
      config.module = config.module || {};
      config.module.rules = config.module.rules || [];
      config.module.rules.push({
        test: /node_modules\/stockfish\.wasm\/stockfish\.js$/,
        use: 'null-loader',
      });
      
      // Ignore Node.js modules when they're required in stockfish packages
      config.plugins = config.plugins || [];
      config.plugins.push(
        new webpack.IgnorePlugin({
          resourceRegExp: /^(fs|path|worker_threads|perf_hooks|module|os|child_process)$/,
          contextRegExp: /node_modules\/(stockfish|stockfish\.wasm)/,
        })
      );
    }
    return config;
  },
};

module.exports = nextConfig;

