# Dashboard design review

## What the reference repositories actually use

- [PlantDiseaseNet-Edge](https://github.com/Akbeherab/PlantDiseaseNet-Edge) is a Python model-training, benchmarking, and Raspberry Pi inference repository. Its tracked files include Python scripts, result JSON, and model-accuracy/confusion-matrix images. It has no dashboard page, frontend source, stylesheet, Node package, or JavaScript dashboard to copy. Its useful presentation idea is to make model results and edge-device constraints visible with clear benchmark tables and plots. The reported numbers belong to that repository and are not AgriSahayak results.
- [EdgeShiksha](https://github.com/Akbeherab/EdgeShiksha) has a React 18 and Vite client, Tailwind CSS 3 with PostCSS, Lucide React icons, and a Node/Express server. Its interface is composed from page sections and reusable React components, with a small custom CSS layer for fonts, dot-grid backgrounds, and motion. The repository includes Matter.js for its decorative falling-pills canvas; it does not use Three.js or a 3D dashboard renderer.

## AgriSahayak design decision

AgriSahayak currently serves its dashboard from the Python web server as HTML, CSS, and JavaScript. The refreshed laptop dashboard keeps that architecture, the existing API contract, and the tablet stylesheet. It takes inspiration from EdgeShiksha's clear page hierarchy, restrained background texture, reusable spacing, and small motion details, then uses AgriSahayak's own field palette and status colors. The dashboard now uses a light, high-contrast canvas with a deep green navigation rail, white data cards, clearer KPI grouping, and responsive card layouts.

## Scope

The changes are dashboard CSS, stylesheet/cache-busting links, and a privacy-safe server status label. They do not replace model logic, server routes, rover behavior, records, support-desk recommendations, chat, or tablet controls. The UI changes and review package have not been committed or published.

## Page previews

These local browser captures show the actual dashboard with an empty record store and no connected tablet or Arduino. They document layout, not model or hardware test results.

- [Overview](dashboard-previews/overview.png)
- [Live Monitor](dashboard-previews/live-monitor.png)
- [Rover Tools](dashboard-previews/rover.png)
- [Farmer Support Desk](dashboard-previews/support-desk.png)
- [Fasal Saathi open](dashboard-previews/fasal-saathi-open.png)
- [Records](dashboard-previews/records.png)
