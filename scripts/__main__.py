"""Python pre-processor — callable from Node.js as a child process."""
from .pre_analyze import run_pre_analysis
import json
import sys

def main():
    """Reads JSON {jd_text, resume_text} from stdin, writes pre-analysis JSON to stdout."""
    try:
        data = json.load(sys.stdin)
        result = run_pre_analysis(data["jd_text"], data["resume_text"])
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
