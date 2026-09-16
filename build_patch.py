from pathlib import Path
path = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
src = path.read_text()
if 'd.setBackgroundColor(null);' not in src:
    src = src.replace('            d.setDefaultBackground(false);\n', '            d.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n', 1)
path.write_text(src)
