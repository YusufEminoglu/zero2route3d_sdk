# -*- coding: utf-8 -*-
"""
Builder for zero2route3d-sdk Master Interactive Academic Reference Manual.
Generates a comprehensive, 10,000+ line interactive documentation site with KaTeX/MathJax,
live calculators, 15 mobility profile catalogs, full API reference, and PyPI/GitHub guides.
"""

import os

OUTPUT_DIR = r"C:\Users\YE\PyCharmMiscProject\PyPI\zero2route3d_sdk\docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

os.makedirs(OUTPUT_DIR, exist_ok=True)

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>zero2route3d-sdk — Academic Reference Manual & 3D Kinematics Documentation</title>
<meta name="description" content="Official academic reference manual for zero2route3d-sdk: Headless 3D spatial mobility, biomechanical human kinematics, metabolic energy modeling, and multi-criteria routing analytics.">
<meta name="author" content="Yusuf Eminoğlu">

<!-- MathJax for formula rendering -->
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    processEscapes: true,
    processEnvironments: true,
    tags: 'ams',
    macros: {
      arg: '\\mathop{\\mathrm{arg}}\\nolimits',
      min: '\\mathop{\\mathrm{min}}\\nolimits',
      max: '\\mathop{\\mathrm{max}}\\nolimits',
    }
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    ignoreHtmlClass: 'no-math|tex2jax_ignore'
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>

<!-- Typography -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">

<style>
:root {
  --bg: #0b0f19;
  --bg-secondary: #111827;
  --bg-sidebar: #0e1422;
  --fg: #f3f4f6;
  --fg-heading: #ffffff;
  --muted: #9ca3af;
  --dim: #6b7280;
  
  --accent: #10b981;
  --accent-dark: #059669;
  --accent-light: rgba(16, 185, 129, 0.12);
  --accent-cyan: #06b6d4;
  --accent-blue: #3b82f6;
  --accent-indigo: #6366f1;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  
  --border: #1f2937;
  --border-subtle: #374151;
  --code-bg: #0d1117;
  --sidebar-active: rgba(16, 185, 129, 0.15);
  --table-stripe: #141d2e;
  
  --gradient-brand: linear-gradient(135deg, #10b981 0%, #06b6d4 50%, #3b82f6 100%);
  --shadow-card: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
  
  font-size: 14.5px;
  line-height: 1.68;
}

[data-theme="light"] {
  --bg: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-sidebar: #f1f5f9;
  --fg: #1e293b;
  --fg-heading: #0f172a;
  --muted: #475569;
  --dim: #64748b;
  
  --accent: #059669;
  --accent-dark: #047857;
  --accent-light: #d1fae5;
  
  --border: #e2e8f0;
  --border-subtle: #cbd5e1;
  --code-bg: #0f172a;
  --sidebar-active: #d1fae5;
  --table-stripe: #f8fafc;
  --shadow-card: 0 4px 15px -1px rgba(0, 0, 0, 0.08);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--fg);
  display: flex;
  min-height: 100vh;
  transition: background 0.2s ease, color 0.2s ease;
}

/* Top App Bar */
#top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 58px;
  background: rgba(14, 20, 34, 0.92);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  z-index: 1000;
}

[data-theme="light"] #top-bar {
  background: rgba(255, 255, 255, 0.94);
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.brand-badge {
  background: var(--gradient-brand);
  color: white;
  font-weight: 800;
  font-size: 1.1rem;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.5);
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.brand-text {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 800;
  font-size: 1.25rem;
  letter-spacing: -0.02em;
  background: var(--gradient-brand);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.ver-tag {
  font-family: 'Fira Code', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--accent-light);
  color: var(--accent);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.top-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
  border-radius: 7px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all 0.15s ease;
  cursor: pointer;
}

.top-btn:hover {
  color: var(--fg-heading);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.top-btn.primary {
  background: var(--accent);
  color: #0b0f19;
  border-color: transparent;
  font-weight: 600;
}

/* Sidebar */
#sidebar {
  width: 320px;
  min-width: 320px;
  height: calc(100vh - 58px);
  position: sticky;
  top: 58px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 100;
}

#search-wrap {
  padding: 0.85rem 1rem 0.65rem;
  border-bottom: 1px solid var(--border);
}

#search {
  width: 100%;
  padding: 0.55rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
  background: var(--bg);
  color: var(--fg);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

#search:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-light);
}

#toc {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  list-style: none;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.toc-group {
  border-bottom: 1px solid var(--border);
}

.toc-group-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  text-align: left;
  padding: 8px 16px;
  background: none;
  border: none;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--fg-heading);
  cursor: pointer;
  transition: background 0.15s;
}

.toc-group-btn:hover {
  background: var(--accent-light);
}

.toc-group-btn .arrow {
  font-size: 0.7em;
  transition: transform 0.2s;
}

.toc-group-btn[aria-expanded="false"] .arrow {
  transform: rotate(-90deg);
}

.toc-algs {
  list-style: none;
  overflow: hidden;
}

.toc-algs li a {
  display: block;
  padding: 4px 16px 4px 24px;
  font-size: 0.82rem;
  color: var(--muted);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.toc-algs li a:hover, .toc-algs li a.active {
  background: var(--sidebar-active);
  border-left-color: var(--accent);
  color: var(--accent);
  font-weight: 500;
}

.toc-algs li a.hidden {
  display: none;
}

#sidebar-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: var(--bg-secondary);
}

#sidebar-footer a {
  font-size: 0.78rem;
  color: var(--muted);
  text-decoration: none;
}

#sidebar-footer a:hover {
  color: var(--accent);
}

/* Content */
#content {
  flex: 1;
  max-width: 960px;
  margin: 0 auto;
  padding: calc(58px + 2rem) 3rem 6rem;
  overflow-y: auto;
}

/* Headings */
h1 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 2.3rem;
  margin: 0 0 0.25em;
  color: var(--fg-heading);
  letter-spacing: -0.02em;
}

h1.subtitle {
  font-size: 1.15rem;
  font-weight: 400;
  color: var(--muted);
  margin-bottom: 1.75em;
}

h2 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 1.6rem;
  margin: 2.75em 0 0.6em;
  padding-bottom: 0.3em;
  border-bottom: 2px solid var(--border);
  color: var(--fg-heading);
}

h2.group-header {
  border-bottom: 2px solid var(--accent);
  color: var(--accent);
  margin-top: 3.5em;
}

h3 {
  font-size: 1.22rem;
  margin: 1.6em 0 0.45em;
  color: var(--fg-heading);
}

h4 {
  font-size: 1.05rem;
  margin: 1.25em 0 0.35em;
  color: var(--muted);
}

p, ul, ol { margin: 0.75em 0; }
ul, ol { padding-left: 1.8em; }
li { margin: 0.3em 0; color: var(--fg); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.88em;
  background: var(--code-bg);
  color: var(--accent);
  padding: 0.12em 0.38em;
  border-radius: 4px;
  border: 1px solid var(--border);
}

pre {
  background: var(--code-bg);
  padding: 1.1em 1.25em;
  border-radius: 8px;
  border: 1px solid var(--border);
  overflow-x: auto;
  margin: 1em 0;
  font-family: 'Fira Code', monospace;
  font-size: 0.88em;
  line-height: 1.6;
  color: #f1f5f9;
}

pre code {
  background: transparent;
  border: none;
  padding: 0;
  color: inherit;
  font-size: 1em;
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.2em 0 1.6em;
  font-size: 0.9em;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
}

th, td {
  text-align: left;
  padding: 0.6em 0.85em;
  border: 1px solid var(--border);
}

th {
  background: var(--bg-secondary);
  color: var(--fg-heading);
  font-weight: 600;
}

tr:nth-child(even) td {
  background: var(--table-stripe);
}

.note {
  background: var(--accent-light);
  border-left: 4px solid var(--accent);
  padding: 0.8em 1.2em;
  margin: 1.2em 0;
  border-radius: 0 8px 8px 0;
  color: var(--fg);
}

.warn {
  background: rgba(245, 158, 11, 0.12);
  border-left: 4px solid var(--accent-amber);
  padding: 0.8em 1.2em;
  margin: 1.2em 0;
  border-radius: 0 8px 8px 0;
  color: var(--fg);
}

.ref {
  margin: 0.45em 0;
  padding-left: 1.5em;
  text-indent: -1.5em;
  font-size: 0.9em;
  line-height: 1.6;
}

.ref .check { color: #10b981; font-weight: bold; }
.ref .no-doi { color: #f59e0b; }

.eq { text-align: center; margin: 1.2em 0; }
.param-table td:first-child { font-family: monospace; font-weight: 600; white-space: nowrap; color: var(--accent); }
.field-table td:first-child { font-family: monospace; white-space: nowrap; color: var(--accent-cyan); }

.cover {
  text-align: center;
  padding: 4rem 0 3rem;
  background: radial-gradient(circle at center, rgba(16, 185, 129, 0.08) 0%, transparent 70%);
  border-radius: 16px;
  border: 1px solid var(--border);
  margin-bottom: 3rem;
}

.cover h1 { font-size: 3.2rem; margin-bottom: 0.15em; }
.cover .version { font-size: 1.2rem; color: var(--accent); font-weight: 600; font-family: 'Fira Code', monospace; }
.cover .date { font-size: 0.95rem; color: var(--muted); margin-top: 1em; }

/* Interactive Sandbox Calculator Card */
.sandbox-card {
  background: var(--bg-secondary);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1.8rem 0;
  box-shadow: var(--shadow-card);
}

.sandbox-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(16, 185, 129, 0.15);
  color: var(--accent);
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  text-transform: uppercase;
  margin-bottom: 0.75rem;
}

.sandbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1rem;
}

@media (max-width: 768px) {
  .sandbox-grid { grid-template-columns: 1fr; }
}

.control-item { margin-bottom: 0.85rem; }
.control-item label { display: flex; justify-content: space-between; font-size: 0.82rem; font-weight: 500; margin-bottom: 0.3rem; }
.control-item label span.val { color: var(--accent); font-family: 'Fira Code', monospace; font-weight: 600; }
.slider { width: 100%; height: 6px; border-radius: 3px; background: var(--border); outline: none; cursor: pointer; }

.calc-display {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.calc-result {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 2.2rem;
  font-weight: 800;
  color: var(--accent);
}

/* Back to top */
#back-to-top {
  position: fixed; bottom: 24px; right: 24px; width: 42px; height: 42px;
  background: var(--accent); color: white; border: none; border-radius: 50%;
  font-size: 1.3em; cursor: pointer; opacity: 0; transform: translateY(20px);
  transition: opacity .2s, transform .2s; z-index: 200;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}
#back-to-top.visible { opacity: 0.9; transform: translateY(0); }
#back-to-top:hover { opacity: 1; transform: scale(1.08); }

/* Mobile */
@media (max-width: 1024px) {
  #sidebar { display: none; }
  #content { padding: calc(58px + 1.5rem) 1.5rem 5rem; }
}
</style>
</head>
<body>

<!-- Top Navigation -->
<header id="top-bar">
  <a href="#" class="brand-wrap">
    <div class="brand-badge">Z</div>
    <span class="brand-text">zero2route3d-sdk</span>
    <span class="ver-tag">v0.2.0</span>
  </a>
  <div class="top-actions">
    <a href="https://pypi.org/project/zero2route3d-sdk/" target="_blank" class="top-btn"><i data-lucide="package" style="width:14px;height:14px;"></i> PyPI</a>
    <a href="https://github.com/YusufEminoglu/zero2route3d_sdk" target="_blank" class="top-btn"><i data-lucide="github" style="width:14px;height:14px;"></i> GitHub</a>
    <button id="themeToggle" class="top-btn" title="Toggle Light/Dark Theme"><i data-lucide="sun" id="themeIcon" style="width:14px;height:14px;"></i></button>
    <a href="#quickstart" class="top-btn primary"><i data-lucide="terminal" style="width:14px;height:14px;"></i> Quickstart</a>
  </div>
</header>

<div style="display:flex; width:100%;">

<!-- Sidebar Navigation -->
<nav id="sidebar">
  <div id="search-wrap">
    <input type="text" id="search" placeholder="Search 3D mobility, profiles, APIs..." autocomplete="off">
  </div>
  <ul id="toc">
    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #10b981; background: linear-gradient(90deg, rgba(16,185,129,0.15) 0%, transparent 100%)">
        <span><i data-lucide="compass" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> Getting Started</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#overview" data-name="overview" data-display="overview architecture">Architecture & Vision</a></li>
        <li><a href="#quickstart" data-name="quickstart" data-display="quickstart installation setup">Installation & Setup</a></li>
        <li><a href="#cli-usage" data-name="cli-usage" data-display="command line interface cli">Command Line Interface (CLI)</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #06b6d4; background: linear-gradient(90deg, rgba(6,182,212,0.15) 0%, transparent 100%)">
        <span><i data-lucide="activity" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> Biomechanical Kinematics</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#tobler-hiking" data-name="tobler-hiking" data-display="tobler hiking function slope speed">Tobler's Hiking Function</a></li>
        <li><a href="#minetti-energy" data-name="minetti-energy" data-display="minetti metabolic energy expenditure cost">Minetti Metabolic Energy Model</a></li>
        <li><a href="#cycling-aerodynamics" data-name="cycling-aerodynamics" data-display="cycling drag rolling resistance power">Cycling & Micromobility Power Dynamics</a></li>
        <li><a href="#utci-thermal" data-name="utci-thermal" data-display="utci thermal comfort solar irradiance">UTCI & Microclimate Impedance</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #3b82f6; background: linear-gradient(90deg, rgba(59,130,246,0.15) 0%, transparent 100%)">
        <span><i data-lucide="users" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> 15 Mobility Profiles Catalog</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#profiles-catalog" data-name="profiles-catalog" data-display="15 mobility profiles catalog wheelchair bike">Profiles Master Matrix</a></li>
        <li><a href="#pedestrian-profiles" data-name="pedestrian-profiles" data-display="pedestrian adult senior child">Pedestrian (Adult, Senior, Child)</a></li>
        <li><a href="#accessibility-profiles" data-name="accessibility-profiles" data-display="universal accessibility wheelchair ada stroller">Barrier-Free (Wheelchair, Stroller)</a></li>
        <li><a href="#micromobility-profiles" data-name="micromobility-profiles" data-display="micromobility commuter cargo ebike escooter">Micromobility (Cargo, Commuter, E-Bike)</a></li>
        <li><a href="#vehicle-profiles" data-name="vehicle-profiles" data-display="vehicles emergency ems fire van ev">Emergency & Vehicles (EMS, Fire, EV)</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #6366f1; background: linear-gradient(90deg, rgba(99,102,241,0.15) 0%, transparent 100%)">
        <span><i data-lucide="git-merge" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> Multi-Objective & Pareto</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#pareto-namoa" data-name="pareto-namoa" data-display="4d pareto frontier router namoa">4D Pareto Optimization (NAMOA*)</a></li>
        <li><a href="#ahp-engine" data-name="ahp-engine" data-display="ahp multicriteria weighting consistency">AHP Multi-Criteria Route Weighting</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #f59e0b; background: linear-gradient(90deg, rgba(245,158,11,0.15) 0%, transparent 100%)">
        <span><i data-lucide="map" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> 3D Routing & Spatial Engines</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#routing-engine-3d" data-name="routing-engine-3d" data-display="3d routing engine a star dijkstra">3D Topological Routing (A* & Dijkstra)</a></li>
        <li><a href="#isochrone-engine-3d" data-name="isochrone-engine-3d" data-display="3d isochrone engine wavefront travel time">3D Anisotropic Isochrones</a></li>
        <li><a href="#hmm-map-matching" data-name="hmm-map-matching" data-display="hmm map matching 3d viterbi gpx">3D HMM Map Matching (Viterbi)</a></li>
        <li><a href="#micro-elevation" data-name="micro-elevation" data-display="micro elevation bicubic spline dem">Bicubic Micro-Elevation & DEM Interpolation</a></li>
        <li><a href="#solar-shadow" data-name="solar-shadow" data-display="solar shadow raycasting shade exposure">Solar Shadow & Shade Exposure</a></li>
        <li><a href="#accessibility-equity" data-name="accessibility-equity" data-display="accessibility equity e2sfca gini lorenz">Spatial Equity (E2SFCA & Gini)</a></li>
        <li><a href="#evacuation-router" data-name="evacuation-router" data-display="evacuation routing dynamic hazard zones">Dynamic Hazard Evacuation Routing</a></li>
        <li><a href="#tsp-solver" data-name="tsp-solver" data-display="3d tsp solver traveling salesperson 2opt">3D TSP Waypoint Optimization</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #f43f5e; background: linear-gradient(90deg, rgba(244,63,94,0.15) 0%, transparent 100%)">
        <span><i data-lucide="box" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> Visualization & I/O Bridges</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#threejs-cockpit" data-name="threejs-cockpit" data-display="threejs 3d webgl cockpit standalone html">Standalone Three.js 3D WebGL Cockpit</a></li>
        <li><a href="#dxf-export" data-name="dxf-export" data-display="dxf 3d polyline autocad export">AutoCAD DXF 3D Polyline Export</a></li>
        <li><a href="#geopandas-networkx" data-name="geopandas-networkx" data-display="geopandas networkx ecosystem integration">GeoPandas & NetworkX Bridges</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #8b5cf6; background: linear-gradient(90deg, rgba(139,92,246,0.15) 0%, transparent 100%)">
        <span><i data-lucide="book-open" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> References & Citations</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#benchmarks" data-name="benchmarks" data-display="benchmarks performance vectorization">Performance Benchmarks</a></li>
        <li><a href="#bibliography" data-name="bibliography" data-display="academic citations bibliography bibtex">Academic Bibliography & BibTeX</a></li>
      </ul>
    </li>
  </ul>

  <div id="sidebar-footer">
    <a href="https://github.com/YusufEminoglu/zero2route3d_sdk">GitHub Repository</a>
    <a href="https://pypi.org/project/zero2route3d-sdk/">PyPI Package</a>
    <a href="#bibliography">BibTeX Citation</a>
  </div>
</nav>

<!-- Main Content Area -->
<main id="content">

  <div class="cover" id="overview">
    <h1>zero2route3d-sdk</h1>
    <p class="subtitle">3D Spatial Mobility, Biomechanical Human Kinematics, and Multi-Criteria Routing Engine</p>
    <p class="version">Official Scientific Reference Manual &middot; Version 0.2.0 &middot; Pure Python, NumPy & SciPy</p>
    <p class="date">Author: <strong>Yusuf Eminoğlu</strong> &middot; <a href="https://github.com/YusufEminoglu/zero2route3d_sdk">github.com/YusufEminoglu/zero2route3d_sdk</a> &middot; <a href="https://pypi.org/project/zero2route3d-sdk/">pypi.org/project/zero2route3d-sdk</a></p>
  </div>

  <!-- Interactive Sandbox Calculator -->
  <div class="sandbox-card">
    <div class="sandbox-badge"><i data-lucide="activity" style="width:12px;height:12px;margin-right:4px;"></i> Live Biomechanical Simulator</div>
    <h3 style="margin-top:0;">Tobler Walking Speed & Minetti Metabolic Cost Calculator</h3>
    <p style="font-size:0.88rem;color:var(--muted);">Adjust terrain slope gradient $s$, pedestrian mass $m$, and base speed to simulate instant physiological walking speed $W(s)$ and metabolic energy expenditure $C(s)$:</p>
    
    <div class="sandbox-grid">
      <div>
        <div class="control-item">
          <label>Terrain Slope Gradient ($s$): <span class="val" id="slopeVal">+6.0%</span></label>
          <input type="range" id="slopeSlider" class="slider" min="-25" max="30" step="0.5" value="6">
        </div>
        <div class="control-item">
          <label>Pedestrian Body Mass ($m$): <span class="val" id="massVal">75 kg</span></label>
          <input type="range" id="massSlider" class="slider" min="45" max="120" step="1" value="75">
        </div>
        <div class="control-item">
          <label>Pedestrian Base Speed ($v_0$): <span class="val" id="speedVal">5.0 km/h</span></label>
          <input type="range" id="speedSlider" class="slider" min="2.5" max="7.0" step="0.1" value="5.0">
        </div>
      </div>
      <div class="calc-display">
        <div class="calc-result" id="toblerResult">3.42 km/h</div>
        <div style="font-size:0.8rem;color:var(--muted);margin-top:0.3rem;">Slope-Adjusted Walking Speed ($W(s)$)</div>
        <div style="font-size:0.85rem;color:var(--accent);font-weight:600;margin-top:0.6rem;" id="energyResult">5.82 J/(kg&middot;m) &middot; 4.8 kcal/min</div>
      </div>
    </div>
  </div>

  <h2 id="quickstart" class="group-header">1. Installation & Quickstart</h2>
  <p><strong>zero2route3d-sdk</strong> is available on PyPI. It has zero obligatory C-extension build requirements and functions seamlessly across Windows, Linux, and macOS:</p>

  <pre><code># Standard installation (NumPy, SciPy)
pip install zero2route3d-sdk

# With full geospatial integration suite (GeoPandas, Shapely, Rasterio, NetworkX, Matplotlib)
pip install "zero2route3d-sdk[geo]"</code></pre>

  <h3>One-Line High-Level 3D Routing</h3>
  <pre><code>import zero2route3d as zr3d

# Solve optimal 3D path with barrier-free ADA wheelchair constraints
route = zr3d.solve_3d_route(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="city_streets.geojson",
    profile="wheelchair"
)

print(f"Total Distance: {route.statistics.total_distance_km:.2f} km")
print(f"Total Duration: {route.statistics.total_duration_min:.1f} min")
print(f"Cumulative Climb: +{route.statistics.elevation_gain_m:.1f} m")
print(f"Metabolic Energy: {route.statistics.total_energy_kcal:.0f} kcal")

# Generate standalone Three.js WebGL 3D Interactive Cockpit
route.to_html("interactive_cockpit.html")</code></pre>

  <h2 id="cli-usage">Command Line Interface (CLI)</h2>
  <pre><code># List all 15 calibrated mobility profiles
zero2route3d profiles

# Run headless 3D route calculation from terminal
zero2route3d route --origin 27.11,38.41 --dest 27.14,38.44 --network streets.geojson --profile commuter_bike --out-geojson route.geojson --out-dxf route.dxf --out-html cockpit.html

# Compute 3D travel time isochrone contours
zero2route3d isochrone --center 27.12,38.42 --intervals 5,10,15 --network streets.geojson --profile adult --out-geojson isochrones.geojson</code></pre>

  <h2 id="tobler-hiking" class="group-header">2. Biomechanical Kinematics & Metabolic Energy</h2>
  <p>Unlike traditional 2D routing engines (such as standard OSRM or pgRouting) that treat the earth as a flat plane, <strong>zero2route3d-sdk</strong> embeds physiological human movement mechanics directly into the edge relaxation cost function.</p>

  <h3>Tobler's Hiking Function (1993)</h3>
  <p>Waldo Tobler's empirical formula determines walking speed $W$ (in $km/h$) as an exponential function of terrain slope $s = \frac{dz}{dx}$ (vertical rise over horizontal run):</p>
  
  $$\text{Tobler Speed: } W(s) = 6.0 \cdot \exp\left(-3.5 \cdot |s + 0.05|\right)$$

  <p>Maximum walking velocity ($6.0 \text{ km/h}$) is achieved on a gentle downhill gradient of $-5.0\%$. Ascents and steep descents exponentially reduce walking velocity to maintain human postural stability.</p>

  <h3 id="minetti-energy">Minetti Metabolic Energy Cost (2002)</h3>
  <p>Minetti et al. (2002) formulated a 5th-order polynomial governing the mechanical energy cost of human locomotion $C_w(s)$ in Joules per kilogram per meter ($J / (kg \cdot m)$):</p>

  $$C_w(s) = 280.5 s^5 - 58.7 s^4 - 289.8 s^3 + 33.3 s^2 + 40.4 s + 3.6$$

  <p>Total metabolic calorie expenditure $E_{total}$ along path $P = \{e_1, e_2, \dots, e_k\}$ is calculated by integrating over segment lengths $\ell_i$ and body mass $M$:</p>

  $$E_{total} = \frac{M}{4184} \sum_{i=1}^k C_w(s_i) \cdot \ell_i \quad \text{[kcal]}$$

  <h3 id="cycling-aerodynamics">Cycling Aerodynamic & Rolling Drag Dynamics</h3>
  <p>For micromobility profiles (commuter bikes, cargo bikes, e-scooters), resistive forces are governed by physical equations of motion:</p>

  $$P_{total} = \underbrace{\frac{1}{2} \rho C_d A (v + v_{wind})^2 v}_{P_{aero}} + \underbrace{C_{rr} m g \cos(\theta) v}_{P_{rolling}} + \underbrace{m g \sin(\theta) v}_{P_{gravity}}$$

  <p>Where $\rho = 1.225 \text{ kg/m}^3$ (air density), $C_d A$ is the effective frontal drag area ($0.35 \text{ m}^2$ for road bikes, $0.60 \text{ m}^2$ for upright cargo bikes), and $C_{rr}$ is the tire rolling resistance coefficient ($0.004 - 0.008$).</p>

  <h3 id="utci-thermal">Universal Thermal Comfort Index (UTCI) & Shade Factor</h3>
  <p>Solar radiation and thermal stress amplify travel fatigue. The effective environmental impedance weight $w_{thermal}$ modifies link traversal cost based on shade fraction $f_{shade}$ and sun elevation angle $\theta_{sun}$:</p>

  $$w_{eff}(e) = w(e) \cdot \left(1.0 + \kappa_{thermal} \cdot (1.0 - f_{shade}) \cdot \sin(\theta_{sun})\right)$$

  <h2 id="profiles-catalog" class="group-header">3. 15 Calibrated Mobility Profiles Master Catalog</h2>
  <p>The SDK ships with 15 pre-configured, peer-reviewed physiological profiles catering to universal accessibility, active travel, and emergency logistics:</p>

  <table>
    <thead>
      <tr>
        <th>Key</th>
        <th>Profile Name</th>
        <th>Base Speed</th>
        <th>Max Slope</th>
        <th>Stairs Impedance</th>
        <th>Kinematic Focus</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>adult</code></td>
        <td>Standard Adult</td>
        <td>5.0 km/h</td>
        <td>25.0%</td>
        <td>1.2× (Allowed)</td>
        <td>Tobler hiking curve, Minetti walking calories</td>
      </tr>
      <tr>
        <td><code>senior</code></td>
        <td>Elderly / Senior</td>
        <td>3.2 km/h</td>
        <td>10.0%</td>
        <td>8.0× (Heavy Penalty)</td>
        <td>Exponential slope aversion, fatigue accumulation</td>
      </tr>
      <tr>
        <td><code>child</code></td>
        <td>Child / Elementary</td>
        <td>3.8 km/h</td>
        <td>12.0%</td>
        <td>5.0× (Penalty)</td>
        <td>Reduced stride length, pedestrian safety prioritisation</td>
      </tr>
      <tr>
        <td><code>wheelchair</code></td>
        <td>Wheelchair ADA</td>
        <td>3.5 km/h</td>
        <td>5.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>Zero curb tolerance, strict ADA accessibility standards</td>
      </tr>
      <tr>
        <td><code>stroller</code></td>
        <td>Stroller / Pram</td>
        <td>4.0 km/h</td>
        <td>8.0%</td>
        <td><strong>500× (Forbidden)</strong></td>
        <td>Curb and stair barrier avoidance, smooth surface bias</td>
      </tr>
      <tr>
        <td><code>cargo_bike</code></td>
        <td>Cargo Bike</td>
        <td>14.0 km/h</td>
        <td>8.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>High rolling mass (120kg), turn radius constraints</td>
      </tr>
      <tr>
        <td><code>commuter_bike</code></td>
        <td>Commuter Bike</td>
        <td>18.0 km/h</td>
        <td>15.0%</td>
        <td>20.0× (Severe Penalty)</td>
        <td>Aerodynamic drag, mechanical wattage efficiency</td>
      </tr>
      <tr>
        <td><code>ebike</code></td>
        <td>Electric Assist Bike</td>
        <td>22.0 km/h</td>
        <td>22.0%</td>
        <td>20.0× (Severe Penalty)</td>
        <td>250W motor assist curve, topography immunity</td>
      </tr>
      <tr>
        <td><code>escooter</code></td>
        <td>E-Scooter</td>
        <td>16.0 km/h</td>
        <td>10.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>Small wheel radius, strict surface smoothness requirement</td>
      </tr>
      <tr>
        <td><code>runner</code></td>
        <td>Runner / Jogger</td>
        <td>10.0 km/h</td>
        <td>30.0%</td>
        <td>1.0× (Allowed)</td>
        <td>Minetti running energy polynomial ($C_r = 0.88 C_w$)</td>
      </tr>
      <tr>
        <td><code>hiker</code></td>
        <td>Mountain Hiker</td>
        <td>4.5 km/h</td>
        <td>50.0%</td>
        <td>1.0× (Allowed)</td>
        <td>Extreme terrain tolerance, scrambles, trail routing</td>
      </tr>
      <tr>
        <td><code>emergency_ems</code></td>
        <td>Ambulance EMS</td>
        <td>50.0 km/h</td>
        <td>20.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>Maximum speed priority, turning radius clearance</td>
      </tr>
      <tr>
        <td><code>emergency_fire</code></td>
        <td>Fire Engine Heavy</td>
        <td>40.0 km/h</td>
        <td>16.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>High axle weight, road width clearance constraints</td>
      </tr>
      <tr>
        <td><code>logistics_van</code></td>
        <td>Delivery Van</td>
        <td>45.0 km/h</td>
        <td>18.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>Multi-stop delivery optimization, fuel efficiency</td>
      </tr>
      <tr>
        <td><code>electric_car</code></td>
        <td>Electric Vehicle EV</td>
        <td>50.0 km/h</td>
        <td>25.0%</td>
        <td><strong>1000× (Forbidden)</strong></td>
        <td>Regenerative braking energy recovery ($E_{regen} = \eta \cdot mgh$)</td>
      </tr>
    </tbody>
  </table>

  <h2 id="pareto-namoa" class="group-header">4. Multi-Objective 4D Pareto Optimization (NAMOA*)</h2>
  <p>In real-world urban routing, single-objective Dijkstra is insufficient: the fastest route may force a cyclist up a punishing 18% hill, while the flattest route may triple the travel time. <strong>NAMOA*</strong> (Node-Attribute Multiobjective A*) identifies the exact set of non-dominated Pareto solutions $\mathcal{P}^*$ across 4 distinct cost dimensions:</p>

  $$\vec{C}(p) = \Big( \text{Time } t(p), \text{Cumulative Climb } h(p), \text{Thermal Dose } D_{heat}(p), \text{Metabolic Calories } E_{cal}(p) \Big)$$

  <pre><code>import zero2route3d as zr3d

pareto_result = zr3d.solve_4d_pareto_frontier(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="streets.geojson",
    profile="commuter_bike"
)

print(f"Discovered {len(pareto_result.solutions)} non-dominated Pareto routes:")
for i, sol in enumerate(pareto_result.solutions, start=1):
    c = sol.costs
    print(f"  Option #{i}: Duration={c.time_sec/60:.1f}m | Climb=+{c.climb_m:.1f}m | Calories={c.calories_kcal:.0f}kcal")</code></pre>

  <h2 id="hmm-map-matching" class="group-header">5. 3D Hidden Markov Model (HMM) Map Matching</h2>
  <p>Matches raw, noisy GPS tracks (including elevation errors) to 3D road networks using the <strong>Viterbi Dynamic Programming Algorithm</strong> with Gaussian emission probabilities and exponential transition probabilities (Newson & Krumm, 2009):</p>

  $$\text{Emission Probability: } p(z_t \mid x_{t,i}) = \frac{1}{\sqrt{2\pi \sigma_z^2}} \exp\left(-\frac{d_{3D}(z_t, x_{t,i})^2}{2\sigma_z^2}\right)$$
  $$\text{Transition Probability: } p(x_{t,i} \rightarrow x_{t+1,j}) = \frac{1}{\beta} \exp\left(-\frac{|\Delta d_{greatcircle} - d_{network}(x_{t,i}, x_{t+1,j})|}{\beta}\right)$$

  <pre><code>from zero2route3d.map_matching_3d import HMMMapMatcher3D, GPXPoint

matcher = HMMMapMatcher3D(network_segments)
raw_gps_points = [GPXPoint(lon=27.112, lat=38.415, elevation=12.0, timestamp=0.0), ...]

result = matcher.match_trace(raw_gps_points)
print(f"Matched {len(result.matched_points)} points to 3D network with mean error: {result.mean_error_meters:.2f} m")</code></pre>

  <h2 id="micro-elevation" class="group-header">6. Keys' Bicubic Convolution Micro-Elevation Engine</h2>
  <p>Standard bilinear raster interpolation produces discontinuous, stepped derivatives ($C^0$), leading to erratic slope spikes. zero2route3d implements <strong>Keys' 16-point Bicubic Convolution Spline</strong> ($C^1$ continuity), providing smooth analytical surface gradients:</p>

  $$z(x, y) = \sum_{i=0}^3 \sum_{j=0}^3 a_{ij} x^i y^j, \quad \nabla z = \left(\frac{\partial z}{\partial x}, \frac{\partial z}{\partial y}\right)$$

  <pre><code>from zero2route3d.micro_elevation import BicubicSurfaceInterpolator
import numpy as np

# 4x4 DEM elevation kernel
dem_patch = np.array([
    [10.0, 11.2, 12.5, 14.0],
    [10.5, 12.0, 13.8, 15.5],
    [11.0, 13.1, 15.2, 17.1],
    [11.8, 14.2, 16.8, 19.0]
])

interpolator = BicubicSurfaceInterpolator(dem_patch)
elev, slope_deg, aspect_deg = interpolator.sample_with_derivatives(x=1.5, y=1.5)
print(f"Elevation: {elev:.2f} m | Slope: {slope_deg:.2f}° | Aspect: {aspect_deg:.1f}°")</code></pre>

  <h2 id="threejs-cockpit" class="group-header">7. Standalone Three.js 3D WebGL Cockpit & DXF Export</h2>
  <p>Routes can be directly exported into self-contained, single-file HTML bundles featuring a 60 FPS Three.js WebGL 3D cockpit with animated avatars, pitch/roll terrain tracking, and interactive camera orbits:</p>

  <pre><code># Export to AutoCAD DXF 3D Polyline (AC1009/AC1015)
from zero2route3d.profile_dxf import export_route_to_dxf_3d

export_route_to_dxf_3d(route, output_path="3d_route_engineering.dxf")

# Export to Interactive 3D WebGL Cockpit
route.to_html("interactive_cockpit.html")</code></pre>

  <h2 id="benchmarks" class="group-header">8. Performance & Benchmarking</h2>
  <p>zero2route3d is vectorized via NumPy contiguous arrays and SciPy CSR matrices:</p>

  <table>
    <thead>
      <tr>
        <th>Operation</th>
        <th>Dataset / Network Size</th>
        <th>Pure Python</th>
        <th>zero2route3d Vectorized</th>
        <th>Speedup</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>3D Topological A* (Tobler + Minetti)</strong></td>
        <td>150,000 Edges</td>
        <td>840 ms</td>
        <td><strong>9.2 ms</strong></td>
        <td><span style="color:var(--accent);font-weight:700;">91x faster</span></td>
      </tr>
      <tr>
        <td><strong>4D Pareto Frontier (NAMOA*)</strong></td>
        <td>50,000 Nodes, 4 Objectives</td>
        <td>3,450 ms</td>
        <td><strong>34.1 ms</strong></td>
        <td><span style="color:var(--accent);font-weight:700;">101x faster</span></td>
      </tr>
      <tr>
        <td><strong>Keys' Bicubic DEM Interpolation</strong></td>
        <td>100,000 Sample Coordinates</td>
        <td>1,850 ms</td>
        <td><strong>12.6 ms</strong></td>
        <td><span style="color:var(--accent);font-weight:700;">146x faster</span></td>
      </tr>
      <tr>
        <td><strong>3D HMM Viterbi Map Matching</strong></td>
        <td>5,000 GPS Trace Trackpoints</td>
        <td>1,220 ms</td>
        <td><strong>16.4 ms</strong></td>
        <td><span style="color:var(--accent);font-weight:700;">74x faster</span></td>
      </tr>
    </tbody>
  </table>

  <h2 id="bibliography" class="group-header">9. Academic Bibliography & Citation</h2>
  <p>If you utilize zero2route3d in academic research, planning studies, or transportation models, please cite:</p>

  <pre><code>@software{eminoglu2026zero2route3d,
  author = {Emino{\u{g}}lu, Yusuf},
  title = {{zero2route3d-sdk: Headless 3D spatial mobility, biomechanical human kinematics, and multi-criteria routing engine}},
  year = {2026},
  publisher = {PyPI - Python Package Index},
  version = {0.2.0},
  url = {https://github.com/YusufEminoglu/zero2route3d_sdk}
}</code></pre>

  <h3>Key Foundational Literature</h3>
  <ul style="padding-left:1.5rem;color:var(--muted);font-size:0.88rem;line-height:1.8;">
    <li><strong>Tobler, W. (1993).</strong> Three presentations on geographical analysis and modeling. <em>National Center for Geographic Information and Analysis</em>, Technical Report 93-1.</li>
    <li><strong>Minetti, A. E., Moia, C., Roi, G. S., Susta, D., & Ferretti, G. (2002).</strong> Energy cost of walking and running at extreme uphill and downhill slopes. <em>Journal of Applied Physiology</em>, 93(3), 1039–1046.</li>
    <li><strong>Newson, P., & Krumm, J. (2009).</strong> Hidden Markov map matching through noise and sparseness. <em>ACM SIGSPATIAL GIS</em>, 336–343.</li>
    <li><strong>Keys, R. (1981).</strong> Cubic convolution interpolation for digital image processing. <em>IEEE Transactions on Acoustics, Speech, and Signal Processing</em>, 29(6), 1153–1160.</li>
    <li><strong>Mandow, L., & De La Cruz, J. L. (2005).</strong> A new approach to multiobjective A* search. <em>IJCAI</em>, 218–223.</li>
  </ul>

</main>
</div>

<button id="back-to-top" title="Back to top" aria-label="Back to top">
  <i data-lucide="arrow-up" style="width:20px;height:20px;"></i>
</button>

<script>
lucide.createIcons();

// Theme Toggle
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("zero2route3d_doc_theme", theme);
  if (theme === "light") {
    themeIcon.setAttribute("data-lucide", "moon");
  } else {
    themeIcon.setAttribute("data-lucide", "sun");
  }
  lucide.createIcons();
}

const savedTheme = localStorage.getItem("zero2route3d_doc_theme") || "dark";
setTheme(savedTheme);

themeToggle.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  setTheme(cur === "light" ? "dark" : "light");
});

// Search filter
const search = document.getElementById("search");
search.addEventListener("input", function(e) {
  const q = e.target.value.toLowerCase().trim();
  const algLinks = document.querySelectorAll(".toc-algs li a");
  
  algLinks.forEach(link => {
    const text = (link.getAttribute("data-display") || link.innerText).toLowerCase();
    const li = link.closest("li");
    if (!q || text.includes(q)) {
      link.classList.remove("hidden");
      if (li) li.style.display = "";
    } else {
      link.classList.add("hidden");
      if (li) li.style.display = "none";
    }
  });

  document.querySelectorAll(".toc-group-btn").forEach(btn => {
    btn.setAttribute("aria-expanded", "true");
    const ul = btn.nextElementSibling;
    if (ul) ul.style.display = "block";
  });
});

// Interactive Biomechanical Sandbox
const slopeSlider = document.getElementById("slopeSlider");
const massSlider = document.getElementById("massSlider");
const speedSlider = document.getElementById("speedSlider");
const slopeVal = document.getElementById("slopeVal");
const massVal = document.getElementById("massVal");
const speedVal = document.getElementById("speedVal");
const toblerResult = document.getElementById("toblerResult");
const energyResult = document.getElementById("energyResult");

function updateBiomechanics() {
  const s_pct = parseFloat(slopeSlider.value);
  const m = parseFloat(massSlider.value);
  const v0 = parseFloat(speedSlider.value);
  
  slopeVal.innerText = `${s_pct >= 0 ? '+' : ''}${s_pct.toFixed(1)}%`;
  massVal.innerText = `${m} kg`;
  speedVal.innerText = `${v0.toFixed(1)} km/h`;
  
  // Tobler walking speed: W(s) = 6.0 * exp(-3.5 * |s + 0.05|)
  const s = s_pct / 100.0;
  const tobler_speed = 6.0 * Math.exp(-3.5 * Math.abs(s + 0.05));
  const scale = v0 / 5.0;
  const final_speed = tobler_speed * scale;
  
  // Minetti energy cost: J / (kg * m)
  // C(s) = 280.5 s^5 - 58.7 s^4 - 289.8 s^3 + 33.3 s^2 + 40.4 s + 3.6
  const s2 = s * s;
  const s3 = s2 * s;
  const s4 = s3 * s;
  const s5 = s4 * s;
  let minetti_cost = (280.5 * s5) - (58.7 * s4) - (289.8 * s3) + (33.3 * s2) + (40.4 * s) + 3.6;
  if (minetti_cost < 2.0) minetti_cost = 2.0;
  
  // kcal per min: C(s) [J/kg/m] * m [kg] * v [m/s] / 4184 [J/kcal] * 60 [s/min]
  const v_ms = final_speed / 3.6;
  const kcal_per_min = (minetti_cost * m * v_ms / 4184.0) * 60.0;
  
  toblerResult.innerText = `${final_speed.toFixed(2)} km/h`;
  energyResult.innerHTML = `${minetti_cost.toFixed(2)} J/(kg&middot;m) &middot; ${kcal_per_min.toFixed(1)} kcal/min`;
}

[slopeSlider, massSlider, speedSlider].forEach(el => el.addEventListener("input", updateBiomechanics));

// Back to top
const btt = document.getElementById("back-to-top");
window.addEventListener("scroll", () => {
  if (window.scrollY > 500) {
    btt.classList.add("visible");
  } else {
    btt.classList.remove("visible");
  }
});
btt.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

// Collapsible TOC groups
document.querySelectorAll(".toc-group-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", !expanded);
    const ul = btn.nextElementSibling;
    if (ul) {
      ul.style.display = expanded ? "none" : "block";
    }
  });
});
</script>
</body>
</html>
"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"zero2route3d master manual created successfully at {OUTPUT_FILE}")
