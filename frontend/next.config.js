/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a minimal standalone server bundle for smaller Docker images.
  output: "standalone",
};

module.exports = nextConfig;
