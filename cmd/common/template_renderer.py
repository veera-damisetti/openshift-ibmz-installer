from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=StrictUndefined,
    autoescape=False,
)

def render_template(template_name: str, output_path: Path, config: dict):
    template = _env.get_template(template_name)
    rendered = template.render(**config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")