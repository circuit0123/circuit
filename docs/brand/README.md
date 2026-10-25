# Circuit logo pack ("The Bridge", emerald)

Put these files in the repo like this:

| Files | Copy to | Used for |
|---|---|---|
| svg/*.svg | packages/ui/assets/logo/ | The Logo component in packages/ui (inline SVG, both themes) |
| png/favicon.ico, png/apple-touch-icon-180.png | apps/app/public/ and apps/landing/public/ | Browser tab icon, iPhone home screen |
| png/circuit-app-icon-192.png, -512.png, png/circuit-app-icon-maskable-192.png, -512.png | apps/app/public/icons/ | PWA manifest icons (maskable = Android adaptive icon) |
| png/circuit-app-icon-1024.png | apps/app/public/icons/ | App stores later, social profile picture |
| png/circuit-logo-on-light-1200.png, -on-dark-1200.png | apps/landing/public/brand/ | Open Graph images, emails, press |
| png/circuit-mark-*-512.png | apps/landing/public/brand/ | Anywhere SVG isn't supported |

Which version to use:
- Dark backgrounds: circuit-logo-on-dark / circuit-mark-bright (#2FBF8A mark, #F3EEF5 text)
- Light backgrounds: circuit-logo-on-light / circuit-mark-emerald (#00563F mark, #120309 text)
- On a photo or the emerald colour: circuit-logo-white / circuit-mark-white
- circuit-app-icon.svg is full-bleed square (iOS/Android round the corners themselves);
  circuit-app-icon-rounded.svg is for the web (favicon, landing page).

The wordmark is converted to outlines (Geist SemiBold, tracking -0.035em), so it renders
the same everywhere without the font. Gaps around the nodes are real transparency.
Never recolour, outline, add effects to, or redraw the logo (DESIGN.md §5 "Logo").
