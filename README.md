# photobooth

we are going to take pibooth and upgrade the hell out of it. and make it into a modern product that runs great on new raspberry pis. i have a photo booth we can use to test! 

## Getting Started

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run server
uvicorn app.main:app --reload
```

Server will start at http://localhost:8000

API docs available at http://localhost:8000/docs

## Scripts

- `uvicorn app.main:app --reload` - Development server
- `pytest` - Run tests
- `ruff check .` - Lint code
- `ruff format .` - Format code