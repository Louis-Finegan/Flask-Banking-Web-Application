"""Local entry point; use Gunicorn for the container's application server."""
from Website import create_app
app = create_app()

if __name__ == '__main__':
    app.run()
