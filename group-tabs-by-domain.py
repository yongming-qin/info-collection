import json
import sys
from urllib.parse import urlparse
from collections import defaultdict
import html
import tldextract
from datetime import datetime

def extract_tabs(data):
    tabs = []
    dates = set()

    def recurse(node):
        if isinstance(node, list) and len(node) >= 2:
            node_data = node[1]
            if isinstance(node_data, dict):
                data_field = node_data.get('data', {})
                url = data_field.get('url')
                title = data_field.get('title', 'No Title')
                icon = data_field.get('favIconUrl', '')
                # Extract date from lastAccessed if available
                if 'lastAccessed' in data_field:
                    try:
                        # Chrome stores timestamps in milliseconds
                        date = datetime.fromtimestamp(data_field['lastAccessed'] / 1000)
                        dates.add(date)
                    except (ValueError, TypeError):
                        pass
                if url:
                    tabs.append({'title': title, 'url': url, 'icon': icon})
            for child in node[2:]:
                recurse(child)
        elif isinstance(node, dict):
            for value in node.values():
                recurse(value)
        elif isinstance(node, list):
            for item in node:
                recurse(item)

    recurse(data)
    return tabs, dates

def deduplicate_tabs(tabs):
    seen = set()
    unique = []
    for tab in tabs:
        if tab['url'] not in seen:
            seen.add(tab['url'])
            unique.append(tab)
    return unique

def get_registrable_domain(url):
    ext = tldextract.extract(url)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    else:
        return urlparse(url).netloc or 'unknown'

def group_by_domain(tabs):
    domain_map = defaultdict(list)
    icon_map = {}
    for tab in tabs:
        domain = get_registrable_domain(tab['url'])
        domain_map[domain].append(tab)
        if domain not in icon_map and tab['icon']:
            icon_map[domain] = tab['icon']
    return domain_map, icon_map


def sanitize_id(text):
    return ''.join(c if c.isalnum() else '-' for c in text)

def generate_html(domain_groups, domain_icons, dates):
    # Format dates
    date_range = ""
    date_range_div = ""
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        date_range = f" ({min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')})"
        date_range_div = f"<div class='date-range'>Date Range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}</div>"

    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>Tabs by Domain{date_range}</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; background-color: #f5f5f5; }",
        "h1 { color: #2c3e50; text-align: center; margin-bottom: 15px; }",
        "h2 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 4px; margin-top: 15px; }",
        ".date-range { color: #666; font-size: 0.9em; text-align: center; margin-bottom: 20px; }",
        "ul { list-style-type: none; padding-left: 0; }",
        ".toc { column-count: auto; column-width: 250px; column-gap: 20px; background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        ".toc li { break-inside: avoid; margin: 4px 0; }",
        ".toc a { text-decoration: none; color: #2980b9; transition: color 0.2s; }",
        ".toc a:hover { color: #3498db; }",
        "li { margin: 6px 0; padding: 4px; border-radius: 4px; transition: background-color 0.2s; }",
        "li:hover { background-color: #f0f0f0; }",
        "li img { vertical-align: middle; width: 16px; height: 16px; margin-right: 6px; }",
        "li a { text-decoration: none; color: #2c3e50; }",
        "li a:hover { color: #3498db; }",
        "hr { border: none; border-top: 2px solid #e0e0e0; margin: 15px 0; }",
        "</style>",
        "</head><body>",
        f"<h1>Tabs Grouped by Domain{date_range}</h1>",
        date_range_div,
        "<h2>Table of Contents</h2>",
        "<ul class='toc'>"
    ]

    # TOC
    for domain in sorted(domain_groups.keys()):
        anchor = sanitize_id(domain)
        icon = domain_icons.get(domain) or f"https://www.google.com/s2/favicons?domain={domain}"
        html_parts.append(
            f'<li><a href="#{anchor}">'
            f'<img src="{html.escape(icon)}" alt="icon">'
            f'{html.escape(domain)}</a></li>'
        )
    html_parts.append("</ul><hr>")

    # Domain sections
    for domain in sorted(domain_groups.keys()):
        anchor = sanitize_id(domain)
        html_parts.append(f'<h2 id="{anchor}">{html.escape(domain)}</h2>')
        html_parts.append("<ul>")
        for tab in domain_groups[domain]:
            title = html.escape(tab['title'])
            url = html.escape(tab['url'])
            icon = html.escape(tab['icon']) if tab['icon'] else f"https://www.google.com/s2/favicons?domain={urlparse(tab['url']).netloc}"
            html_parts.append(
                f'<li><img src="{icon}" alt="icon">'
                f'<a href="{url}" target="_blank">{title}</a></li>'
            )
        html_parts.append("</ul>")

    html_parts.append("</body></html>")
    return '\n'.join(html_parts)

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_tree_to_html.py <input.tree>")
        return

    input_file = sys.argv[1]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tabs, dates = extract_tabs(data)
    tabs = deduplicate_tabs(tabs)
    domain_groups, domain_icons = group_by_domain(tabs)
    
    # Generate output filename with date range
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        date_suffix = f"{min_date.strftime('%Y%m%d')}-{max_date.strftime('%Y%m%d')}"
    else:
        date_suffix = ""
    
    output_file = input_file.replace(".tree", f"-grouped-{date_suffix}.html")
    
    html_content = generate_html(domain_groups, domain_icons, dates)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML saved to {output_file}")
    if dates:
        print(f"Date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
