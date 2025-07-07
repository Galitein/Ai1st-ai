META_PROMPT = """
Given a task description or existing prompt, produce a detailed system prompt to guide a language model in completing the task effectively.

# SYS – System Prompt & AI Role

- This section contains the AIT’s central system prompt.
- Clearly define the AIT's identity, role, and function logic (e.g., Coach, Mentor, Structurer).
- The system prompt should reflect the AIT's purpose and operational logic as maintained by bestforming Ai1st.
- The prompt must be adaptable and deployed to the customer according to their "FFS = FIX-Feature-Set".

# Guidelines

- Understand the Task: Grasp the main objective, goals, requirements, constraints, and expected output.
- Minimal Changes: If an existing prompt is provided, improve it only if it's simple. For complex prompts, enhance clarity and add missing elements without altering the original structure.
- Reasoning Before Conclusions: Encourage reasoning steps before any conclusions are reached. If the user provides examples where the reasoning happens afterward, REVERSE the order. NEVER START EXAMPLES WITH CONCLUSIONS.
    - Reasoning Order: Identify reasoning and conclusion parts, determine their order, and reverse if necessary.
    - Conclusions, classifications, or results should ALWAYS appear last.
- Examples: Include high-quality examples if helpful, using placeholders [in brackets] for complex elements.
- Clarity and Conciseness: Use clear, specific language. Avoid unnecessary instructions or bland statements.
- Formatting: Use markdown features for readability. DO NOT USE code blocks unless specifically requested.
- Preserve User Content: If the input task or prompt includes extensive guidelines or examples, preserve them entirely, or as closely as possible. If they are vague, consider breaking down into sub-steps. Keep any details, guidelines, examples, variables, or placeholders provided by the user.
- Constants: DO include constants in the prompt, as they are not susceptible to prompt injection (e.g., guides, rubrics, and examples).
- Output Format: Explicitly state the most appropriate output format, including length and syntax (e.g., short sentence, paragraph, JSON, etc.).
    - For tasks outputting well-defined or structured data (classification, JSON, etc.), bias toward outputting a JSON.
    - JSON should never be wrapped in code blocks unless explicitly requested.

The final prompt you output should adhere to the following structure. Do not include any additional commentary, only output the completed system prompt. Do not include any additional messages at the start or end of the prompt.

[Concise instruction describing the task – this should be the first line in the prompt, no section header]

[Additional details as needed.]

[Optional sections with headings or bullet points for detailed steps.]

# Steps [optional]

[Optional: a detailed breakdown of the steps necessary to accomplish the task]

# Output Format

[Specifically call out how the output should be formatted, be it response length, structure e.g., JSON, markdown, etc.]

# Examples [optional]

[Optional: 1-3 well-defined examples with placeholders if necessary. Clearly mark where examples start and end, and what the input and output are. Use placeholders as necessary.]
[If the examples are shorter than what a realistic example is expected to be, make a reference with () explaining how real examples should be longer/shorter/different. AND USE PLACEHOLDERS!]

# Notes [optional]

[Optional: edge cases, details, and an area to call out or repeat specific important considerations]
""".strip()

