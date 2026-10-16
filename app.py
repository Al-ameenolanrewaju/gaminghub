"""WSGI entry point for Flask deployments."""

from flask_app import create_app


app = create_app()
