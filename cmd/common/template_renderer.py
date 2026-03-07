from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
import logging
logger = logging.getLogger("ocp_ibmz_install")

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=StrictUndefined,
    autoescape=False,
)

def render_template(template_name: str, output_path: Path, config: dict):
    try:    
        template = _env.get_template(template_name)
        rendered = template.render(**config)
    except Exception as e:
        logger.error("Failed to render template %s: %s", template_name, str(e))
        return 1 , str(e)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")

    logger.debug("Template %s rendered successfully to %s", template_name, output_path)
    return 0, ""