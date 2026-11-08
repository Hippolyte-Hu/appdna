# Design references and decisions

- React Flow mind-map example: https://reactflow.dev/learn/tutorials/mind-map-app-with-react-flow — drag/pan/zoom, keyboard-accessible nodes, minimap and fit-view are useful inspection primitives.
- Cytoscape.js gallery: https://js.cytoscape.org/ — grouped layouts, navigation and selective edge highlighting reduce dense-map clutter.

AppDNA uses @xyflow/react 12, not a static SVG imitation. A readable initial application neighborhood and an explicit Fit all action avoid reducing 145 nodes to unreadable text. All nodes remain in the graph. Selected evidence brightens adjacent edges and hides unrelated labels. Motion is opt-in and CSS respects reduced motion. A jump selector supports keyboard access to every source and moves the viewport to it. Expanded view, focus app, layout reset, minimap and original source-text panel remain available. Layout is keyed by graph content, not polling-array identity, so dragging survives polling.

Actual regression: `PYTHONPATH=. .venv/bin/python tests/verify_graph_browser.py` — actual mouse drag, zoom, fit and reading all 9 collected articles on project_934cb111315a; 145 nodes; no page exceptions. Initial and post-fit screenshots in tasks/overnight/evidence/.
