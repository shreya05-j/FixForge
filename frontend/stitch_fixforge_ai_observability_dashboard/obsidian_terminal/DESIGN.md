---
name: Obsidian Terminal
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
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.05em
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 1px
---

## Brand & Style

This design system embodies a **Brutalist-Minimalist** aesthetic tailored for high-performance developer environments. The brand personality is industrial, technical, and unapologetically utilitarian, drawing inspiration from command-line interfaces and low-level system monitors. 

The target audience consists of software engineers and systems architects who prioritize information density and ocular comfort. The UI evokes a sense of "digital machinery"—precise, robust, and distraction-free. By stripping away all hue and decorative soft-shadows, the design system focuses purely on structure, hierarchy, and data clarity.

**Design Principles:**
- **Extreme Contrast:** Use pure black backgrounds against stark white text to ensure maximum legibility.
- **Structural Integrity:** Layouts are defined by 1px borders rather than shadows or depth.
- **Information Density:** Compact spacing and small, high-quality typography allow for complex data visualization.

## Colors

The palette is strictly monochrome, utilizing the full dynamic range of grayscale to establish hierarchy.

- **Background:** Pure OLED Black (#000000) serves as the foundation to minimize bezel distraction and maximize contrast.
- **Surfaces:** Deep Zinc tones (#09090b, #121214) differentiate secondary panels, sidebars, and nested containers.
- **Typography:** Stark White (#ffffff) is reserved for primary content and active states. Muted Zinc (#71717a) is used for metadata, labels, and disabled states.
- **Borders:** A consistent 1px border (#27272a) is the primary method of separation. No glows or gradients are permitted.

## Typography

Typography is the primary driver of visual interest. **Geist Sans** provides a clean, geometric feel for standard UI elements, while **JetBrains Mono** is utilized for telemetry, data points, and code blocks to maintain a "terminal" feel.

- **Scale:** Keep font sizes conservative to maintain high density. 
- **Telemetry:** Any dynamic data (CPU usage, timestamps, logs) must use JetBrains Mono.
- **Hierarchy:** Use font weight (600 vs 400) and color (White vs Zinc) to differentiate headings from body text rather than large jumps in scale.

## Layout & Spacing

The layout follows a **Fixed-Grid Modular** philosophy. Interfaces should feel like a dashboard of discrete modules locked into a grid.

- **Grid:** Use a 12-column grid for the primary dashboard, but interior modules often utilize simple vertical stacks or 2-column key-value pairs.
- **Margins:** External margins are tight (16px or 24px) to maximize screen real estate.
- **Gutters:** Use 1px borders as the visual gutter between adjacent panels.
- **Rhythm:** All spacing must be a multiple of 4px. Use 8px for internal component padding and 16px for block-level separation.

## Elevation & Depth

This system avoids shadows and Z-axis depth in favor of **Tonal Layering** and **Border Contiguity**.

- **Level 0 (Base):** #000000. Used for the main application background.
- **Level 1 (Panels):** #09090b. Used for sidebar, header, and main content areas.
- **Level 2 (In-panel elements):** #121214. Used for cards, input fields, and hover states.
- **Separation:** All levels must be separated by a 1px border (#27272a). 
- **Active State:** Instead of a shadow, an active element is indicated by a 1px Stark White (#ffffff) border or a solid White background with Black text.

## Shapes

The shape language is strictly **Sharp**. 

- **Primary Radius:** 0px. All buttons, panels, and input fields should have 90-degree corners.
- **Exceptions:** Very small icons or status pips may use a 2px radius if necessary for legibility, but all structural containers must remain sharp. 
- **Visual Weight:** Heavy, 1px lines create the perimeter of every interactive element.

## Components

### Buttons
- **Primary:** Solid #ffffff background, #000000 text. Sharp corners.
- **Secondary:** #000000 background, #ffffff text, 1px #27272a border.
- **Ghost:** #000000 background, #71717a text. No border until hover.

### Inputs
- **Text Fields:** #09090b background, 1px #27272a border. Text in Geist Sans. On focus, border changes to #ffffff.
- **Code Inputs:** Same as text fields but using JetBrains Mono.

### Navigation & Lists
- **Sidebar Items:** High-density (32px height). Active state uses a vertical 2px white "accent" bar on the far left or right of the item.
- **Data Tables:** No vertical lines. 1px horizontal lines (#27272a) between rows. Header row in `label-caps` typography.

### Status Indicators
- **Active/Success:** High-contrast white dot or "OK" in mono.
- **Warning/Error:** Since no color is used, use "!" icons or inverted (white background) blocks to draw immediate attention.

### Cards & Panels
- Flat containers with #09090b background and 1px #27272a borders. Use `headline-md` for panel titles, followed by a horizontal separator.