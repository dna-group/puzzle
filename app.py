import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink — Grid", layout="wide")
st.title("Slitherlink — Grid of dots")

# User controls
cols = st.sidebar.number_input("Columns (X)", min_value=2, max_value=40, value=7, step=1)
rows = st.sidebar.number_input("Rows (Y)", min_value=2, max_value=40, value=7, step=1)
cell_px = st.sidebar.slider("Cell size (px)", min_value=24, max_value=120, value=56)

# compute svg dimensions (viewBox coordinates)
margin = 8
view_w = cols * cell_px + margin * 2
view_h = rows * cell_px + margin * 2

# Build SVG string (dots only)
dot_radius = max(2, int(cell_px * 0.07))
svg_parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" style="width:100%;height:auto;touch-action:none">',
    f'<rect width="{view_w}" height="{view_h}" fill="transparent"/>'
]
for r in range(rows + 1):
    for c in range(cols + 1):
        cx = margin + c * cell_px
        cy = margin + r * cell_px
        svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{dot_radius}" fill="#000" />')

svg_parts.append("</svg>")
svg_code = "\n".join(svg_parts)

# Render SVG inside an iframe (component) so we can later add JS handlers safely
iframe_height = 360 if max(rows, cols) <= 10 else 720
html(svg_code, height=iframe_height, scrolling=True)

st.markdown("Grid drawn. Next: make edges selectable by tapping a dot-pair or by tapping the edge region.")
