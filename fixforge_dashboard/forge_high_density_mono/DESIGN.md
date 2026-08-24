---
name: Forge High-Density Mono
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1b1b1b'
  surface-container: '#1f1f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353535'
  on-surface: '#e2e2e2'
  on-surface-variant: '#c4c7c8'
  inverse-surface: '#e2e2e2'
  inverse-on-surface: '#303030'
  outline: '#8e9192'
  outline-variant: '#444748'
  surface-tint: '#c6c6c7'
  primary: '#ffffff'
  on-primary: '#2f3131'
  primary-container: '#e2e2e2'
  on-primary-container: '#636565'
  inverse-primary: '#5d5f5f'
  secondary: '#c6c5cf'
  on-secondary: '#2f3038'
  secondary-container: '#4a4b53'
  on-secondary-container: '#bcbbc5'
  tertiary: '#ffffff'
  on-tertiary: '#2f3131'
  tertiary-container: '#e2e2e2'
  on-tertiary-container: '#636565'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e2e2e2'
  primary-fixed-dim: '#c6c6c7'
  on-primary-fixed: '#1a1c1c'
  on-primary-fixed-variant: '#454747'
  secondary-fixed: '#e3e1ec'
  secondary-fixed-dim: '#c6c5cf'
  on-secondary-fixed: '#1a1b22'
  on-secondary-fixed-variant: '#46464e'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#131313'
  on-background: '#e2e2e2'
  surface-variant: '#353535'
  surface-deep: '#09090b'
  surface-elevated: '#121214'
  border-muted: '#27272a'
  text-muted: '#a1a1aa'
  success-white: '#ffffff'
  warning-gray: '#a1a1aa'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.04em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: -0.02em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.1em
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 12px
  margin-desktop: 24px
  panel-gap: 1px
---

## Brand & Style

The design system is engineered for professional AI-driven observability and high-stakes developer tools. It prioritizes information density and immediate legibility over decorative elements. The brand persona is technical, authoritative, and unapologetically precise—functioning as a high-contrast mission control for codebase health.

The aesthetic follows a **Brutalist-Minimal** approach. It leverages the "OLED-first" philosophy of deep blacks and stark whites to reduce eye strain during deep-work sessions while using 1px borders to define structure. There is no decorative fluff; every pixel must serve a functional purpose in data visualization or telemetry reporting.

## Colors

This is a strictly monochrome, dark-mode-first system. The foundation is **OLED Black (#000000)** to provide infinite depth and maximize contrast for white text. 

- **Primary Canvas:** Use `#000000` for main backgrounds.
- **Surface Tiers:** Use `Deep Zinc (#09090b)` for sidebar and panel backgrounds, and `#121214` for floating elements or code blocks.
- **Interaction States:** Primary actions are `Stark White (#ffffff)` with black text. Hover states utilize subtle opacity shifts or solid borders rather than hue changes.
- **Data Status:** Since the palette is monochrome, use density (solid vs. outline), weight (bold vs. light), and patterns to differentiate status levels rather than traditional semantic colors (red/green).

## Typography

Typography is used as a structural element. **Geist** provides a modern, geometric feel for headings, while **Inter** ensures maximum readability for dense documentation and UI labels. **JetBrains Mono** is reserved exclusively for code, telemetry data, and technical metadata.

- **Scale:** Use tight line-heights (1.2–1.4) to maintain high information density.
- **Hierarchy:** Contrast is achieved through weight and case. Use `label-caps` (JetBrains Mono) for section headers and table column titles to evoke a terminal-like aesthetic.
- **Code Blocks:** All telemetry data should be set in `code-sm` to ensure character alignment in tabular views.

## Layout & Spacing

The layout uses a **High-Density Fixed Grid** system. Components are often separated by 1px borders rather than wide gutters to maximize screen real estate for logs and graphs.

- **The 4px Rhythm:** All padding and margins must be multiples of 4px.
- **Panel System:** Use a "bento-box" style grid where panels are flush against each other, separated by a `1px` border (`#27272a`). 
- **Breakpoints:**
  - **Mobile (<768px):** Single column, condensed margins.
  - **Desktop (>1280px):** Multi-pane "IDE" layout with fixed sidebars (240px) and fluid center telemetry.

## Elevation & Depth

Elevation is conveyed through **Tonal Layering** and **1px Outlines** rather than soft shadows. 

- **Level 0:** Base background (`#000000`).
- **Level 1:** Containers (`#09090b`) with a `1px` solid border (`#27272a`).
- **Level 2:** Modals and Popovers (`#121214`) with a slightly brighter border (`#71717a`) to pull them forward.
- **Glassmorphism:** Code blocks and floating overlays should use a background-blur (20px) with 60% opacity on the surface color to maintain context of the logs underneath.

## Shapes

The shape language is strictly **Sharp (0px)**. This reinforces the Brutalist-Minimal aesthetic and ensures that 1px borders align perfectly with the pixel grid without anti-aliasing artifacts. 

- **Buttons & Inputs:** Hard 90-degree corners.
- **Status Badges:** Use rectangular boxes with no radius.
- **Focus States:** Use a secondary 1px offset white border for keyboard navigation.

## Components

### Buttons
Primary buttons are solid `Stark White` with black text. Secondary buttons are outline-only with white text. Ghost buttons use `text-muted` and become white on hover. All buttons have 0px radius.

### Linear Step Trackers
Used for AI fix-pipelines. Represented as a vertical 1px line. Active steps are a solid white circle; pending steps are an outlined gray square.

### Technical Badges
Small, rectangular tags using `JetBrains Mono`. Backgrounds are transparent with a 1px border. Use high-contrast white text for "Critical" and gray text for "Info."

### Confidence Gauges
Represented as horizontal segmented bars (10 segments). Solid white blocks fill the percentage of confidence, while empty blocks are dark gray outlines.

### Code Blocks
Glassmorphic containers (`#121214` at 80% opacity) with `JetBrains Mono` text. Syntax highlighting must be limited to shades of gray and white (e.g., bold white for keywords, muted gray for comments).

### Input Fields
Hard-edged boxes with a 1px border (`#27272a`). On focus, the border turns white. Labels use `label-caps` positioned above the input field.