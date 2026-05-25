---
name: svg-icon-registry-keyword-matching
description: "Inline SVG icon registry with keyword-based auto-resolution and explicit config override for dynamic icon selection"
user-invocable: false
origin: auto-extracted
---

# SVG Icon Registry with Keyword Matching

**Extracted:** 2026-03-17
**Context:** When components need to display contextually appropriate icons based on content titles (e.g., service cards, feature lists) without requiring manual icon assignment for every item.

## Problem
Components display items with icons, but hardcoding icon-to-item mappings is brittle and doesn't scale. Random or missing icons hurt the user experience. Need a system that:
1. Automatically picks a relevant icon based on the item's title/description
2. Allows explicit override via config when auto-matching isn't right
3. Falls back gracefully to a sensible default

## Solution

Three-layer resolution: **explicit override → keyword match → default fallback**

```typescript
// 1. Named registry of inline SVG components
const ICON_REGISTRY: Record<string, React.FC<{ size?: number }>> = {
  home: ({ size = 24 }) => <svg width={size} height={size}>...</svg>,
  camera: ({ size = 24 }) => <svg>...</svg>,
  dollar: ({ size = 24 }) => <svg>...</svg>,
  search: ({ size = 24 }) => <svg>...</svg>,
  star: ({ size = 24 }) => <svg>...</svg>,  // default
  // ... 10-15 domain-relevant icons
};

// 2. Keyword-to-icon mapping (ordered by specificity)
const KEYWORD_MAP: Array<[string[], string]> = [
  [["valuation", "home value", "market analysis", "cma"], "home"],
  [["photo", "staging", "virtual tour"], "camera"],
  [["price", "commission", "investment", "roi"], "dollar"],
  [["buyer", "search", "find", "looking"], "search"],
  [["negotiat", "contract", "closing"], "handshake"],
];

// 3. Resolution function with three-layer priority
export function resolveIcon(
  title: string,
  explicitIcon?: string
): React.FC<{ size?: number }> {
  // Layer 1: Explicit override from config
  if (explicitIcon && ICON_REGISTRY[explicitIcon]) {
    return ICON_REGISTRY[explicitIcon];
  }
  // Layer 2: Keyword matching against title
  const t = title.toLowerCase();
  for (const [keywords, key] of KEYWORD_MAP) {
    if (keywords.some((kw) => t.includes(kw))) {
      return ICON_REGISTRY[key];
    }
  }
  // Layer 3: Default fallback
  return ICON_REGISTRY.star;
}
```

**Usage in component:**
```tsx
function ServiceCard({ title, icon }: { title: string; icon?: string }) {
  const Icon = resolveIcon(title, icon);
  return (
    <div className="card">
      <Icon size={32} />
      <h3>{title}</h3>
    </div>
  );
}
```

**Data model:** Add optional `icon?: string` to item type for explicit overrides:
```typescript
interface ServiceItem {
  title: string;
  description: string;
  icon?: string;  // key from ICON_REGISTRY, overrides keyword matching
}
```

## Key Decisions
- **Inline SVGs over icon fonts/sprite sheets** — tree-shakeable, styleable via CSS, no extra HTTP requests
- **Array-of-tuples for keyword map** — preserves ordering (more specific keywords checked first), unlike object keys
- **`includes()` over exact match** — catches partial matches ("negotiation" matches "negotiat")
- **Invalid override falls through** — if config specifies a non-existent icon key, keyword matching still runs instead of erroring

## When to Use
- Components rendering lists of items where each needs a contextual icon
- CMS-driven content where icon assignment should be automatic but overridable
- Any UI with 10+ items that would be tedious to manually assign icons to
