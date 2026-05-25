---
name: nextjs-image-cloudflare-workers
description: "Next.js <Image> breaks on Cloudflare Workers — set unoptimized:true or use custom loader"
user-invocable: false
origin: auto-extracted
---

# Next.js Image Optimization Fails on Cloudflare Workers

**Extracted:** 2026-03-14
**Context:** Deploying Next.js apps via OpenNext to Cloudflare Workers

## Problem
Next.js `<Image>` component routes all images through `/_next/image`, which uses Node.js
`sharp` module for on-the-fly resizing and format conversion. Cloudflare Workers runs V8
isolates, not Node.js — `sharp` is unavailable. Images silently fail to render (no error
in the browser console, just broken/missing images).

This affects ALL images using `next/image` — both local (`public/`) and remote URLs.

## Solution

### Quick fix: Disable optimization globally
```ts
// next.config.ts
const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
    // remotePatterns still needed for external domains
    remotePatterns: [
      { protocol: "https", hostname: "example.com", pathname: "/**" },
    ],
  },
};
```

### Production alternative: Cloudflare Image Resizing (paid)
```ts
// next.config.ts
const nextConfig: NextConfig = {
  images: {
    loader: "custom",
    loaderFile: "./lib/cloudflare-image-loader.ts",
  },
};

// lib/cloudflare-image-loader.ts
export default function cloudflareLoader({
  src, width, quality,
}: { src: string; width: number; quality?: number }) {
  const params = [`width=${width}`, `quality=${quality || 75}`, "format=auto"];
  return `/cdn-cgi/image/${params.join(",")}/${src}`;
}
```

## When to Use
- Deploying Next.js to Cloudflare Workers (via OpenNext or otherwise)
- Images not rendering on deployed site but working in local dev
- No errors in browser console but `<Image>` components show nothing
- Any `next/image` usage on edge runtimes without Node.js APIs
