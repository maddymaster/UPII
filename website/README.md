# Smritium website

Static marketing + docs site for **smritium.ai / smritium.com**. No build step, no framework — plain HTML/CSS/JS, deployable anywhere.

## Structure

```
website/
├── index.html        # Landing: hero (animated terminal), features, Membrane, comparison, pricing, FAQ
├── onboarding.html   # 7-step interactive onboarding wizard (Supermemory-style)
├── docs.html         # Developer documentation (sidebar layout, CLI reference, concepts, MCP)
├── research.html     # Benchmarks, reproducibility audit, ELEVATE Nxt grant, patent, About
├── changelog.html    # Release notes
├── privacy.html      # Privacy policy (DRAFT — needs counsel review)
├── terms.html        # Terms of service (DRAFT — needs counsel review)
├── llms.txt          # Machine-readable site summary for LLM crawlers
└── assets/
    ├── styles.css    # Shared design system (light editorial: paper/indigo/ember)
    ├── logo.svg      # Wordmark + vault mark
    └── favicon.svg
```

## Deploy

Any static host. Fastest options:

**Vercel:** `cd website && npx vercel --prod` (set smritium.ai as the domain in the dashboard)
**Netlify:** drag the `website/` folder into app.netlify.com/drop, then attach the domain
**GitHub Pages:** push `website/` contents to a `gh-pages` branch, add a `CNAME` file containing `smritium.ai`, point DNS (A records to GitHub Pages IPs or ALIAS to `<user>.github.io`)

DNS at your registrar: point smritium.ai (and www) at the host; 301-redirect smritium.com → smritium.ai.

## Before launch — TODO

- [ ] Replace placeholder install links in `onboarding.html` (.dmg / .AppImage / .msi hrefs are `#`)
- [ ] Wire the MCP waitlist to a real endpoint (currently a mailto: to hello@smritium.ai). Options: Formspree, Buttondown, Tally, or a tiny worker
- [ ] Publish `install.sh` at smritium.ai/install.sh (referenced by the install commands)
- [ ] Have counsel review privacy.html and terms.html (both are marked DRAFT)
- [ ] Update benchmark cards in research.html from real REPORT.md artifacts as T1 harnesses land
- [ ] Add real ELEVATE Nxt application/reference number to research.html if permitted
- [ ] OG image (assets/og.png, 1200×630) and `<meta property="og:image">` tags
- [ ] Rename CLI examples if the binary stays `upii` instead of `smritium` (site assumes the binary is renamed to `smritium`)

## Design system

Defined in `assets/styles.css`: warm paper background (#FBFAF7), deep indigo ink (#1C1B4B), ember accent (#E8632C), Georgia serif for display, system sans for body. All animation is CSS + a small IntersectionObserver; no external JS/font/CDN dependencies — the site itself works offline, which is on-brand.

## Handoff note for Claude sessions

Product naming convention: **Smritium** is the public brand; **UPII** remains the internal/grant-facing codename (KITS milestone reports keep saying UPII). The site assumes CLI commands are `smritium <cmd>` — when finishing the product, either alias `upii` → `smritium` in the CLI entry point or update the docs/onboarding pages. Brand claims on the site map 1:1 to repo capabilities (deterministic chunking, rehydrator, inbox, 12 CLI commands); the aspirational items are labeled "coming soon" (MCP) or "planned" (v1.0 items in changelog).
