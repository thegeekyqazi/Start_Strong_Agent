# Design: Strong Start Agent

The locked system. Every Hallmark run reads this first and pages share it. Change it on purpose; this file is the rule.

## System

- Genre: modern-minimal
- Shape of the first page: dense application workspace
- Theme: Furrow
- Axes: warm paper / compact display / trust-blue accent · posture: working-document

## Tokens

`apps/web/src/tokens.css` is the source of truth. The roles:

```css
:root {
  --color-paper: oklch(96% 0.011 85);
  --color-paper-2: oklch(99.5% 0.005 85);
  --color-paper-3: oklch(92% 0.016 85);
  --color-ink: oklch(18% 0.006 60);
  --color-ink-2: oklch(28% 0.008 60);
  --color-muted: oklch(44% 0.012 60);
  --color-rule: oklch(88% 0.013 85);
  --color-accent: oklch(48% 0.17 252);
  --color-accent-ink: oklch(98% 0.006 252);
  --color-focus: oklch(52% 0.18 252);
  --font-display: 'Red Hat Display', 'Red Hat Text', ui-sans-serif, sans-serif;
  --font-body: 'Red Hat Text', ui-sans-serif, system-ui, sans-serif;
  --font-outlier: 'Red Hat Mono', ui-monospace, monospace;
  --radius-card: 10px;
  --radius-pill: 6px;
  --rule-hair: 1px;
  --shadow-card: 0 1px 2px oklch(18% 0.006 60 / 0.08),
    0 14px 28px -16px oklch(18% 0.006 60 / 0.28);
}
```

The spacing scale, type scale, easings and durations are defined in `tokens.css`.

## Controls

- Primary: trust-blue fill · 6px radius · 40px minimum height
- Secondary: ink outline or text · same radius and height

## Motion

- Character: calm; brief state transitions only; reduced motion ends immediately.

## Variants

- Workflow console: a Lumen-informed dark operational surface may guide movement between existing stages. It uses the core Furrow tokens, carries no invented metrics, and never replaces route-level content or actions.
- Public landing page: a product explanation using the same workflow console, blue forward actions and verified project capabilities only.

## Exports

`apps/web/src/tokens.css` in this project. Tailwind, DTCG or shadcn blocks can be added here on request.
