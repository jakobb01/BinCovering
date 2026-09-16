"""Compatibility entry point for the shared experiment UI.

Install the repository package first: python -m pip install -e '.[web,plot]'.
"""
from bincovering.web.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=False)
