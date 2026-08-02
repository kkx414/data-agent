from pathlib import Path


def load_prompt(name: str):
    prompt_path = Path(__file__).parents[2]/'prompts'/name
    return prompt_path.read_text(encoding="utf-8")