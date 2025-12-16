/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enable standalone output for Docker deployment
  output: 'standalone',
  // Enable experimental features for React 19
  experimental: {
    // Enable server actions
    serverActions: {
      bodySizeLimit: '50mb',
    },
  },
  // Allow external images from Azure blob storage
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.blob.core.windows.net',
      },
    ],
  },
}

module.exports = nextConfig
