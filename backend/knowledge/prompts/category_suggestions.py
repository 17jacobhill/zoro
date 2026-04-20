CATEGORY_MERGE_PROMPT = """
Analyze these categories and their actual rules to suggest intelligent merges:

{category_details}

For each suggested merge:
1. Look at the ACTUAL CONTENT of rules, not just category names
2. Merge categories where rules overlap in purpose/domain
3. Keep separate categories with similar names but distinct content
4. Choose the clearest target category name

Example: "ui-styling" and "component-architecture" might have similar names but serve different purposes based on their rules.

Return JSON:
{{
  "suggestions": [
    {{
      "merge_from": ["category-a", "category-b"],
      "merge_to": "target-category",
      "reasoning": "Detailed reasoning based on rule content analysis"
    }}
  ]
}}

Only suggest merges that truly improve organization based on the actual rule content.
"""
