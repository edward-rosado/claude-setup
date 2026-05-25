---
name: hash-anchor-multi-page-nav
description: "Fix shared nav hash anchors (#section) that silently fail on non-homepage routes"
user-invocable: false
origin: auto-extracted
---

# Hash Anchor Navigation in Shared Nav Components

**Extracted:** 2026-03-16
**Context:** Any Next.js or SPA with a shared Nav component containing hash anchors to homepage sections

## Problem

A shared Nav renders links like `#services`, `#testimonials`, `#about` that scroll to sections
on the homepage. On non-homepage routes (`/terms`, `/privacy`, `/accessibility`), clicking these
links does nothing — there's no element with that ID on the current page. No error is thrown,
the click just silently fails, making the nav appear broken.

## Solution

Detect whether the current page is the homepage. If not, prefix hash anchors with `/` so the
browser navigates to the homepage first, then scrolls to the anchor.

**Next.js (App Router):**

```tsx
import { usePathname } from "next/navigation";

export function Nav() {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const prefix = isHome ? "" : "/";

  const sections = [
    { label: "Services", href: `${prefix}#services` },
    { label: "About", href: `${prefix}#about` },
  ];

  return (
    <nav>
      {sections.map((s) => (
        <a key={s.href} href={s.href}>{s.label}</a>
      ))}
    </nav>
  );
}
```

**Test:**

```tsx
const mockPathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({ usePathname: () => mockPathname() }));

it("uses hash-only on homepage", () => {
  mockPathname.mockReturnValue("/");
  render(<Nav />);
  expect(screen.getByText("Services")).toHaveAttribute("href", "#services");
});

it("uses absolute path on non-homepage", () => {
  mockPathname.mockReturnValue("/terms");
  render(<Nav />);
  expect(screen.getByText("Services")).toHaveAttribute("href", "/#services");
});
```

## When to Use

- Shared Nav/Header component with anchor links to homepage sections
- App has multiple routes (legal pages, blog, dashboards) that reuse the same nav
- Users report "hamburger menu links don't work" on non-homepage routes
