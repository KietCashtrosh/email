```python
import os
import re
from jinja2 import Template

# Configuration
TEMPLATE_DIR = "templates/customer"
OUTPUT_DIR = "templates/customer/styled"
COLORS = {
    "primary": "#7C1EE9",  # Purple
    "secondary": "#E1760C",  # Orange
    "light-purple": "#D8BFFF",
    "light-orange": "#FFDAB9",
    "light-gray": "#F3F4F6",
    "gray": "#6B7280"
}
TAILWIND_CLASSES = {
    "container": "max-w-5xl mx-auto",
    "heading": "text-3xl font-bold text-[var(--primary)] mb-6",
    "subheading": "text-xl font-semibold text-[var(--gray)] mb-4",
    "card": "bg-white p-6 rounded-lg shadow-md",
    "link": "text-[var(--secondary)] hover:underline",
    "button": "btn-primary px-4 py-2 rounded w-full",
    "table": "w-full border-collapse",
    "table-header": "bg-[var(--light-gray)]",
    "table-row": "border-b hover:bg-[var(--light-gray)]",
    "form-input": "w-full p-2 border rounded",
    "error": "text-red-500 text-sm",
    "badge": "bg-green-500 text-white text-xs px-2 py-1 rounded"
}

# CSS to replace with Tailwind
CSS_REPLACEMENTS = {
    r'font-family:\s*[^;]+;': '',  # Remove font-family (handled by base.html)
    r'background:\s*#fff;': 'bg-white',
    r'background-color:\s*#f9f9f9;': 'bg-[var(--light-gray)]',
    r'border:\s*1px solid #eee;': 'border border-[var(--light-gray)]',
    r'border:\s*1px solid #ddd;': 'border border-[var(--light-gray)]',
    r'border-radius:\s*8px;': 'rounded-lg',
    r'padding:\s*20px;': 'p-6',
    r'color:\s*#333;': 'text-[var(--gray)]',
    r'color:\s*#666;': 'text-[var(--gray)]',
    r'color:\s*#007bff;': 'text-[var(--secondary)]',
    r'background-color:\s*#007bff;': 'bg-[var(--primary)]',
    r'background-color:\s*#28a745;': 'bg-green-500',
    r'margin-bottom:\s*20px;': 'mb-6',
    r'font-weight:\s*bold;': 'font-bold',
    r'width:\s*100%;': 'w-full',
    r'box-sizing:\s*border-box;': ''  # Handled by Tailwind
}

def apply_tailwind_styling(template_content):
    # Remove inline style blocks
    style_block = re.search(r'<style[^>]*>(.*?)</style>', template_content, re.DOTALL)
    if style_block:
        style_content = style_block.group(1)
        for pattern, replacement in CSS_REPLACEMENTS.items():
            style_content = re.sub(pattern, replacement, style_content)
        template_content = template_content.replace(style_block.group(0), '')

    # Update HTML elements
    # Headings
    template_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'<h1 class="{}">\1</h1>'.format(TAILWIND_CLASSES["heading"]), template_content)
    template_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'<h2 class="{}">\1</h2>'.format(TAILWIND_CLASSES["subheading"]), template_content)

    # Links
    template_content = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', r'<a href="\1" class="{}">\2</a>'.format(TAILWIND_CLASSES["link"]), template_content)

    # Forms
    template_content = re.sub(r'<form\s+method="POST"[^>]*>', r'<form method="POST" class="{}">'.format(TAILWIND_CLASSES["card"]), template_content)
    template_content = re.sub(r'<form\s+method="post"[^>]*>', r'<form method="POST" class="{}">'.format(TAILWIND_CLASSES["card"]), template_content)
    template_content = re.sub(r'<input([^>]*name="[^"]+"[^>]*)(?<!>)>', r'<input\1 class="{}">'.format(TAILWIND_CLASSES["form-input"]), template_content)
    template_content = re.sub(r'<select([^>]*name="[^"]+"[^>]*)(?<!>)>', r'<select\1 class="{}">'.format(TAILWIND_CLASSES["form-input"]), template_content)
    template_content = re.sub(r'<button[^>]*type="submit"[^>]*>(.*?)</button>', r'<button type="submit" class="{}">\1</button>'.format(TAILWIND_CLASSES["button"]), template_content)

    # Tables
    template_content = re.sub(r'<table[^>]*>', r'<table class="{}">'.format(TAILWIND_CLASSES["table"]), template_content)
    template_content = re.sub(r'<thead[^>]*>', r'<thead class="{}">'.format(TAILWIND_CLASSES["table-header"]), template_content)
    template_content = re.sub(r'<tr[^>]*>', r'<tr class="{}">'.format(TAILWIND_CLASSES["table-row"]), template_content)
    template_content = re.sub(r'<th[^>]*>', r'<th class="p-4 text-left text-[var(--gray)]">', template_content)
    template_content = re.sub(r'<td[^>]*>', r'<td class="p-4 text-[var(--gray)]">', template_content)

    # Containers
    template_content = re.sub(r'<div[^>]*class="[^"]*container[^"]*"[^>]*>', r'<div class="{}">'.format(TAILWIND_CLASSES["container"]), template_content)
    template_content = re.sub(r'<div[^>]*class="[^"]*section[^"]*"[^>]*>', r'<div class="{}">'.format(TAILWIND_CLASSES["card"]), template_content)

    # Add CSRF token if form is present
    if '<form' in template_content:
        template_content = template_content.replace('<form', '<form {{ form.hidden_tag() }}')

    # Wrap content in container if not already present
    if 'max-w-' not in template_content:
        template_content = template_content.replace('{% block customer_content %}', '{% block customer_content %}\n<div class="{}">'.format(TAILWIND_CLASSES["container"]))
        template_content = template_content.replace('{% endblock %}', '</div>\n{% endblock %}')

    return template_content

def process_templates():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for filename in os.listdir(TEMPLATE_DIR):
        if filename.endswith('.html'):
            input_path = os.path.join(TEMPLATE_DIR, filename)
            output_path = os.path.join(OUTPUT_DIR, filename)

            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Skip if template doesn't extend customer/base.html
            if "{% extends \"customer/base.html\" %}" not in content:
                continue

            # Apply styling
            styled_content = apply_tailwind_styling(content)

            # Write to output directory
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(styled_content)
            print(f"Processed {filename} -> {output_path}")

if __name__ == "__main__":
    process_templates()
```